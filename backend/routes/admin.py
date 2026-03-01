import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

import aiosqlite
from database import get_db
from auth import hash_pin, create_token, get_current_admin
from models import AdminVerify, ChildCreate, ChildUpdate, CoinAdjust, DeviceCreate, DeviceUpdate
import adapters
from adapters import nintendo

_FALLBACK = '[{"von":"08:00","bis":"20:00"}]'


def _parse_periods(raw) -> list:
    if isinstance(raw, list):
        return raw
    return json.loads(raw or _FALLBACK)

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"

router = APIRouter()

ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")


@router.post("/verify")
async def admin_verify(body: AdminVerify):
    """Verify admin PIN and return admin token."""
    if body.pin != ADMIN_PIN:
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
    result = []
    for r in rows:
        child = dict(r)
        child["allowed_periods"] = _parse_periods(child.get("allowed_periods"))
        child["weekend_periods"] = _parse_periods(child.get("weekend_periods"))
        child["avatar"] = child.get("avatar") or "🦁"
        result.append(child)
    return result


@router.post("/children", status_code=201)
async def admin_create_child(
    body: ChildCreate,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    pin_hash = hash_pin(body.pin)
    allowed_json = json.dumps([{"von": p.von, "bis": p.bis} for p in body.allowed_periods])
    weekend_json = json.dumps([{"von": p.von, "bis": p.bis} for p in body.weekend_periods])
    async with db.execute(
        """INSERT INTO children
           (name, pin_hash, switch_coins, switch_coins_weekly, switch_coins_max,
            tv_coins, tv_coins_weekly, tv_coins_max,
            allowed_periods, weekend_periods, avatar)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            body.name, pin_hash,
            body.switch_coins, body.switch_coins_weekly, body.switch_coins_max,
            body.tv_coins, body.tv_coins_weekly, body.tv_coins_max,
            allowed_json, weekend_json, body.avatar,
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
    if body.allowed_periods is not None:
        updates["allowed_periods"] = json.dumps([{"von": p.von, "bis": p.bis} for p in body.allowed_periods])
    if body.weekend_periods is not None:
        updates["weekend_periods"] = json.dumps([{"von": p.von, "bis": p.bis} for p in body.weekend_periods])
    if body.avatar is not None:
        updates["avatar"] = body.avatar

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
        async with db.execute(
            "SELECT identifier, control_type FROM devices WHERE device_type='tv' AND is_active=1 LIMIT 1"
        ) as cur:
            dev = await cur.fetchone()
        identifier = dev["identifier"] if dev and dev["identifier"] else "Fernseher"
        control_type = dev["control_type"] if dev else "mikrotik"
        await adapters.tv_sperren(control_type, identifier)
    elif session["type"] == "switch":
        await nintendo.switch_sperren()

    return {"ok": True}


# --- Mock-Status (nur im Simulations-Modus) ---

@router.get("/mock-status")
async def admin_mock_status(_: dict = Depends(get_current_admin)):
    """Zeigt den aktuellen simulierten Gerätezustand (nur wenn USE_MOCK_ADAPTERS=true)."""
    if not USE_MOCK:
        # Kein 404, damit das Admin-Frontend den Status-Endpunkt gefahrlos pollen kann.
        return None
    from adapters.mock import get_mock_status
    return get_mock_status()


# --- Devices ---

_ALLOWED_DEVICE_TYPES = {"tv"}
_ALLOWED_CONTROL_TYPES = {"fritzbox", "mikrotik", "schedule_only", "none"}


def _mask_config(cfg: dict) -> dict:
    """Return config with password replaced by *** for display."""
    if not cfg:
        return cfg
    masked = dict(cfg)
    if masked.get("password"):
        masked["password"] = "***"
    return masked


@router.get("/devices")
async def admin_list_devices(
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        """SELECT d.*, c.name as child_name
           FROM devices d
           LEFT JOIN children c ON d.child_id = c.id
           ORDER BY d.device_type, d.name"""
    ) as cur:
        rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        cfg = json.loads(d.get("config") or "{}")
        d["config"] = _mask_config(cfg)
        result.append(d)
    return result


@router.post("/devices", status_code=201)
async def admin_create_device(
    body: DeviceCreate,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    if body.device_type not in _ALLOWED_DEVICE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unbekannter Typ: {body.device_type}")
    if body.control_type not in _ALLOWED_CONTROL_TYPES:
        raise HTTPException(status_code=400, detail=f"Unbekannter Steuertyp: {body.control_type}")
    async with db.execute(
        "INSERT INTO devices (name, device_type, control_type, identifier, config, is_active) VALUES (?,?,?,?,?,1)",
        (body.name, body.device_type, body.control_type, body.identifier, json.dumps(body.config)),
    ) as cur:
        device_id = cur.lastrowid
    await db.commit()
    return {"id": device_id, "name": body.name}


@router.put("/devices/{device_id}")
async def admin_update_device(
    device_id: int,
    body: DeviceUpdate,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT * FROM devices WHERE id=?", (device_id,)) as cur:
        device = await cur.fetchone()
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")

    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.identifier is not None:
        updates["identifier"] = body.identifier
    if body.device_type is not None:
        if body.device_type not in _ALLOWED_DEVICE_TYPES:
            raise HTTPException(status_code=400, detail=f"Unbekannter Typ: {body.device_type}")
        updates["device_type"] = body.device_type
    if body.control_type is not None:
        if body.control_type not in _ALLOWED_CONTROL_TYPES:
            raise HTTPException(status_code=400, detail=f"Unbekannter Steuertyp: {body.control_type}")
        updates["control_type"] = body.control_type
    if body.config is not None:
        # Merge with existing config; keep stored password if submitted value is "***"
        existing_cfg = json.loads(device["config"] or "{}")
        new_cfg = dict(existing_cfg)
        new_cfg.update(body.config)
        if new_cfg.get("password") == "***":
            new_cfg["password"] = existing_cfg.get("password", "")
        updates["config"] = json.dumps(new_cfg)
    if body.is_active is not None:
        updates["is_active"] = 1 if body.is_active else 0

    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        await db.execute(
            f"UPDATE devices SET {set_clause} WHERE id=?",
            (*updates.values(), device_id),
        )
        await db.commit()
    return {"ok": True}


@router.delete("/devices/{device_id}")
async def admin_delete_device(
    device_id: int,
    _: dict = Depends(get_current_admin),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT * FROM devices WHERE id=?", (device_id,)) as cur:
        device = await cur.fetchone()
    if not device:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")
    await db.execute("DELETE FROM devices WHERE id=?", (device_id,))
    await db.commit()
    return {"ok": True}


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
