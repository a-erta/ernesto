#!/usr/bin/env python3
"""
List eBay fulfillment, payment, and return policy IDs for a marketplace.
Optional admin helper; the app now fetches policies automatically from the connected user's account.

Requires EBAY_PROD_USER_TOKEN (or EBAY_USER_TOKEN for --sandbox) in .env.
Run from repo root:  python backend/scripts/list_ebay_policies.py  [--marketplace EBAY_IT] [--sandbox]
"""
import argparse
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import asyncio
import httpx
from backend.config import settings

BASE = "https://api.ebay.com"
SANDBOX_BASE = "https://api.sandbox.ebay.com"
CONTENT_LANGUAGE = {"EBAY_US": "en-US", "EBAY_IT": "it-IT", "EBAY_DE": "de-DE", "EBAY_FR": "fr-FR", "EBAY_ES": "es-ES", "EBAY_GB": "en-GB"}


def main() -> None:
    parser = argparse.ArgumentParser(description="List eBay policy IDs for a marketplace")
    parser.add_argument("--marketplace", default=None, help="Default: EBAY_MARKETPLACE_ID from env")
    parser.add_argument("--sandbox", action="store_true")
    args = parser.parse_args()

    marketplace_id = (args.marketplace or settings.EBAY_MARKETPLACE_ID or "EBAY_US").strip()
    token = (settings.EBAY_USER_TOKEN if args.sandbox else settings.EBAY_PROD_USER_TOKEN or "").strip()
    if not token:
        print("Set EBAY_PROD_USER_TOKEN (or EBAY_USER_TOKEN for --sandbox) in .env.", file=sys.stderr)
        sys.exit(1)

    base_url = SANDBOX_BASE if args.sandbox else BASE
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Language": CONTENT_LANGUAGE.get(marketplace_id, "en-US"),
    }

    print(f"Marketplace: {marketplace_id}\n")

    async def run() -> None:
        async with httpx.AsyncClient(base_url=base_url, headers=headers) as client:
            for label, path, key in (
                ("Fulfillment", "/sell/account/v1/fulfillment_policy", "fulfillmentPolicies"),
                ("Payment", "/sell/account/v1/payment_policy", "paymentPolicies"),
                ("Return", "/sell/account/v1/return_policy", "returnPolicies"),
            ):
                r = await client.get(path, params={"marketplace_id": marketplace_id})
                if r.status_code != 200:
                    print(f"{label}: HTTP {r.status_code} - {r.text[:200]}")
                else:
                    policies = (r.json() or {}).get(key, [])
                    id_key = path.split("/")[-1].replace("_policy", "PolicyId")
                    if "fulfillment" in path:
                        id_key = "fulfillmentPolicyId"
                    elif "payment" in path:
                        id_key = "paymentPolicyId"
                    else:
                        id_key = "returnPolicyId"
                    print(f"{label}:")
                    for p in policies:
                        print(f"  {p.get(id_key)}  {p.get('name', '')}")
                    if not policies:
                        print("  (none)")
                    print()

    asyncio.run(run())


if __name__ == "__main__":
    main()
