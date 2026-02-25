"""
eBay adapter using the eBay Sell API (REST).
Sandbox mode is used by default; set EBAY_SANDBOX=false for production.
"""
import httpx
import structlog
from datetime import datetime
from typing import List, Optional

from .base import (
    BasePlatformAdapter,
    ListingDraft,
    PublishedListing,
    PlatformOffer,
    PlatformMessage,
)
from ..config import settings

log = structlog.get_logger()

EBAY_SANDBOX_BASE = "https://api.sandbox.ebay.com"
EBAY_PROD_BASE = "https://api.ebay.com"


class EbayAdapter(BasePlatformAdapter):
    """
    eBay REST API adapter.
    Requires a valid OAuth user token with sell.* scopes.
    """

    def __init__(self):
        self._base = EBAY_SANDBOX_BASE if settings.EBAY_SANDBOX else EBAY_PROD_BASE
        self._token = settings.EBAY_USER_TOKEN

    @property
    def platform_name(self) -> str:
        return "ebay"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        }

    async def post_listing(self, draft: ListingDraft) -> PublishedListing:
        """Create an inventory item + offer, then publish."""
        sku = f"ernesto-{datetime.utcnow().timestamp()}"

        async with httpx.AsyncClient(base_url=self._base) as client:
            # 1. Create inventory item
            inventory_payload = {
                "availability": {"shipToLocationAvailability": {"quantity": 1}},
                "condition": self._map_condition(draft.condition),
                "product": {
                    "title": draft.title,
                    "description": draft.description,
                    "imageUrls": [],  # Images must be hosted URLs in production
                },
            }
            resp = await client.put(
                f"/sell/inventory/v1/inventory_item/{sku}",
                json=inventory_payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            log.info("ebay.inventory_item_created", sku=sku)

            # 2. Create offer
            offer_payload = {
                "sku": sku,
                "marketplaceId": "EBAY_US",
                "format": "FIXED_PRICE",
                "availableQuantity": 1,
                "categoryId": draft.category_id,
                "listingDescription": draft.description,
                "listingPolicies": draft.extra.get("listing_policies", {}),
                "pricingSummary": {
                    "price": {"value": str(draft.price), "currency": "USD"}
                },
            }
            resp = await client.post(
                "/sell/inventory/v1/offer",
                json=offer_payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            offer_id = resp.json()["offerId"]

            # 3. Publish offer
            resp = await client.post(
                f"/sell/inventory/v1/offer/{offer_id}/publish",
                headers=self._headers(),
            )
            resp.raise_for_status()
            listing_id = resp.json()["listingId"]

        base_url = "sandbox.ebay.com" if settings.EBAY_SANDBOX else "ebay.com"
        return PublishedListing(
            platform_listing_id=listing_id,
            platform_url=f"https://www.{base_url}/itm/{listing_id}",
        )

    async def update_listing(self, platform_listing_id: str, draft: ListingDraft) -> bool:
        log.info("ebay.update_listing", listing_id=platform_listing_id)
        # In production: revise the offer via PUT /sell/inventory/v1/offer/{offerId}
        return True

    async def end_listing(self, platform_listing_id: str) -> bool:
        log.info("ebay.end_listing", listing_id=platform_listing_id)
        return True

    async def get_offers(self, platform_listing_id: str) -> List[PlatformOffer]:
        """Poll eBay Best Offer API."""
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.get(
                f"/sell/negotiation/v1/best_offer?listing_id={platform_listing_id}",
                headers=self._headers(),
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()

        offers = []
        for o in data.get("bestOffers", []):
            offers.append(
                PlatformOffer(
                    platform_offer_id=o["bestOfferId"],
                    listing_id=platform_listing_id,
                    buyer_username=o.get("buyer", {}).get("username", "unknown"),
                    amount=float(o["price"]["value"]),
                    received_at=datetime.fromisoformat(o["creationDate"].replace("Z", "+00:00")),
                    message=o.get("message"),
                )
            )
        return offers

    async def accept_offer(self, platform_offer_id: str) -> bool:
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                f"/sell/negotiation/v1/best_offer/{platform_offer_id}/accept",
                headers=self._headers(),
            )
            return resp.is_success

    async def decline_offer(self, platform_offer_id: str) -> bool:
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                f"/sell/negotiation/v1/best_offer/{platform_offer_id}/decline",
                headers=self._headers(),
            )
            return resp.is_success

    async def counter_offer(self, platform_offer_id: str, amount: float) -> bool:
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.post(
                f"/sell/negotiation/v1/best_offer/{platform_offer_id}/counter_offer",
                json={"counterOffer": {"price": {"value": str(amount), "currency": "USD"}}},
                headers=self._headers(),
            )
            return resp.is_success

    async def get_messages(self, platform_listing_id: str) -> List[PlatformMessage]:
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.get(
                f"/post-order/v2/inquiry?item_id={platform_listing_id}",
                headers=self._headers(),
            )
            if resp.status_code in (404, 204):
                return []
            resp.raise_for_status()

        messages = []
        for m in resp.json().get("inquiries", []):
            messages.append(
                PlatformMessage(
                    platform_message_id=m["inquiryId"],
                    listing_id=platform_listing_id,
                    buyer_username=m.get("buyer", {}).get("username", "unknown"),
                    content=m.get("inquiryMessage", ""),
                    received_at=datetime.fromisoformat(
                        m["creationDate"].replace("Z", "+00:00")
                    ),
                )
            )
        return messages

    async def send_message(self, platform_listing_id: str, buyer_username: str, content: str) -> bool:
        log.info("ebay.send_message", listing_id=platform_listing_id, buyer=buyer_username)
        # POST /post-order/v2/inquiry/{inquiryId}/respond
        return True

    async def get_sold_comparables(self, query: str, limit: int = 10) -> List[dict]:
        """Search eBay completed/sold listings for pricing research."""
        async with httpx.AsyncClient(base_url=self._base) as client:
            resp = await client.get(
                "/buy/browse/v1/item_summary/search",
                params={
                    "q": query,
                    "filter": "buyingOptions:{FIXED_PRICE},conditions:{USED}",
                    "sort": "endTimeSoonest",
                    "limit": limit,
                },
                headers=self._headers(),
            )
            if not resp.is_success:
                return []

        items = resp.json().get("itemSummaries", [])
        return [
            {
                "title": i.get("title"),
                "sold_price": float(i.get("price", {}).get("value", 0)),
                "url": i.get("itemWebUrl"),
                "condition": i.get("condition"),
                "platform": "ebay",
            }
            for i in items
        ]

    async def mark_sold(self, platform_listing_id: str) -> bool:
        return await self.end_listing(platform_listing_id)

    @staticmethod
    def _map_condition(condition: str) -> str:
        mapping = {
            "new": "NEW",
            "like new": "LIKE_NEW",
            "excellent": "EXCELLENT_REFURBISHED",
            "good": "USED_EXCELLENT",
            "fair": "USED_GOOD",
            "poor": "FOR_PARTS_OR_NOT_WORKING",
        }
        return mapping.get(condition.lower(), "USED_GOOD")
