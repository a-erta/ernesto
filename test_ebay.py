"""
eBay diagnostic script — works for both sandbox and production.

Usage (from the ernesto/ directory, venv active):
    python test_ebay.py            # uses EBAY_SANDBOX setting from .env
    python test_ebay.py --prod     # force production mode
    python test_ebay.py --sandbox  # force sandbox mode

⚠️  PRODUCTION WARNING: this script will create a REAL listing on eBay.
    It will ask for confirmation before publishing and offers a cleanup option.
    The listing price is set to $999.99 to avoid accidental sales.
"""
import asyncio
import json
import sys
from datetime import datetime

import httpx

sys.path.insert(0, ".")
from backend.config import settings

# ── mode selection ────────────────────────────────────────────────────────────

if "--prod" in sys.argv:
    PRODUCTION = True
elif "--sandbox" in sys.argv:
    PRODUCTION = False
else:
    PRODUCTION = not settings.EBAY_SANDBOX

BASE = "https://api.ebay.com" if PRODUCTION else "https://api.sandbox.ebay.com"
TOKEN = settings.EBAY_PROD_USER_TOKEN if PRODUCTION else settings.EBAY_USER_TOKEN
APP_ID = settings.EBAY_PROD_APP_ID if PRODUCTION else settings.EBAY_APP_ID
CERT_ID = settings.EBAY_PROD_CERT_ID if PRODUCTION else settings.EBAY_CERT_ID

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Content-Language": "en-US",
    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)

def show(label: str, resp: httpx.Response):
    ok = "✅" if resp.is_success else "❌"
    print(f"\n{ok} {label}")
    print(f"   Status : {resp.status_code}")
    try:
        body = resp.json()
        print(f"   Body   : {json.dumps(body, indent=4)}")
    except Exception:
        print(f"   Body   : {resp.text[:500]}")
    return resp.is_success

# ── steps ─────────────────────────────────────────────────────────────────────

async def check_token():
    section("STEP 0 — Token & seller registration check")
    print(f"\n   Mode     : {'🔴 PRODUCTION' if PRODUCTION else '🟡 SANDBOX'}")
    print(f"   Base URL : {BASE}")
    print(f"   Token    : {TOKEN[:40]}...")
    print(f"   Length   : {len(TOKEN)} chars")

    if len(TOKEN) < 200:
        print("\n   ❌ Token too short — looks like a legacy Auth'n'Auth token.")
        print("      Need an OAuth token (400+ chars).")
        _print_token_instructions()
        return False

    async with httpx.AsyncClient(base_url=BASE) as c:
        # Check inventory access
        resp = await c.get(
            "/sell/inventory/v1/inventory_item",
            params={"limit": 1},
            headers=HEADERS,
        )
        ok = show("GET /sell/inventory/v1/inventory_item", resp)
        if not ok:
            print("\n   ❌ Token rejected. Regenerate it with the correct scopes.")
            _print_token_instructions()
            return False

        # Check seller registration
        resp2 = await c.get("/sell/account/v1/privilege", headers=HEADERS)
        show("GET /sell/account/v1/privilege", resp2)
        if resp2.is_success:
            priv = resp2.json()
            reg = priv.get("sellerRegistrationCompleted", False)
            print(f"\n   sellerRegistrationCompleted : {reg}")
            if not reg:
                print("\n   ❌ Seller registration is not complete.")
                if PRODUCTION:
                    print("      Go to https://www.ebay.com/sh/ovw and complete seller onboarding.")
                else:
                    print("      Go to https://www.sandbox.ebay.com and click Sell to register.")
                return False

    return True


async def get_or_create_policies() -> dict:
    section("STEP 1 — Listing policies")
    ids = {}

    def extract_duplicate_id(r, keys):
        for err in r.json().get("errors", []):
            params = {p["name"]: p["value"] for p in err.get("parameters", [])}
            for k in keys:
                if k in params:
                    return params[k]
        return None

    async with httpx.AsyncClient(base_url=BASE) as c:

        # Try to opt in to Business Policies first (no-op if already opted in)
        opt_in = await c.post(
            "/sell/account/v1/sales_tax",  # dummy call to trigger BP check
            headers=HEADERS,
            json={},
        )
        # The real opt-in endpoint
        opt_in2 = await c.post(
            "/sell/account/v1/program/opt_in",
            headers=HEADERS,
            json={"programType": "SELLING_POLICY_MANAGEMENT"},
        )
        if opt_in2.status_code in (200, 204):
            print("\n   ✅ Successfully opted in to Business Policies!")
        elif opt_in2.status_code == 409:
            print("\n   ✅ Already opted in to Business Policies.")
        else:
            print(f"\n   ℹ️  Opt-in attempt: {opt_in2.status_code} {opt_in2.text[:200]}")

        # Try GET first (works on production, broken on sandbox)
        resp = await c.get(
            "/sell/account/v1/fulfillment_policy",
            params={"marketplace_id": "EBAY_US"},
            headers=HEADERS,
        )
        if resp.is_success and resp.json().get("fulfillmentPolicies"):
            ids["fulfillmentPolicyId"] = resp.json()["fulfillmentPolicies"][0]["fulfillmentPolicyId"]
            print(f"\n   ✔ fulfillmentPolicyId : {ids['fulfillmentPolicyId']}")
        else:
            print("\n   → Creating fulfillment policy...")
            r = await c.post("/sell/account/v1/fulfillment_policy", headers=HEADERS, json={
                "name": "ernesto-fulfillment",
                "marketplaceId": "EBAY_US",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                "handlingTime": {"value": 3, "unit": "DAY"},
                "shipToLocations": {
                    "regionIncluded": [{"regionName": "Worldwide"}],
                },
                "shippingOptions": [{
                    "optionType": "DOMESTIC",
                    "costType": "FLAT_RATE",
                    "shippingServices": [{
                        "shippingServiceCode": "USPSFirstClass",
                        "shippingCost": {"value": "4.99", "currency": "USD"},
                        "freeShipping": False,
                        "buyerResponsibleForShipping": False,
                    }],
                }],
            })
            show("POST fulfillment_policy", r)
            if r.is_success:
                ids["fulfillmentPolicyId"] = r.json()["fulfillmentPolicyId"]
            else:
                pid = extract_duplicate_id(r, ["DuplicateProfileId", "Shipping Profile Id"])
                if pid:
                    ids["fulfillmentPolicyId"] = pid
                    print(f"   ✔ Already exists: fulfillmentPolicyId = {pid}")

        resp = await c.get(
            "/sell/account/v1/payment_policy",
            params={"marketplace_id": "EBAY_US"},
            headers=HEADERS,
        )
        if resp.is_success and resp.json().get("paymentPolicies"):
            ids["paymentPolicyId"] = resp.json()["paymentPolicies"][0]["paymentPolicyId"]
            print(f"   ✔ paymentPolicyId     : {ids['paymentPolicyId']}")
        else:
            print("\n   → Creating payment policy...")
            r = await c.post("/sell/account/v1/payment_policy", headers=HEADERS, json={
                "name": "ernesto-payment",
                "marketplaceId": "EBAY_US",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                "immediatePay": True,
            })
            show("POST payment_policy", r)
            if r.is_success:
                ids["paymentPolicyId"] = r.json()["paymentPolicyId"]
            else:
                pid = extract_duplicate_id(r, ["DuplicateProfileId", "Payment Profile Id"])
                if pid:
                    ids["paymentPolicyId"] = pid
                    print(f"   ✔ Already exists: paymentPolicyId = {pid}")

        resp = await c.get(
            "/sell/account/v1/return_policy",
            params={"marketplace_id": "EBAY_US"},
            headers=HEADERS,
        )
        if resp.is_success and resp.json().get("returnPolicies"):
            ids["returnPolicyId"] = resp.json()["returnPolicies"][0]["returnPolicyId"]
            print(f"   ✔ returnPolicyId      : {ids['returnPolicyId']}")
        else:
            print("\n   → Creating return policy...")
            r = await c.post("/sell/account/v1/return_policy", headers=HEADERS, json={
                "name": "ernesto-returns",
                "marketplaceId": "EBAY_US",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                "returnsAccepted": True,
                "returnPeriod": {"value": 30, "unit": "DAY"},
                "returnShippingCostPayer": "BUYER",
                "refundMethod": "MONEY_BACK",
            })
            show("POST return_policy", r)
            if r.is_success:
                ids["returnPolicyId"] = r.json()["returnPolicyId"]
            else:
                pid = extract_duplicate_id(r, ["DuplicateProfileId", "Return Profile Id"])
                if pid:
                    ids["returnPolicyId"] = pid
                    print(f"   ✔ Already exists: returnPolicyId = {pid}")

        # Patch fulfillment policy to add shipToLocations (required for publish)
        if "fulfillmentPolicyId" in ids:
            fid = ids["fulfillmentPolicyId"]
            print(f"\n   → Patching fulfillment policy {fid} with shipToLocations...")
            r = await c.put(f"/sell/account/v1/fulfillment_policy/{fid}", headers=HEADERS, json={
                "name": "ernesto-fulfillment",
                "marketplaceId": "EBAY_US",
                "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
                "handlingTime": {"value": 3, "unit": "DAY"},
                "globalShipping": False,
                "pickupDropOff": False,
                "freightShipping": False,
                "shipToLocations": {
                    "regionIncluded": [{"regionName": "Worldwide"}],
                },
                "shippingOptions": [{
                    "optionType": "DOMESTIC",
                    "costType": "FLAT_RATE",
                    "shippingServices": [{
                        "shippingServiceCode": "USPSFirstClass",
                        "shippingCost": {"value": "4.99", "currency": "USD"},
                        "freeShipping": False,
                        "buyerResponsibleForShipping": False,
                    }],
                }],
            })
            if r.is_success:
                print(f"   ✔ Fulfillment policy updated.")
            else:
                print(f"   ℹ️  Patch response: {r.status_code} {r.text[:300]}")

    print(f"\n   Policies : {ids}")
    return ids


async def create_inventory_item(sku: str) -> bool:
    section("STEP 2 — Create inventory item")
    payload = {
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "condition": "USED_EXCELLENT",
        "packageWeightAndSize": {
            "dimensions": {"height": 5, "length": 10, "width": 5, "unit": "INCH"},
            "packageType": "PACKAGE_THICK_ENVELOPE",
            "weight": {"value": 1, "unit": "POUND"},
        },
        "product": {
            "title": "Ernesto Test Item — DO NOT BUY (automated test)",
            "description": "This is an automated test listing created by Ernesto. It will be removed shortly.",
            "imageUrls": [
                "https://ir.ebaystatic.com/cr/v/c1/ebay-logo-1-1200x630-margin.png"
            ],
        },
    }
    async with httpx.AsyncClient(base_url=BASE) as c:
        resp = await c.put(
            f"/sell/inventory/v1/inventory_item/{sku}",
            json=payload,
            headers=HEADERS,
        )
        ok = show(f"PUT inventory_item/{sku}", resp)
    if ok:
        print(f"\n   ✔ SKU: {sku}")
    return ok


async def ensure_merchant_location() -> str | None:
    """Create a merchant location (ship-from address) if none exists. Returns locationKey."""
    section("STEP 2b — Merchant location (ship-from)")
    location_key = "ernesto-location-1"
    async with httpx.AsyncClient(base_url=BASE) as c:
        # Check if already exists
        resp = await c.get("/sell/inventory/v1/location", headers=HEADERS)
        if resp.is_success:
            locs = resp.json().get("locations", [])
            if locs:
                key = locs[0]["merchantLocationKey"]
                print(f"\n   ✔ Using existing location: {key}")
                return key

        # Create one
        print(f"\n   → Creating merchant location '{location_key}'...")
        r = await c.post(
            f"/sell/inventory/v1/location/{location_key}",
            headers=HEADERS,
            json={
                "location": {
                    "address": {
                        "addressLine1": "123 Main St",
                        "city": "San Jose",
                        "stateOrProvince": "CA",
                        "postalCode": "95125",
                        "country": "US",
                    }
                },
                "locationTypes": ["WAREHOUSE"],
                "name": "Ernesto Default Location",
                "merchantLocationStatus": "ENABLED",
            },
        )
        show(f"POST /sell/inventory/v1/location/{location_key}", r)
        if r.is_success or r.status_code == 204:
            print(f"   ✔ Location created: {location_key}")
            return location_key
        # Already exists
        if r.status_code == 409 or "already exists" in r.text.lower():
            print(f"   ✔ Location already exists: {location_key}")
            return location_key
    return None


async def create_offer(sku: str, policy_ids: dict, location_key: str | None = None) -> str | None:
    section("STEP 3 — Create offer")
    # Use $999.99 in production to prevent accidental purchase
    price = "999.99" if PRODUCTION else "9.99"
    payload = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "availableQuantity": 1,
        "categoryId": "29223",  # Everything Else > Wholesale Lots > Other — leaf, no required specifics
        "listingDescription": "This is an automated test listing created by Ernesto. It will be removed shortly.",
        "listingPolicies": {
            "fulfillmentPolicyId": policy_ids["fulfillmentPolicyId"],
            "paymentPolicyId": policy_ids["paymentPolicyId"],
            "returnPolicyId": policy_ids["returnPolicyId"],
        },
        "pricingSummary": {
            "price": {"value": price, "currency": "USD"}
        },
    }
    if location_key:
        payload["merchantLocationKey"] = location_key
    async with httpx.AsyncClient(base_url=BASE) as c:
        resp = await c.post("/sell/inventory/v1/offer", json=payload, headers=HEADERS)
        ok = show("POST /sell/inventory/v1/offer", resp)
    if ok:
        offer_id = resp.json().get("offerId")
        print(f"\n   ✔ offerId = {offer_id}  (price = ${price})")
        return offer_id
    return None


async def publish_offer(offer_id: str) -> str | None:
    section("STEP 4 — Publish offer")

    if PRODUCTION:
        print("\n   ⚠️  PRODUCTION MODE — this will create a REAL eBay listing!")
        print("      Price is set to $999.99 to prevent accidental sales.")
        confirm = input("      Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            print("   Aborted.")
            return None

    async with httpx.AsyncClient(base_url=BASE) as c:
        resp = await c.post(
            f"/sell/inventory/v1/offer/{offer_id}/publish",
            headers=HEADERS,
        )
        ok = show(f"POST offer/{offer_id}/publish", resp)
    if ok:
        listing_id = resp.json().get("listingId")
        domain = "ebay.com" if PRODUCTION else "sandbox.ebay.com"
        print(f"\n   ✔ listingId = {listing_id}")
        print(f"   🔗 https://www.{domain}/itm/{listing_id}")
        return listing_id
    return None


async def verify_listing(listing_id: str):
    section("STEP 5 — Verify listing via Browse API")
    async with httpx.AsyncClient(base_url=BASE) as c:
        resp = await c.get(
            f"/buy/browse/v1/item/v1|{listing_id}|0",
            headers=HEADERS,
        )
        ok = show(f"GET item/v1|{listing_id}|0", resp)
    if ok:
        data = resp.json()
        print(f"\n   ✔ Title : {data.get('title')}")
        print(f"   ✔ Price : {data.get('price', {}).get('value')} {data.get('price', {}).get('currency')}")
        print(f"   ✔ URL   : {data.get('itemWebUrl')}")
    else:
        print("\n   ℹ️  Browse API sometimes lags — the listing may still be live.")
        domain = "ebay.com" if PRODUCTION else "sandbox.ebay.com"
        print(f"      Check manually: https://www.{domain}/itm/{listing_id}")


async def end_listing(offer_id: str):
    section("CLEANUP — End / delete listing")
    async with httpx.AsyncClient(base_url=BASE) as c:
        resp = await c.delete(
            f"/sell/inventory/v1/offer/{offer_id}",
            headers=HEADERS,
        )
        show(f"DELETE offer/{offer_id}", resp)


async def cleanup(sku: str, offer_id: str | None):
    section("CLEANUP — Delete inventory item")
    async with httpx.AsyncClient(base_url=BASE) as c:
        if offer_id:
            r = await c.delete(f"/sell/inventory/v1/offer/{offer_id}", headers=HEADERS)
            show(f"DELETE offer/{offer_id}", r)
        r = await c.delete(f"/sell/inventory/v1/inventory_item/{sku}", headers=HEADERS)
        show(f"DELETE inventory_item/{sku}", r)


def _print_token_instructions():
    env = "production" if PRODUCTION else "sandbox"
    url = "https://developer.ebay.com/my/auth/?env=production&index=0" if PRODUCTION \
        else "https://developer.ebay.com/my/auth/?env=sandbox&index=0"
    print(f"\n   Generate a new OAuth token at:")
    print(f"   {url}")
    print(f"\n   Required scopes:")
    print(f"     • sell.inventory")
    print(f"     • sell.account")
    print(f"     • sell.negotiation")
    print(f"     • sell.fulfillment")
    key = "EBAY_PROD_USER_TOKEN" if PRODUCTION else "EBAY_USER_TOKEN"
    print(f"\n   Paste the token into backend/.env as {key}=...")


# ── main ──────────────────────────────────────────────────────────────────────

async def main():
    mode = "🔴 PRODUCTION" if PRODUCTION else "🟡 SANDBOX"
    print(f"\n🔍 Ernesto — eBay Diagnostic  [{mode}]")

    if not TOKEN:
        key = "EBAY_PROD_USER_TOKEN" if PRODUCTION else "EBAY_USER_TOKEN"
        print(f"\n❌ {key} is not set in backend/.env")
        _print_token_instructions()
        return

    # Step 0: token + seller registration
    if not await check_token():
        return

    sku = f"ernesto-test-{int(datetime.utcnow().timestamp())}"
    offer_id = None

    # Step 1: policies
    policy_ids = await get_or_create_policies()
    if len(policy_ids) < 3:
        missing = [k for k in ("fulfillmentPolicyId", "paymentPolicyId", "returnPolicyId")
                   if k not in policy_ids]
        print(f"\n❌ Missing policies: {missing}")
        if PRODUCTION:
            print("   Go to https://www.ebay.com/sh/settings/policies to create them.")
        else:
            print("   Complete seller registration at https://www.sandbox.ebay.com first.")
        return

    # Step 2: inventory item
    if not await create_inventory_item(sku):
        print("\n❌ Aborting at step 2.")
        return

    # Step 2b: merchant location
    location_key = await ensure_merchant_location()

    # Step 3: offer
    offer_id = await create_offer(sku, policy_ids, location_key)
    if not offer_id:
        print("\n❌ Aborting at step 3.")
        await cleanup(sku, None)
        return

    # Step 4: publish
    listing_id = await publish_offer(offer_id)
    if not listing_id:
        print("\n❌ Aborting at step 4.")
        await cleanup(sku, offer_id)
        return

    # Step 5: verify
    await verify_listing(listing_id)

    # Save policy IDs for use in .env
    section("RESULT — Save these to backend/.env")
    print(f"\n   EBAY_FULFILLMENT_POLICY_ID={policy_ids['fulfillmentPolicyId']}")
    print(f"   EBAY_PAYMENT_POLICY_ID={policy_ids['paymentPolicyId']}")
    print(f"   EBAY_RETURN_POLICY_ID={policy_ids['returnPolicyId']}")
    print(f"   EBAY_LISTING_ID (test)={listing_id}")

    print("\n" + "=" * 60)
    keep = input("\nKeep the test listing? [y/N] ").strip().lower()
    if keep != "y":
        await cleanup(sku, offer_id)
    else:
        print(f"   Kept. SKU={sku}  offerId={offer_id}  listingId={listing_id}")

    print("\n✅ Diagnostic complete.\n")


if __name__ == "__main__":
    asyncio.run(main())
