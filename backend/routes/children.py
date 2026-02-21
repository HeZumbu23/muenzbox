from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import aiosqlite
from database import get_db, DATABASE_PATH
from auth import hash_pin, verify_pin, create_token, get_current_child
from models import ChildPublic, ChildStatus, PinVerify

router = APIRouter()


@router.get("/children", response_model=list[ChildPublic])
async def list_children(db: aiosqlite.Connection = Depends(get_db)):
    """List all children (id + name only) for the selection screen."""
    async with db.execute("SELECT id, name FROM children ORDER BY name") as cursor:
        rows = await cursor.fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


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

    token = create_token({"sub": child_id, "role": "child", "name": child["name"]})
    return {"token": token, "child_id": child_id, "name": child["name"]}


@router.get("/children/{child_id}/status", response_model=ChildStatus)
async def get_child_status(
    child_id: int,
    current: dict = Depends(get_current_child),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get full coin status for a child (requires child token)."""
    if current["sub"] != child_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    async with db.execute(
        "SELECT * FROM children WHERE id=?", (child_id,)
    ) as cursor:
        child = await cursor.fetchone()

    if not child:
        raise HTTPException(status_code=404, detail="Kind nicht gefunden")

    return dict(child)


@router.get("/children/{child_id}/active-session")
async def get_active_session(
    child_id: int,
    current: dict = Depends(get_current_child),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get the currently active session for a child, if any."""
    if current["sub"] != child_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    async with db.execute(
        "SELECT * FROM sessions WHERE child_id=? AND status='active' ORDER BY started_at DESC LIMIT 1",
        (child_id,),
    ) as cursor:
        session = await cursor.fetchone()

    if not session:
        return None
    return dict(session)
