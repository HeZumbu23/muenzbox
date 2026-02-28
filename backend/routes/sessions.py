from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException

import json

import aiosqlite
from database import get_db
from auth import get_current_child
from models import SessionStart, SessionResponse
import adapters
from adapters import nintendo
from time_utils import is_in_periods, get_active_periods

router = APIRouter()

COIN_MINUTES = 30
_FALLBACK = '[{"von":"08:00","bis":"20:00"}]'


async def _get_tv_device(db: aiosqlite.Connection) -> dict:
    async with db.execute(
        "SELECT identifier, control_type FROM devices WHERE device_type='tv' AND is_active=1 LIMIT 1"
    ) as cur:
        row = await cur.fetchone()
    if row:
        return {"identifier": row["identifier"] or "Fernseher", "control_type": row["control_type"] or "fritzbox"}
    return {"identifier": "Fernseher", "control_type": "fritzbox"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/sessions", response_model=SessionResponse)
async def start_session(
    body: SessionStart,
    current: dict = Depends(get_current_child),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Start a new session for Switch or TV."""
    if current["sub"] != str(body.child_id):
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    if body.type not in ("switch", "tv"):
        raise HTTPException(status_code=400, detail="Ungültiger Typ (switch oder tv)")

    if body.coins < 1:
        raise HTTPException(status_code=400, detail="Mindestens 1 Münze erforderlich")

    if body.type == "switch" and body.coins > 2:
        raise HTTPException(status_code=400, detail="Switch: maximal 2 Münzen (60 Min) pro Session")

    # Load child data
    async with db.execute("SELECT * FROM children WHERE id=?", (body.child_id,)) as cur:
        child = await cur.fetchone()
    if not child:
        raise HTTPException(status_code=404, detail="Kind nicht gefunden")

    # Check time window
    allowed = json.loads(child["allowed_periods"] or _FALLBACK)
    weekend = json.loads(child["weekend_periods"] or _FALLBACK)
    active = get_active_periods(allowed, weekend)
    if not is_in_periods(active):
        times_str = ", ".join(f"{p['von']}–{p['bis']} Uhr" for p in active)
        raise HTTPException(
            status_code=403,
            detail=f"Außerhalb der erlaubten Zeit ({times_str})",
        )

    # Check coin balance
    coin_field = f"{body.type}_coins"
    available = child[coin_field]
    if available < body.coins:
        raise HTTPException(
            status_code=400,
            detail=f"Nicht genug Münzen (verfügbar: {available})",
        )

    # Check for existing active session
    async with db.execute(
        "SELECT id FROM sessions WHERE child_id=? AND status='active'",
        (body.child_id,),
    ) as cur:
        existing = await cur.fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Es läuft bereits eine Session")

    # Deduct coins
    now = _now_iso()
    ends_at = (
        datetime.now(timezone.utc) + timedelta(minutes=body.coins * COIN_MINUTES)
    ).isoformat()

    await db.execute(
        f"UPDATE children SET {coin_field}={coin_field}-? WHERE id=?",
        (body.coins, body.child_id),
    )

    # Log coin deduction
    await db.execute(
        "INSERT INTO coin_log (child_id, type, delta, reason, created_at) VALUES (?,?,?,?,?)",
        (body.child_id, body.type, -body.coins, "session", now),
    )

    # Create session record
    async with db.execute(
        "INSERT INTO sessions (child_id, type, started_at, ends_at, coins_used, status) VALUES (?,?,?,?,?,?)",
        (body.child_id, body.type, now, ends_at, body.coins, "active"),
    ) as cur:
        session_id = cur.lastrowid

    await db.commit()

    # Enable hardware
    ok = False
    if body.type == "tv":
        dev = await _get_tv_device(db)
        ok = await adapters.tv_freigeben(dev["control_type"], dev["identifier"])
    elif body.type == "switch":
        ok = await nintendo.switch_freigeben(minutes=body.coins * COIN_MINUTES)

    if not ok:
        import logging
        logging.getLogger(__name__).warning(
            "Hardware-Freigabe fehlgeschlagen für Session %d", session_id
        )

    return {
        "id": session_id,
        "child_id": body.child_id,
        "type": body.type,
        "started_at": now,
        "ends_at": ends_at,
        "coins_used": body.coins,
        "status": "active",
        "hardware_ok": ok,
    }


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: int,
    current: dict = Depends(get_current_child),
    db: aiosqlite.Connection = Depends(get_db),
):
    """End a session early (child-initiated)."""
    async with db.execute(
        "SELECT * FROM sessions WHERE id=? AND status='active'", (session_id,)
    ) as cur:
        session = await cur.fetchone()

    if not session:
        raise HTTPException(status_code=404, detail="Aktive Session nicht gefunden")

    if str(session["child_id"]) != current["sub"]:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    await db.execute(
        "UPDATE sessions SET status='completed' WHERE id=?", (session_id,)
    )
    await db.commit()

    # Disable hardware
    if session["type"] == "tv":
        dev = await _get_tv_device(db)
        await adapters.tv_sperren(dev["control_type"], dev["identifier"])
    elif session["type"] == "switch":
        await nintendo.switch_sperren()

    return {"status": "completed"}
