import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

import aiosqlite
from database import get_db
from auth import hash_pin, verify_pin, create_token, get_current_admin
from models import AdminVerify, ChildCreate, ChildUpdate, CoinAdjust
from adapters import mikrotik_direct, nintendo

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"

router = APIRouter()

ADMIN_PIN_HASH = os.getenv("ADMIN_PIN_HASH", "")


@router.post("/verify")
async def admin_verify(body: AdminVerify):
    """Verify admin PIN and return admin token."""
    if not ADMIN_PIN_HASH:
        raise HTTPException(status_code=503, detail="Admin-PIN nicht konfiguriert")
    if not verify_pin(body.pin, ADMIN_PIN_HASH):
        raise HTTPException(status_code=401, detail="Falsche Admin-PIN")
    token = create_token({"sub": "admin", "role": "admin"}, expires_hours=12)
    return {"token": token}


# --- Children management ---

@router.get("/children")
async def admin_list_children(
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT * FROM children ORDER BY name") as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/children", status_code=201)
async def admin_create_child(
    body: ChildCreate,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    pin_hash = hash_pin(body.pin)
    async with db.execute(
        """INSERT INTO children
           (name, pin_hash, switch_coins, switch_coins_weekly, switch_coins_max,
            tv_coins, tv_coins_weekly, tv_coins_max, allowed_from, allowed_until)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            body.name, pin_hash,
            body.switch_coins, body.switch_coins_weekly, body.switch_coins_max,
            body.tv_coins, body.tv_coins_weekly, body.tv_coins_max,
            body.allowed_from, body.allowed_until,
        ),
    ) as cur:
        child_id = cur.lastrowid
    await db.commit()
    return {"id": child_id, "name": body.name}


@router.put("/children/{child_id}")
async def admin_update_child(
    child_id: int,
    body: ChildUpdate,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT * FROM children WHERE id=?", (child_id,)) as cur:
        child = await cur.fetchone()
    if not child:
        raise HTTPException(status_code=404, detail="Kind nicht gefunden")

    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.pin is not None:
        updates["pin_hash"] = hash_pin(body.pin)
    if body.switch_coins is not None:
        updates["switch_coins"] = body.switch_coins
    if body.switch_coins_weekly is not None:
        updates["switch_coins_weekly"] = body.switch_coins_weekly
    if body.switch_coins_max is not None:
        updates["switch_coins_max"] = body.switch_coins_max
    if body.tv_coins is not None:
        updates["tv_coins"] = body.tv_coins
    if body.tv_coins_weekly is not None:
        updates["tv_coins_weekly"] = body.tv_coins_weekly
    if body.tv_coins_max is not None:
        updates["tv_coins_max"] = body.tv_coins_max
    if body.allowed_from is not None:
        updates["allowed_from"] = body.allowed_from
    if body.allowed_until is not None:
        updates["allowed_until"] = body.allowed_until

    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        await db.execute(
            f"UPDATE children SET {set_clause} WHERE id=?",
            (*updates.values(), child_id),
        )
        await db.commit()

    return {"ok": True}


@router.delete("/children/{child_id}")
async def admin_delete_child(
    child_id: int,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    await db.execute("DELETE FROM children WHERE id=?", (child_id,))
    await db.execute("DELETE FROM sessions WHERE child_id=?", (child_id,))
    await db.execute("DELETE FROM coin_log WHERE child_id=?", (child_id,))
    await db.commit()
    return {"ok": True}


@router.post("/children/{child_id}/adjust-coins")
async def admin_adjust_coins(
    child_id: int,
    body: CoinAdjust,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    if body.type not in ("switch", "tv"):
        raise HTTPException(status_code=400, detail="Ungültiger Typ")

    async with db.execute("SELECT * FROM children WHERE id=?", (child_id,)) as cur:
        child = await cur.fetchone()
    if not child:
        raise HTTPException(status_code=404, detail="Kind nicht gefunden")

    coin_field = f"{body.type}_coins"
    max_field = f"{body.type}_coins_max"
    new_val = max(0, min(child[coin_field] + body.delta, child[max_field]))

    await db.execute(
        f"UPDATE children SET {coin_field}=? WHERE id=?", (new_val, child_id)
    )
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO coin_log (child_id, type, delta, reason, created_at) VALUES (?,?,?,?,?)",
        (child_id, body.type, body.delta, body.reason, now),
    )
    await db.commit()
    return {"ok": True, "new_value": new_val}


# --- Sessions ---

@router.get("/sessions")
async def admin_list_sessions(
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        """SELECT s.*, c.name as child_name
           FROM sessions s
           JOIN children c ON s.child_id = c.id
           ORDER BY s.started_at DESC
           LIMIT 100"""
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/sessions/{session_id}/cancel")
async def admin_cancel_session(
    session_id: int,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        "SELECT * FROM sessions WHERE id=? AND status='active'", (session_id,)
    ) as cur:
        session = await cur.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Aktive Session nicht gefunden")

    await db.execute(
        "UPDATE sessions SET status='cancelled' WHERE id=?", (session_id,)
    )
    await db.commit()

    if session["type"] == "tv":
        await mikrotik_direct.tv_sperren()
    elif session["type"] == "switch":
        await nintendo.switch_sperren()

    return {"ok": True}


# --- Mock-Status (nur im Simulations-Modus) ---

@router.get("/mock-status")
async def admin_mock_status(_: dict = Depends(get_current_admin)):
    """Zeigt den aktuellen simulierten Gerätezustand (nur wenn USE_MOCK_ADAPTERS=true)."""
    if not USE_MOCK:
        raise HTTPException(status_code=404, detail="Nur im Mock-Modus verfügbar")
    from adapters.mock import get_mock_status
    return get_mock_status()


# --- Coin log ---

@router.get("/coin-log")
async def admin_coin_log(
    child_id: int | None = None,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    if child_id:
        async with db.execute(
            """SELECT l.*, c.name as child_name
               FROM coin_log l
               JOIN children c ON l.child_id = c.id
               WHERE l.child_id=?
               ORDER BY l.created_at DESC LIMIT 200""",
            (child_id,),
        ) as cur:
            rows = await cur.fetchall()
    else:
        async with db.execute(
            """SELECT l.*, c.name as child_name
               FROM coin_log l
               JOIN children c ON l.child_id = c.id
               ORDER BY l.created_at DESC LIMIT 200"""
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
