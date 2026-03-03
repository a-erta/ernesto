"""
Publisher Agent — takes approved listing copy and posts to each target platform.
Uses per-user eBay token (with refresh) when available; otherwise falls back to env.
"""
import structlog
from typing import Any

from ..platforms.base import ListingDraft
from ..platforms.ebay import EbayAdapter
from ..platforms.vinted import VintedAdapter
from ..models.db import AsyncSessionLocal
from ..api.credentials_routes import get_ebay_access_token
from ..config import settings

log = structlog.get_logger()

PLATFORM_ADAPTERS = {
    "ebay": EbayAdapter,
    "vinted": VintedAdapter,
}

PLATFORM_COPY_KEYS = {
    "ebay": ("ebay_title", "ebay_description"),
    "vinted": ("vinted_title", "vinted_description"),
}


async def run_publisher(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: publisher.
    Posts approved listings to all target platforms.
    Expects state to contain human-approved listing_copy and final_price.
    """
    listing_copy: dict = state.get("listing_copy", {})
    item_data: dict = state.get("item_data", {})
    platforms: list[str] = state.get("platforms", ["ebay"])
    final_price: float = state.get("final_price") or state.get("suggested_price", 0)
    image_paths: list[str] = state.get("image_paths", [])

    published: list[dict] = []
    errors: list[str] = list(state.get("errors", []))

    for platform_name in platforms:
        adapter_cls = PLATFORM_ADAPTERS.get(platform_name)
        if not adapter_cls:
            log.warning("publisher.unknown_platform", platform=platform_name)
            continue

        title_key, desc_key = PLATFORM_COPY_KEYS.get(platform_name, ("ebay_title", "ebay_description"))
        title = listing_copy.get(title_key) or item_data.get("title", "Item for sale")
        # Prefer the human-approved description; fall back to LLM-generated copy
        human_description = state.get("human_input", {}).get("description", "")
        raw_description = human_description or listing_copy.get(desc_key) or ""
        # Ensure description is wrapped in HTML for eBay
        if raw_description and not raw_description.strip().startswith("<"):
            description = f"<p>{raw_description}</p>"
        else:
            description = raw_description

        draft = ListingDraft(
            title=title,
            description=description,
            price=final_price,
            category_id="29223",  # Antiquarian & Collectible — no required item specifics
            condition=item_data.get("condition", "good"),
            image_paths=image_paths,
        )

        try:
            if platform_name == "ebay":
                user_id = state.get("user_id")
                access_token = None
                if user_id:
                    async with AsyncSessionLocal() as db:
                        access_token = await get_ebay_access_token(user_id, db)
                if access_token:
                    log.info("publisher.ebay_token", source="user_oauth", user_id=user_id)
                else:
                    log.info("publisher.ebay_token", source="env_fallback", user_id=user_id)
                adapter = EbayAdapter(
                    access_token=access_token,
                    marketplace_id=settings.EBAY_MARKETPLACE_ID,
                    sandbox=settings.EBAY_SANDBOX,
                )
            else:
                adapter = adapter_cls()
            result = await adapter.post_listing(draft)
            published.append({
                "platform": platform_name,
                "platform_listing_id": result.platform_listing_id,
                "platform_url": result.platform_url,
                "title": title,
                "price": final_price,
                "status": "published",
            })
            log.info("publisher.published", platform=platform_name, listing_id=result.platform_listing_id)
        except Exception as e:
            log.error("publisher.error", platform=platform_name, error=str(e))
            errors.append(f"Failed to publish on {platform_name}: {e}")
            # Always save a listing record so the UI can show it, even if the
            # platform call failed (e.g. missing credentials). Status = draft.
            published.append({
                "platform": platform_name,
                "platform_listing_id": None,
                "platform_url": None,
                "title": title,
                "price": final_price,
                "status": "draft",
            })

    return {
        **state,
        "step": "managing",
        "published_listings": published,
        "errors": errors,
        "awaiting_human": False,
    }
