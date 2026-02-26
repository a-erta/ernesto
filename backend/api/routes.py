"""
REST API routes for Ernesto.
"""
import json
import uuid
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from ..models.db import (
    get_db, DBItem, DBListing, DBOffer, DBMessage, DBComparable, DBUser,
    ItemStatusEnum, ListingStatusEnum, OfferStatusEnum,
)
from ..models.schemas import Item, Listing, Offer, Message, OfferDecision
from ..graph.workflow import build_graph
from ..auth import get_current_user, AuthUser
from ..storage import upload_image, get_image_url
from ..config import settings
from .websocket import manager

log = structlog.get_logger()
router = APIRouter(prefix="/api")

CHECKPOINT_DB = "./ernesto_checkpoints.db"


def _get_checkpointer():
    """Return the appropriate LangGraph checkpointer based on DATABASE_URL."""
    if settings.use_postgres:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # type: ignore
        return AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    return AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB)


async def _ensure_user(user: AuthUser, db: AsyncSession):
    """Upsert the authenticated user into the users table."""
    existing = await db.get(DBUser, user.user_id)
    if not existing:
        db.add(DBUser(id=user.user_id, email=user.email))
        await db.commit()


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@router.get("/items", response_model=list[Item])
async def list_items(
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBItem)
        .options(selectinload(DBItem.listings), selectinload(DBItem.comparables))
        .where(DBItem.user_id == current_user.user_id)
        .order_by(desc(DBItem.created_at))
    )
    items = result.scalars().all()
    return items


@router.get("/items/{item_id}", response_model=Item)
async def get_item(
    item_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBItem)
        .options(selectinload(DBItem.listings), selectinload(DBItem.comparables))
        .where(DBItem.id == item_id, DBItem.user_id == current_user.user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/items", response_model=Item)
async def create_item(
    background_tasks: BackgroundTasks,
    description: Optional[str] = Form(None),
    platforms: str = Form("ebay"),
    images: list[UploadFile] = File(default=[]),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new item and kick off the agent pipeline."""
    await _ensure_user(current_user, db)

    image_keys: list[str] = []
    for image in images:
        key = await upload_image(image, current_user.user_id)
        image_keys.append(key)

    db_item = DBItem(
        user_id=current_user.user_id,
        user_description=description,
        image_paths=json.dumps(image_keys),
        status=ItemStatusEnum.analyzing,
    )
    db.add(db_item)
    await db.commit()

    result = await db.execute(
        select(DBItem)
        .options(selectinload(DBItem.listings), selectinload(DBItem.comparables))
        .where(DBItem.id == db_item.id)
    )
    db_item = result.scalar_one()

    background_tasks.add_task(
        run_agent_pipeline,
        item_id=db_item.id,
        image_keys=image_keys,
        user_description=description or "",
        platforms=platforms.split(","),
        user_id=current_user.user_id,
    )

    return db_item


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBItem).where(DBItem.id == item_id, DBItem.user_id == current_user.user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Human-in-the-loop: approve listing
# ---------------------------------------------------------------------------

@router.post("/items/{item_id}/approve")
async def approve_listing(
    item_id: int,
    final_price: float,
    background_tasks: BackgroundTasks,
    description: Optional[str] = None,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBItem).where(DBItem.id == item_id, DBItem.user_id == current_user.user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.final_price = final_price
    item.status = ItemStatusEnum.publishing
    # Persist the user-edited description (overrides AI proposal if provided)
    if description is not None:
        item.proposed_description = description
    await db.commit()

    background_tasks.add_task(
        resume_agent,
        item_id=item_id,
        user_id=current_user.user_id,
        human_input={
            "action": "approve",
            "final_price": final_price,
            "description": description or item.proposed_description,
        },
    )
    return {"ok": True}


@router.post("/items/{item_id}/cancel")
async def cancel_item(
    item_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBItem).where(DBItem.id == item_id, DBItem.user_id == current_user.user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.status = ItemStatusEnum.archived
    await db.commit()
    await resume_agent(item_id=item_id, user_id=current_user.user_id, human_input={"action": "cancel"})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Offers
# ---------------------------------------------------------------------------

@router.get("/items/{item_id}/offers", response_model=list[Offer])
async def get_offers(
    item_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBOffer)
        .join(DBListing)
        .join(DBItem)
        .where(DBListing.item_id == item_id, DBItem.user_id == current_user.user_id)
        .order_by(desc(DBOffer.received_at))
    )
    return result.scalars().all()


@router.post("/offers/{offer_id}/decide")
async def decide_offer(
    offer_id: int,
    decision: OfferDecision,
    background_tasks: BackgroundTasks,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offer = await db.get(DBOffer, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    listing = await db.get(DBListing, offer.listing_id)
    item_id = listing.item_id

    # Verify ownership
    result = await db.execute(
        select(DBItem).where(DBItem.id == item_id, DBItem.user_id == current_user.user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not your item")

    if decision.action == "accept":
        offer.status = OfferStatusEnum.accepted
        offer.resolved_at = datetime.now(timezone.utc)
    elif decision.action == "decline":
        offer.status = OfferStatusEnum.declined
        offer.resolved_at = datetime.now(timezone.utc)
    elif decision.action == "counter":
        offer.status = OfferStatusEnum.countered
        offer.counter_amount = decision.counter_amount
    await db.commit()

    background_tasks.add_task(
        resume_agent,
        item_id=item_id,
        user_id=current_user.user_id,
        human_input={
            "action": decision.action,
            "offer_id": offer_id,
            "counter_amount": decision.counter_amount,
        },
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@router.get("/items/{item_id}/messages", response_model=list[Message])
async def get_messages(
    item_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBMessage)
        .join(DBListing)
        .join(DBItem)
        .where(DBListing.item_id == item_id, DBItem.user_id == current_user.user_id)
        .order_by(DBMessage.received_at)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------

@router.get("/items/{item_id}/listings", response_model=list[Listing])
async def get_listings(
    item_id: int,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBListing)
        .join(DBItem)
        .where(DBListing.item_id == item_id, DBItem.user_id == current_user.user_id)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Agent pipeline helpers
# ---------------------------------------------------------------------------

async def run_agent_pipeline(
    item_id: int,
    image_keys: list[str],
    user_description: str,
    platforms: list[str],
    user_id: str,
):
    """Run the full LangGraph pipeline for a new item."""
    thread_id = f"{user_id}:{item_id}"
    # Resolve storage keys to local paths or URLs for the intake agent
    image_paths = [_resolve_image_path(k) for k in image_keys]
    initial_state = {
        "item_id": item_id,
        "user_id": user_id,
        "step": "intake",
        "image_paths": image_paths,
        "user_description": user_description,
        "platforms": platforms,
        "errors": [],
    }

    log.info("pipeline.start", item_id=item_id, platforms=platforms)
    await manager.broadcast(str(item_id), {"type": "step", "step": "intake", "item_id": item_id})

    try:
        async with _get_checkpointer() as saver:
            graph = build_graph().compile(
                checkpointer=saver,
                interrupt_before=["awaiting_approval", "awaiting_offer_decision"],
            )
            config = {"configurable": {"thread_id": thread_id}}

            async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
                if not isinstance(event, dict):
                    # LangGraph emits interrupt signals as tuples — skip them
                    log.info("graph.interrupt", item_id=item_id)
                    continue
                for node_name, state_snapshot in event.items():
                    if node_name == "__interrupt__":
                        log.info("graph.awaiting_human", item_id=item_id)
                        continue
                    if not isinstance(state_snapshot, dict):
                        continue
                    log.info("graph.event", node=node_name, item_id=item_id)

                    await manager.broadcast(str(item_id), {
                        "type": "step",
                        "step": node_name,
                        "item_id": item_id,
                        "data": _safe_state(state_snapshot),
                    })

                    await _sync_state_to_db(item_id, node_name, state_snapshot)

        log.info("pipeline.complete", item_id=item_id)

    except Exception as e:
        log.error("pipeline.error", item_id=item_id, error=str(e), exc_info=True)
        # Mark item as errored in DB so UI reflects it
        from ..models.db import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            item = await db.get(DBItem, item_id)
            if item:
                item.status = ItemStatusEnum.archived
                item.ai_analysis = json.dumps({"error": str(e)})
                await db.commit()
        await manager.broadcast(str(item_id), {
            "type": "error",
            "item_id": item_id,
            "error": str(e),
        })


async def resume_agent(item_id: int, user_id: str, human_input: dict):
    """Resume a paused graph after human input."""
    thread_id = f"{user_id}:{item_id}"
    log.info("pipeline.resume", item_id=item_id, action=human_input.get("action"))

    try:
        async with _get_checkpointer() as saver:
            graph = build_graph().compile(
                checkpointer=saver,
                interrupt_before=["awaiting_approval", "awaiting_offer_decision"],
            )
            config = {"configurable": {"thread_id": thread_id}}

            current = await graph.aget_state(config)
            updated_state = {**current.values, "human_input": human_input, "awaiting_human": False}
            await graph.aupdate_state(config, updated_state)

            await manager.broadcast(str(item_id), {"type": "resumed", "item_id": item_id, "input": human_input})

            async for event in graph.astream(None, config=config, stream_mode="updates"):
                if not isinstance(event, dict):
                    log.info("graph.interrupt", item_id=item_id)
                    continue
                for node_name, state_snapshot in event.items():
                    if node_name == "__interrupt__" or not isinstance(state_snapshot, dict):
                        continue
                    log.info("graph.event", node=node_name, item_id=item_id)
                    await manager.broadcast(str(item_id), {
                        "type": "step",
                        "step": node_name,
                        "item_id": item_id,
                        "data": _safe_state(state_snapshot),
                    })
                    await _sync_state_to_db(item_id, node_name, state_snapshot)

    except Exception as e:
        log.error("resume.error", item_id=item_id, error=str(e), exc_info=True)
        await manager.broadcast(str(item_id), {"type": "error", "item_id": item_id, "error": str(e)})


async def _sync_state_to_db(item_id: int, node_name: str, state: dict):
    """Persist relevant agent state back to the SQLite application DB."""
    from ..models.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        item = await db.get(DBItem, item_id)
        if not item:
            return

        if node_name == "listing" and state.get("item_data"):
            d = state["item_data"]
            item.title = d.get("title")
            item.category = d.get("category")
            item.brand = d.get("brand")
            item.model = d.get("model")
            item.condition = d.get("condition")
            item.color = d.get("color")
            item.size = d.get("size")
            item.ai_analysis = json.dumps(d)
            item.suggested_price = state.get("suggested_price")
            item.proposed_description = state.get("proposed_description") or ""
            item.status = ItemStatusEnum.ready

            # Save comparables
            for comp in state.get("comparables", []):
                db.add(DBComparable(
                    item_id=item_id,
                    platform=comp.get("platform", "unknown"),
                    title=comp.get("title", ""),
                    sold_price=comp.get("sold_price", 0),
                    url=comp.get("url"),
                    condition=comp.get("condition"),
                ))

        elif node_name == "publisher":
            item.status = ItemStatusEnum.listed
            for pub in state.get("published_listings", []):
                db.add(DBListing(
                    item_id=item_id,
                    platform=pub["platform"],
                    platform_listing_id=pub["platform_listing_id"],
                    platform_url=pub["platform_url"],
                    title=pub["title"],
                    price=pub["price"],
                    status=ListingStatusEnum.published,
                    published_at=datetime.now(timezone.utc),
                ))

        elif node_name == "deal_manager":
            # Save new messages
            result = await db.execute(select(DBListing).where(DBListing.item_id == item_id))
            listings = {l.platform_listing_id: l.id for l in result.scalars().all()}

            for msg in state.get("new_messages", []):
                listing_id = listings.get(msg.get("platform_listing_id"))
                if listing_id:
                    db.add(DBMessage(
                        listing_id=listing_id,
                        platform_message_id=msg.get("platform_message_id"),
                        buyer_username=msg.get("buyer_username"),
                        content=msg.get("content", ""),
                        direction="inbound",
                        auto_replied=True,
                    ))

            # Save pending offers
            for offer_data in state.get("pending_offers", []):
                listing_id = listings.get(offer_data.get("platform_listing_id"))
                if listing_id:
                    db.add(DBOffer(
                        listing_id=listing_id,
                        platform_offer_id=offer_data.get("platform_offer_id"),
                        buyer_username=offer_data.get("buyer_username"),
                        amount=offer_data.get("amount", 0),
                        status=OfferStatusEnum.pending,
                        notes=json.dumps(offer_data.get("ai_recommendation", {})),
                    ))

        elif node_name == "sold":
            item.status = ItemStatusEnum.sold

        await db.commit()


def _safe_state(state: object) -> dict:
    """Strip non-serialisable fields before broadcasting."""
    if not isinstance(state, dict):
        return {}
    safe = {}
    for k, v in state.items():
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            safe[k] = str(v)
    return safe


def _resolve_image_path(key: str) -> str:
    """
    For local dev: key is already a filesystem path, return as-is.
    For S3: key is an S3 object key — the intake agent needs a local temp file
    or a signed URL. For now we return the key and let the intake agent handle it.
    In a full S3 implementation you'd download to a temp file here.
    """
    return key
