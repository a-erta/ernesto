"""
Intake Agent — analyses photos and user description using GPT-4o vision
to produce a structured item profile.

Fallback strategy:
1. Try vision (image + description).
2. If OpenAI refuses or vision fails, retry with text-only using the description.
3. If no description either, build a minimal placeholder so the pipeline continues.
"""
import base64
import json
import structlog
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..config import settings

log = structlog.get_logger()

SYSTEM_PROMPT = """You are an expert second-hand goods appraiser.
Given one or more product photos and an optional user description, extract:
- title: concise, keyword-rich listing title (max 80 chars)
- category: product category (e.g. "Men's Clothing > Jackets", "Electronics > Smartphones")
- brand: brand name if identifiable, else null
- model: model name/number if identifiable, else null
- condition: one of [new, like new, excellent, good, fair, poor]
- condition_notes: brief description of visible wear or defects
- color: primary color
- size: size if applicable (clothing/shoes), else null
- key_features: list of notable features or selling points
- confidence: your confidence score 0-1

Respond ONLY with valid JSON matching the schema above. No markdown, no explanation."""

TEXT_ONLY_PROMPT = """You are an expert second-hand goods appraiser.
Based on the user's description below, extract a structured item profile:
- title: concise, keyword-rich listing title (max 80 chars)
- category: product category (e.g. "Men's Clothing > Jackets", "Pets > Accessories")
- brand: brand name if mentioned, else null
- model: model name/number if mentioned, else null
- condition: one of [new, like new, excellent, good, fair, poor] — default to "good" if unknown
- condition_notes: any wear details mentioned, else null
- color: color if mentioned, else null
- size: size if applicable, else null
- key_features: list of notable features or selling points derived from the description
- confidence: your confidence score 0-1

Respond ONLY with valid JSON matching the schema above. No markdown, no explanation."""

# Phrases that indicate a content policy refusal
_REFUSAL_PHRASES = [
    "i'm sorry",
    "i can't assist",
    "i cannot assist",
    "i'm not able",
    "i cannot help",
    "i can't help",
    "unable to assist",
    "against my guidelines",
    "not something i can",
]


def _is_refusal(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _REFUSAL_PHRASES)


def _parse_json(raw: str) -> dict | None:
    """Strip markdown fences and parse JSON. Returns None on failure."""
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def run_intake(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: intake.
    Reads image_paths and user_description from state,
    returns enriched state with item_data populated.
    """
    image_paths: list[str] = state.get("image_paths", [])
    user_description: str = state.get("user_description", "")

    log.info("intake.start", images=len(image_paths), has_description=bool(user_description))

    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
    )

    # ------------------------------------------------------------------
    # Step 1: Try vision if we have images
    # ------------------------------------------------------------------
    item_data = None

    if image_paths:
        content: list[dict] = []
        if user_description:
            content.append({"type": "text", "text": f"User description: {user_description}"})

        images_loaded = 0
        for path_str in image_paths:
            path = Path(path_str)
            if not path.exists():
                log.warning("intake.image_not_found", path=path_str)
                continue
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            suffix = path.suffix.lower().lstrip(".")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/jpeg")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
            })
            images_loaded += 1

        if content:
            try:
                messages = [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=content),
                ]
                response = await llm.ainvoke(messages)
                raw = response.content.strip()

                if _is_refusal(raw):
                    log.warning("intake.vision_refused", reason=raw[:120])
                else:
                    item_data = _parse_json(raw)
                    if item_data is None:
                        log.warning("intake.vision_parse_failed", raw=raw[:120])

            except Exception as e:
                log.warning("intake.vision_error", error=str(e))

    # ------------------------------------------------------------------
    # Step 2: Fall back to text-only if vision failed or was refused
    # ------------------------------------------------------------------
    if item_data is None and user_description:
        log.info("intake.fallback_text_only")
        try:
            messages = [
                SystemMessage(content=TEXT_ONLY_PROMPT),
                HumanMessage(content=f"User description: {user_description}"),
            ]
            response = await llm.ainvoke(messages)
            raw = response.content.strip()
            item_data = _parse_json(raw)
            if item_data is None:
                log.error("intake.text_parse_failed", raw=raw[:200])
        except Exception as e:
            log.error("intake.text_error", error=str(e))

    # ------------------------------------------------------------------
    # Step 3: Last resort — minimal placeholder so pipeline continues
    # ------------------------------------------------------------------
    if item_data is None:
        log.warning("intake.using_placeholder")
        item_data = {
            "title": user_description[:80] if user_description else "Item for sale",
            "category": "Other",
            "brand": None,
            "model": None,
            "condition": "good",
            "condition_notes": None,
            "color": None,
            "size": None,
            "key_features": [],
            "confidence": 0.1,
        }

    log.info("intake.complete", title=item_data.get("title"), confidence=item_data.get("confidence"))

    return {
        **state,
        "step": "listing",
        "item_data": item_data,
    }
