"""
eBay adapter using the eBay Sell API (REST).
Sandbox mode is used by default; set EBAY_SANDBOX=false for production.
"""
import asyncio
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

_MARKETPLACE_CURRENCIES = {
    "EBAY_US": "USD",
    "EBAY_CA": "CAD",
    "EBAY_GB": "GBP",
    "EBAY_AU": "AUD",
    "EBAY_IT": "EUR",
    "EBAY_DE": "EUR",
    "EBAY_FR": "EUR",
    "EBAY_ES": "EUR",
    "EBAY_AT": "EUR",
    "EBAY_BE": "EUR",
    "EBAY_NL": "EUR",
    "EBAY_CH": "CHF",
    "EBAY_PL": "PLN",
}

# Content-Language for createOffer (eBay recommends matching marketplace locale)
_MARKETPLACE_CONTENT_LANGUAGE = {
    "EBAY_US": "en-US",
    "EBAY_IT": "it-IT",
    "EBAY_DE": "de-DE",
    "EBAY_FR": "fr-FR",
    "EBAY_ES": "es-ES",
    "EBAY_GB": "en-GB",
    "EBAY_AU": "en-AU",
    "EBAY_CA": "en-CA",
    "EBAY_AT": "de-AT",
    "EBAY_BE": "fr-BE",
    "EBAY_NL": "nl-NL",
    "EBAY_CH": "de-CH",
    "EBAY_PL": "pl-PL",
}

def _marketplace_currency() -> str:
    return _MARKETPLACE_CURRENCIES.get(settings.EBAY_MARKETPLACE_ID, "USD")


class EbayAdapter(BasePlatformAdapter):
    """
    eBay REST API adapter.
    Uses per-user token if access_token is passed; otherwise falls back to
    EBAY_USER_TOKEN / EBAY_PROD_USER_TOKEN from settings.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        marketplace_id: Optional[str] = None,
        sandbox: Optional[bool] = None,
    ):
        self._sandbox = settings.EBAY_SANDBOX if sandbox is None else sandbox
        self._base = EBAY_SANDBOX_BASE if self._sandbox else EBAY_PROD_BASE
        self._token = access_token
        if self._token is None:
            self._token = settings.EBAY_USER_TOKEN if self._sandbox else settings.EBAY_PROD_USER_TOKEN
        if not (self._token and self._token.strip()):
            raise ValueError(
                "eBay token missing. Set EBAY_PROD_USER_TOKEN in .env or connect your account via "
                "OAuth: open /api/auth/ebay/authorize in the app."
            )
        self._marketplace_id = marketplace_id or settings.EBAY_MARKETPLACE_ID

    @property
    def platform_name(self) -> str:
        return "ebay"

    def _headers(self) -> dict:
        content_lang = _MARKETPLACE_CONTENT_LANGUAGE.get(
            self._marketplace_id, "en-US"
        )
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Content-Language": content_lang,
            "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
        }

    async def post_listing(self, draft: ListingDraft) -> PublishedListing:
        """Create an inventory item + offer, then publish."""
        sku = f"ernesto-{datetime.utcnow().timestamp()}"

        async with httpx.AsyncClient(base_url=self._base) as client:
            # 1. Create inventory item (draft.image_paths are already full URLs from publisher)
            image_urls = [p for p in draft.image_paths if p and p.startswith("http")]
            if not image_urls:
                log.warning("ebay.no_image_urls_using_placeholder", sku=sku)
                image_urls = ["https://ir.ebaystatic.com/cr/v/c1/ebay-logo-1-1200x630-margin.png"]
            inventory_payload = {
                "availability": {"shipToLocationAvailability": {"quantity": 1}},
                "condition": self._map_condition(draft.condition),
                "packageWeightAndSize": {
                    "dimensions": {"height": 5, "length": 10, "width": 5, "unit": "INCH"},
                    "packageType": "PACKAGE_THICK_ENVELOPE",
                    "weight": {"value": 1, "unit": "POUND"},
                },
                "product": {
                    "title": draft.title,
                    "description": draft.description,
                    "imageUrls": image_urls,
                },
            }
            resp = await client.put(
                f"/sell/inventory/v1/inventory_item/{sku}",
                json=inventory_payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            log.info("ebay.inventory_item_created", sku=sku)

            # Allow eBay a moment to make the SKU available for the marketplace (avoids 25751 on non-US sites)
            await asyncio.sleep(2)

            # 2. Create offer (retry on 25751: SKU not found/not available for marketplace)
            listing_policies = draft.extra.get("listing_policies") or {
                "fulfillmentPolicyId": settings.EBAY_FULFILLMENT_POLICY_ID,
                "paymentPolicyId": settings.EBAY_PAYMENT_POLICY_ID,
                "returnPolicyId": settings.EBAY_RETURN_POLICY_ID,
            }
            if not listing_policies.get("fulfillmentPolicyId"):
                raise ValueError(
                    "eBay requires listing policies. Run 'python test_ebay.py --prod' to set up "
                    "policies and add EBAY_FULFILLMENT_POLICY_ID, EBAY_PAYMENT_POLICY_ID, "
                    "EBAY_RETURN_POLICY_ID to backend/.env."
                )
            offer_payload = {
                "sku": sku,
                "marketplaceId": self._marketplace_id,
                "format": "FIXED_PRICE",
                "availableQuantity": 1,
                "categoryId": draft.category_id,
                "listingDescription": draft.description,
                "listingPolicies": listing_policies,
                "pricingSummary": {
                    "price": {"value": str(draft.price), "currency": _MARKETPLACE_CURRENCIES.get(self._marketplace_id, "USD")}
                },
            }
            merchant_location_key = draft.extra.get("merchant_location_key") or \
                settings.EBAY_MERCHANT_LOCATION_KEY
            if merchant_location_key:
                offer_payload["merchantLocationKey"] = merchant_location_key

            def _is_sku_not_available(resp: httpx.Response) -> bool:
                if resp.status_code != 400:
                    return False
                try:
                    data = resp.json()
                    for err in data.get("errors", []):
                        if err.get("errorId") == 25751:
                            return True
                    return False
                except Exception:
                    return False

            max_offer_attempts = 3
            resp = None
            for attempt in range(max_offer_attempts):
                resp = await client.post(
                    "/sell/inventory/v1/offer",
                    json=offer_payload,
                    headers=self._headers(),
                )
                if resp.is_success:
                    break
                if _is_sku_not_available(resp) and attempt < max_offer_attempts - 1:
                    wait_sec = 3 + attempt * 2
                    log.info(
                        "ebay.offer_retry",
                        sku=sku,
                        marketplace_id=self._marketplace_id,
                        attempt=attempt + 1,
                        wait_sec=wait_sec,
                    )
                    await asyncio.sleep(wait_sec)
                    continue
                log.error("ebay.offer_error", status=resp.status_code, body=resp.text, payload=offer_payload)
                resp.raise_for_status()
            assert resp is not None and resp.is_success
            offer_id = resp.json()["offerId"]

            # 3. Publish offer
            resp = await client.post(
                f"/sell/inventory/v1/offer/{offer_id}/publish",
                headers=self._headers(),
            )
            if not resp.is_success:
                log.error("ebay.publish_error", status=resp.status_code, body=resp.text, offer_id=offer_id)
            resp.raise_for_status()
            listing_id = resp.json()["listingId"]

        if self._sandbox:
            base_url = "sandbox.ebay.com"
        else:
            marketplace_domains = {
                "EBAY_US": "ebay.com",
                "EBAY_IT": "ebay.it",
                "EBAY_GB": "ebay.co.uk",
                "EBAY_DE": "ebay.de",
                "EBAY_FR": "ebay.fr",
                "EBAY_ES": "ebay.es",
                "EBAY_AU": "ebay.com.au",
                "EBAY_CA": "ebay.ca",
                "EBAY_AT": "ebay.at",
                "EBAY_BE": "ebay.be",
                "EBAY_NL": "ebay.nl",
                "EBAY_CH": "ebay.ch",
                "EBAY_PL": "ebay.pl",
            }
            base_url = marketplace_domains.get(self._marketplace_id, "ebay.com")
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
                json={"counterOffer": {"price": {"value": str(amount), "currency": _MARKETPLACE_CURRENCIES.get(self._marketplace_id, "USD")}}},
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
        # USED_EXCELLENT and USED_GOOD are accepted by virtually all eBay categories.
        # LIKE_NEW and EXCELLENT_REFURBISHED are only valid for specific categories
        # (e.g. certified refurbished electronics), so we avoid them here.
        mapping = {
            "new": "NEW",
            "like new": "USED_EXCELLENT",
            "excellent": "USED_EXCELLENT",
            "good": "USED_GOOD",
            "fair": "USED_ACCEPTABLE",
            "poor": "FOR_PARTS_OR_NOT_WORKING",
        }
        return mapping.get(condition.lower(), "USED_GOOD")
