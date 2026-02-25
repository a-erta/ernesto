"""
Listing Agent — generates platform-optimised listing copy and suggests a price
based on sold comparables fetched from each target platform.
"""
import json
import statistics
import structlog
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..config import settings
from ..platforms.ebay import EbayAdapter
from ..platforms.vinted import VintedAdapter

log = structlog.get_logger()

LISTING_SYSTEM_PROMPT = """You are an expert copywriter for second-hand selling platforms.
Given structured item data and a list of comparable sold listings, generate:
- ebay_title: eBay-optimised title (keyword-rich, max 80 chars)
- ebay_description: eBay listing description (HTML allowed, 2-4 paragraphs)
- vinted_title: Vinted-optimised title (casual, friendly, max 60 chars)
- vinted_description: Vinted description (conversational, 1-2 paragraphs)
- suggested_price: recommended asking price in USD based on comparables
- price_rationale: brief explanation of the price recommendation

Respond ONLY with valid JSON. No markdown, no explanation."""


PLATFORM_ADAPTERS = {
    "ebay": EbayAdapter,
    "vinted": VintedAdapter,
}


async def _fetch_comparables(item_data: dict, platforms: list[str]) -> list[dict]:
    """Fetch sold comparables from all target platforms."""
    query = " ".join(filter(None, [
        item_data.get("brand"),
        item_data.get("model"),
        item_data.get("title", "").split()[0] if item_data.get("title") else None,
    ]))
    if not query:
        query = item_data.get("category", "item")

    all_comps: list[dict] = []
    for platform_name in platforms:
        adapter_cls = PLATFORM_ADAPTERS.get(platform_name)
        if not adapter_cls:
            continue
        try:
            adapter = adapter_cls()
            comps = await adapter.get_sold_comparables(query, limit=8)
            all_comps.extend(comps)
            log.info("listing.comparables_fetched", platform=platform_name, count=len(comps))
        except Exception as e:
            log.warning("listing.comparables_error", platform=platform_name, error=str(e))

    return all_comps


def _calculate_price_suggestion(comparables: list[dict], condition: str) -> float | None:
    """Median of comp prices adjusted by condition multiplier."""
    prices = [c["sold_price"] for c in comparables if c.get("sold_price", 0) > 0]
    if not prices:
        return None

    median = statistics.median(prices)

    condition_multipliers = {
        "new": 1.0,
        "like new": 0.90,
        "excellent": 0.80,
        "good": 0.70,
        "fair": 0.55,
        "poor": 0.35,
    }
    multiplier = condition_multipliers.get(condition.lower(), 0.70)
    return round(median * multiplier, 2)


async def run_listing(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: listing.
    Fetches comparables, generates platform copy, suggests price.
    """
    item_data: dict = state.get("item_data", {})
    platforms: list[str] = state.get("platforms", ["ebay"])

    if not item_data:
        return {**state, "errors": state.get("errors", []) + ["No item data available for listing generation"]}

    log.info("listing.start", title=item_data.get("title"), platforms=platforms)

    # 1. Fetch comparables
    comparables = await _fetch_comparables(item_data, platforms)
    price_suggestion = _calculate_price_suggestion(comparables, item_data.get("condition", "good"))

    # 2. Generate listing copy via LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.4,
    )

    prompt_data = {
        "item": item_data,
        "comparables": comparables[:10],
        "price_suggestion_from_comps": price_suggestion,
        "target_platforms": platforms,
    }

    messages = [
        SystemMessage(content=LISTING_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(prompt_data, indent=2)),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        listing_copy = json.loads(raw)
    except json.JSONDecodeError:
        log.error("listing.json_parse_error", raw=raw[:200])
        listing_copy = {
            "ebay_title": item_data.get("title", "Item for sale"),
            "ebay_description": item_data.get("title", ""),
            "vinted_title": item_data.get("title", "Item for sale"),
            "vinted_description": item_data.get("title", ""),
            "suggested_price": price_suggestion or 0,
            "price_rationale": "Based on comparable listings",
        }

    log.info(
        "listing.complete",
        suggested_price=listing_copy.get("suggested_price"),
        comps_count=len(comparables),
    )

    return {
        **state,
        "step": "awaiting_approval",
        "comparables": comparables,
        "listing_copy": listing_copy,
        "suggested_price": listing_copy.get("suggested_price") or price_suggestion,
        "awaiting_human": True,
    }
