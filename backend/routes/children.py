import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import aiosqlite
from database import get_db, DATABASE_PATH
from auth import hash_pin, verify_pin, create_token, get_current_child
from models import ChildAvatarUpdate, ChildPublic, ChildStatus, PinVerify
from time_utils import is_weekend_or_holiday

_FALLBACK = '[{"von":"08:00","bis":"20:00"}]'

router = APIRouter()


@router.get("/children", response_model=list[ChildPublic])
async def list_children(db: aiosqlite.Connection = Depends(get_db)):
    """List all children (id + name only) for the selection screen."""
    async with db.execute(
        "SELECT id, name, avatar, switch_coins, tv_coins FROM children ORDER BY name"
    ) as cursor:
        rows = await cursor.fetchall()
    return [
        {"id": r["id"], "name": r["name"], "avatar": r["avatar"] or "🦁", "switch_coins": r["switch_coins"], "tv_coins": r["tv_coins"]}
        for r in rows
    ]


@router.post("/children/{child_id}/verify-pin")
async def verify_child_pin(
    child_id: int,
    body: PinVerify,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Verify child PIN and return a session token."""
    async with db.execute(
        "SELECT id, name, pin_hash FROM children WHERE id=?", (child_id,)
    ) as cursor:
        child = await cursor.fetchone()

    if not child:
        raise HTTPException(status_code=404, detail="Kind nicht gefunden")

    if not verify_pin(body.pin, child["pin_hash"]):
        raise HTTPException(status_code=401, detail="Falsche PIN")

    token = create_token({"sub": str(child_id), "role": "child", "name": child["name"]})
    return {"token": token, "child_id": child_id, "name": child["name"]}


@router.get("/children/{child_id}/status", response_model=ChildStatus)
async def get_child_status(
    child_id: int,
    current: dict = Depends(get_current_child),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get full coin status for a child (requires child token)."""
    if current["sub"] != str(child_id):
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    async with db.execute(
        "SELECT * FROM children WHERE id=?", (child_id,)
    ) as cursor:
        child = await cursor.fetchone()

    if not child:
        raise HTTPException(status_code=404, detail="Kind nicht gefunden")

    child_dict = dict(child)
    child_dict["allowed_periods"] = json.loads(child_dict.get("allowed_periods") or _FALLBACK)
    child_dict["weekend_periods"] = json.loads(child_dict.get("weekend_periods") or _FALLBACK)
    child_dict["avatar"] = child_dict.get("avatar") or "🦁"
    child_dict["is_weekend_or_holiday"] = is_weekend_or_holiday()
    return child_dict


@router.get("/children/{child_id}/active-session")
async def get_active_session(
    child_id: int,
    current: dict = Depends(get_current_child),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get the currently active session for a child, if any."""
    if current["sub"] != str(child_id):
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    async with db.execute(
        "SELECT * FROM sessions WHERE child_id=? AND status='active' ORDER BY started_at DESC LIMIT 1",
        (child_id,),
    ) as cursor:
        session = await cursor.fetchone()

    if not session:
        return None
    return dict(session)


@router.patch("/children/{child_id}/avatar")
async def update_child_avatar(
    child_id: int,
    body: ChildAvatarUpdate,
    current: dict = Depends(get_current_child),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Update avatar for the currently authenticated child."""
    if current["sub"] != str(child_id):
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    async with db.execute("SELECT id FROM children WHERE id=?", (child_id,)) as cursor:
        child = await cursor.fetchone()

    if not child:
        raise HTTPException(status_code=404, detail="Kind nicht gefunden")

    await db.execute("UPDATE children SET avatar=? WHERE id=?", (body.avatar, child_id))
    await db.commit()
    return {"ok": True, "avatar": body.avatar}
