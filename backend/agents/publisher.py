"""
Publisher Agent — takes approved listing copy and posts to each target platform.
"""
import structlog
from typing import Any

from ..platforms.base import ListingDraft
from ..platforms.ebay import EbayAdapter
from ..platforms.vinted import VintedAdapter

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
        description = listing_copy.get(desc_key) or ""

        draft = ListingDraft(
            title=title,
            description=description,
            price=final_price,
            category_id=item_data.get("ebay_category_id", ""),
            condition=item_data.get("condition", "good"),
            image_paths=image_paths,
        )

        try:
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
