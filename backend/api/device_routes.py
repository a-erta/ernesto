"""
Device registration for push notifications (iOS / Android).
"""
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..auth import get_current_user, AuthUser
from ..models.db import get_db, DBDevice

log = structlog.get_logger()
device_router = APIRouter(prefix="/api/devices")


class DeviceRegister(BaseModel):
    device_token: str
    platform: str  # 'ios' | 'android'


@device_router.post("")
async def register_device(
    body: DeviceRegister,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBDevice).where(DBDevice.device_token == body.device_token)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.user_id = current_user.user_id
        existing.platform = body.platform
    else:
        db.add(DBDevice(
            user_id=current_user.user_id,
            device_token=body.device_token,
            platform=body.platform,
        ))
    await db.commit()
    log.info("device.registered", user_id=current_user.user_id, platform=body.platform)
    return {"ok": True}


@device_router.delete("/{device_token}")
async def unregister_device(
    device_token: str,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DBDevice).where(
            DBDevice.device_token == device_token,
            DBDevice.user_id == current_user.user_id,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await db.delete(device)
    await db.commit()
    return {"ok": True}
