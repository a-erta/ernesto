"""
Deal Manager Agent — monitors platform inboxes, auto-answers common questions,
and surfaces offers to the human for a decision.
"""
import json
import structlog
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..config import settings
from ..platforms.ebay import EbayAdapter
from ..platforms.vinted import VintedAdapter

log = structlog.get_logger()

PLATFORM_ADAPTERS = {
    "ebay": EbayAdapter,
    "vinted": VintedAdapter,
}

AUTO_REPLY_SYSTEM_PROMPT = """You are a helpful seller assistant.
Given item details and a buyer's question, write a concise, friendly reply.
If the question is about price negotiation, politely redirect to the offer system.
If you cannot answer confidently, say you'll check and get back to them.
Reply in plain text, max 3 sentences."""

OFFER_ANALYSIS_PROMPT = """You are a negotiation advisor for a second-hand seller.
Given the listing price, the buyer's offer, and comparable sold prices,
provide a brief recommendation: accept, decline, or counter (with suggested counter price).
Respond as JSON: {"recommendation": "accept|decline|counter", "counter_price": null_or_float, "reasoning": "..."}"""


async def _auto_reply_message(item_data: dict, message_content: str) -> str:
    """Generate an automatic reply to a buyer question."""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.3,
    )
    messages = [
        SystemMessage(content=AUTO_REPLY_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps({
            "item": item_data,
            "buyer_question": message_content,
        })),
    ]
    response = await llm.ainvoke(messages)
    return response.content.strip()


async def _analyse_offer(
    listing_price: float,
    offer_amount: float,
    comparables: list[dict],
    item_data: dict,
) -> dict:
    """Ask the LLM for an offer recommendation."""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
    )
    messages = [
        SystemMessage(content=OFFER_ANALYSIS_PROMPT),
        HumanMessage(content=json.dumps({
            "listing_price": listing_price,
            "offer_amount": offer_amount,
            "comparables": comparables[:5],
            "item": item_data,
        })),
    ]
    response = await llm.ainvoke(messages)
    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"recommendation": "counter", "counter_price": None, "reasoning": response.content}


async def run_deal_manager(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: deal_manager.
    Polls inboxes for new messages and offers.
    - Auto-replies to informational questions.
    - Surfaces offers to the human (sets awaiting_human=True).
    """
    published_listings: list[dict] = state.get("published_listings", [])
    item_data: dict = state.get("item_data", {})
    comparables: list[dict] = state.get("comparables", [])

    new_messages: list[dict] = []
    pending_offers: list[dict] = []

    for listing in published_listings:
        platform_name = listing["platform"]
        platform_listing_id = listing["platform_listing_id"]
        adapter_cls = PLATFORM_ADAPTERS.get(platform_name)
        if not adapter_cls:
            continue

        adapter = adapter_cls()

        # Check messages
        try:
            messages = await adapter.get_messages(platform_listing_id)
            for msg in messages:
                already_seen = any(
                    m.get("platform_message_id") == msg.platform_message_id
                    for m in state.get("seen_messages", [])
                )
                if already_seen:
                    continue

                reply = await _auto_reply_message(item_data, msg.content)
                await adapter.send_message(platform_listing_id, msg.buyer_username, reply)

                new_messages.append({
                    "platform": platform_name,
                    "platform_message_id": msg.platform_message_id,
                    "buyer_username": msg.buyer_username,
                    "content": msg.content,
                    "auto_reply": reply,
                })
                log.info("deal_manager.auto_replied", buyer=msg.buyer_username)
        except Exception as e:
            log.warning("deal_manager.messages_error", platform=platform_name, error=str(e))

        # Check offers
        try:
            offers = await adapter.get_offers(platform_listing_id)
            for offer in offers:
                already_seen = any(
                    o.get("platform_offer_id") == offer.platform_offer_id
                    for o in state.get("seen_offers", [])
                )
                if already_seen:
                    continue

                analysis = await _analyse_offer(
                    listing_price=listing["price"],
                    offer_amount=offer.amount,
                    comparables=comparables,
                    item_data=item_data,
                )

                pending_offers.append({
                    "platform": platform_name,
                    "platform_offer_id": offer.platform_offer_id,
                    "platform_listing_id": platform_listing_id,
                    "buyer_username": offer.buyer_username,
                    "amount": offer.amount,
                    "listing_price": listing["price"],
                    "ai_recommendation": analysis,
                })
                log.info(
                    "deal_manager.offer_received",
                    buyer=offer.buyer_username,
                    amount=offer.amount,
                    recommendation=analysis.get("recommendation"),
                )
        except Exception as e:
            log.warning("deal_manager.offers_error", platform=platform_name, error=str(e))

    seen_messages = state.get("seen_messages", []) + new_messages
    seen_offers = state.get("seen_offers", []) + [
        {"platform_offer_id": o["platform_offer_id"]} for o in pending_offers
    ]

    awaiting_human = len(pending_offers) > 0

    return {
        **state,
        "step": "awaiting_offer_decision" if awaiting_human else "managing",
        "new_messages": new_messages,
        "pending_offers": pending_offers,
        "seen_messages": seen_messages,
        "seen_offers": seen_offers,
        "awaiting_human": awaiting_human,
    }
