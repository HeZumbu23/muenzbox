from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException

import aiosqlite
from database import get_db
from auth import get_current_child
from models import SessionStart, SessionResponse
from adapters import mikrotik_direct, nintendo

router = APIRouter()

COIN_MINUTES = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(t: str) -> tuple[int, int]:
    h, m = t.split(":")
    return int(h), int(m)


def _is_in_time_window(allowed_from: str, allowed_until: str) -> bool:
    now = datetime.now()
    fh, fm = _parse_time(allowed_from)
    uh, um = _parse_time(allowed_until)
    from_minutes = fh * 60 + fm
    until_minutes = uh * 60 + um
    current_minutes = now.hour * 60 + now.minute
    return from_minutes <= current_minutes <= until_minutes


@router.post("/sessions", response_model=SessionResponse)
async def start_session(
    body: SessionStart,
    current: dict = Depends(get_current_child),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Start a new session for Switch or TV."""
    if current["sub"] != body.child_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    if body.type not in ("switch", "tv"):
        raise HTTPException(status_code=400, detail="Ungültiger Typ (switch oder tv)")

    if body.coins < 1:
        raise HTTPException(status_code=400, detail="Mindestens 1 Münze erforderlich")

    # Load child data
    async with db.execute("SELECT * FROM children WHERE id=?", (body.child_id,)) as cur:
        child = await cur.fetchone()
    if not child:
        raise HTTPException(status_code=404, detail="Kind nicht gefunden")

    # Check time window
    if not _is_in_time_window(child["allowed_from"], child["allowed_until"]):
        raise HTTPException(
            status_code=403,
            detail=f"Außerhalb der erlaubten Zeit ({child['allowed_from']} – {child['allowed_until']})",
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
        ok = await mikrotik_direct.tv_freigeben()
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

    if session["child_id"] != current["sub"]:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    await db.execute(
        "UPDATE sessions SET status='completed' WHERE id=?", (session_id,)
    )
    await db.commit()

    # Disable hardware
    if session["type"] == "tv":
        await mikrotik_direct.tv_sperren()
    elif session["type"] == "switch":
        await nintendo.switch_sperren()

    return {"status": "completed"}
