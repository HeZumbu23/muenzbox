"""
FritzBox LUA Interface Adapter.

Steuert Geräte-Zugangsprofile über die FritzBox LUA-Schnittstelle.
- Gerät wird per FritzBox-Gerätename (Hostname) identifiziert
- Freigabe: Zugangsprofil auf allowed_profile setzen (Standard: "Standard")
- Sperrung: Zugangsprofil auf blocked_profile setzen (Standard: "Gesperrt")

Credentials werden per config-Dict übergeben (aus der Geräteverwaltung).
Env-Vars FRITZBOX_* dienen nur noch als Fallback für bestehende Setups.

Set USE_MOCK_ADAPTERS=true to skip real hardware and use in-memory simulation.
"""
import hashlib
import logging
import os
import time
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"

# SID cache per host: host → {"sid": str, "expires_at": float}
_sid_cache: dict[str, dict] = {}
_SID_TTL = 18 * 60  # 18 minutes (FritzBox invalidates after 20 min idle)


def _get_cfg(config: dict) -> tuple[str, str, str, str, str]:
    """Extract connection params from config dict, with env-var fallback."""
    host = config.get("host") or os.getenv("FRITZBOX_HOST", "fritz.box")
    user = config.get("user") or os.getenv("FRITZBOX_USER", "")
    password = config.get("password") or os.getenv("FRITZBOX_PASS", "")
    allowed = config.get("allowed_profile") or os.getenv("FRITZBOX_ALLOWED_PROFILE", "Standard")
    blocked = config.get("blocked_profile") or os.getenv("FRITZBOX_BLOCKED_PROFILE", "Gesperrt")
    return host, user, password, allowed, blocked


def _base_url(host: str) -> str:
    return f"http://{host}"


def _sid_is_valid(host: str) -> bool:
    c = _sid_cache.get(host, {})
    return (
        bool(c.get("sid"))
        and c.get("sid") != "0000000000000000"
        and time.monotonic() < c.get("expires_at", 0)
    )


def _invalidate_sid(host: str) -> None:
    _sid_cache.pop(host, None)


def _compute_pbkdf2_response(challenge: str, password: str) -> str:
    parts = challenge.split("$")
    iter1, salt1 = int(parts[1]), bytes.fromhex(parts[2])
    iter2, salt2 = int(parts[3]), bytes.fromhex(parts[4])
    hash1 = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt1, iter1)
    hash2 = hashlib.pbkdf2_hmac("sha256", hash1, salt2, iter2)
    return f"{challenge}${hash2.hex()}"


def _compute_md5_response(challenge: str, password: str) -> str:
    md5 = hashlib.md5(f"{challenge}-{password}".encode("utf-16-le")).hexdigest()
    return f"{challenge}-{md5}"


async def _login(host: str, user: str, password: str) -> str | None:
    if not password:
        logger.warning("FritzBox: Passwort nicht konfiguriert")
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{_base_url(host)}/login_sid.lua?version=2")
            resp.raise_for_status()
            root = ET.fromstring(resp.text)

            sid = root.findtext("SID", "0000000000000000")
            if sid != "0000000000000000":
                _sid_cache[host] = {"sid": sid, "expires_at": time.monotonic() + _SID_TTL}
                return sid

            challenge = root.findtext("Challenge", "")
            if not challenge:
                logger.error("FritzBox: Kein Challenge in Login-Antwort")
                return None

            response = (
                _compute_pbkdf2_response(challenge, password)
                if challenge.startswith("2$")
                else _compute_md5_response(challenge, password)
            )

            resp = await client.post(
                f"{_base_url(host)}/login_sid.lua?version=2",
                data={"username": user, "response": response},
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            sid = root.findtext("SID", "0000000000000000")
            if sid == "0000000000000000":
                logger.error("FritzBox: Login fehlgeschlagen (ungültige Zugangsdaten?)")
                return None

            _sid_cache[host] = {"sid": sid, "expires_at": time.monotonic() + _SID_TTL}
            logger.info("FritzBox: Login erfolgreich (SID=%s...)", sid[:4])
            return sid
    except Exception as e:
        logger.error("FritzBox: Login-Fehler: %s", e)
        return None


async def _get_sid(host: str, user: str, password: str, force_refresh: bool = False) -> str | None:
    if not force_refresh and _sid_is_valid(host):
        return _sid_cache[host]["sid"]
    return await _login(host, user, password)


async def _get_device_uid(client: httpx.AsyncClient, host: str, sid: str, device_name: str) -> str | None:
    resp = await client.post(
        f"{_base_url(host)}/data.lua",
        data={"xhr": "1", "sid": sid, "lang": "de", "page": "netDev", "xhrId": "all"},
    )
    resp.raise_for_status()
    data = resp.json()
    all_devices = data.get("data", {}).get("active", []) + data.get("data", {}).get("passive", [])
    for dev in all_devices:
        if dev.get("name") == device_name:
            return dev.get("UID") or dev.get("uid")
    logger.error("FritzBox: Gerät '%s' nicht gefunden", device_name)
    return None


async def _get_profile_id(client: httpx.AsyncClient, host: str, sid: str, profile_name: str) -> str | None:
    resp = await client.post(
        f"{_base_url(host)}/data.lua",
        data={"xhr": "1", "sid": sid, "lang": "de", "page": "kidProfils"},
    )
    resp.raise_for_status()
    profiles = resp.json().get("data", {}).get("profiles", [])
    for p in profiles:
        if p.get("Name") == profile_name or p.get("name") == profile_name:
            return p.get("Id") or p.get("id")
    logger.error("FritzBox: Profil '%s' nicht gefunden", profile_name)
    return None


async def _set_profile(host: str, sid: str, device_uid: str, profile_id: str) -> bool:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_base_url(host)}/data.lua",
            data={
                "xhr": "1", "sid": sid, "lang": "de",
                "page": "kids_device", "xhrId": "all",
                "dev": device_uid, "profile": profile_id, "apply": "",
            },
        )
        resp.raise_for_status()
    return True


async def _change_profile(identifier: str, profile_name: str, host: str, user: str, password: str) -> bool:
    for attempt in range(2):
        sid = await _get_sid(host, user, password, force_refresh=(attempt > 0))
        if not sid:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                device_uid = await _get_device_uid(client, host, sid, identifier)
                if not device_uid:
                    return False
                profile_id = await _get_profile_id(client, host, sid, profile_name)
                if not profile_id:
                    return False
            await _set_profile(host, sid, device_uid, profile_id)
            logger.info("FritzBox: Gerät '%s' → Profil '%s' gesetzt", identifier, profile_name)
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and attempt == 0:
                logger.warning("FritzBox: SID abgelaufen, erneuere Login...")
                _invalidate_sid(host)
                continue
            logger.error("FritzBox: HTTP-Fehler beim Profilwechsel: %s", e)
            return False
        except Exception as e:
            logger.error("FritzBox: Fehler beim Profilwechsel: %s", e)
            return False
    return False


async def tv_freigeben(identifier: str, config: dict = {}) -> bool:
    if USE_MOCK:
        from adapters.mock import mock_tv_freigeben
        return mock_tv_freigeben()
    host, user, password, allowed, _ = _get_cfg(config)
    if not host:
        logger.warning("FritzBox: Host nicht konfiguriert")
        return False
    return await _change_profile(identifier, allowed, host, user, password)


async def tv_sperren(identifier: str, config: dict = {}) -> bool:
    if USE_MOCK:
        from adapters.mock import mock_tv_sperren
        return mock_tv_sperren()
    host, user, password, _, blocked = _get_cfg(config)
    if not host:
        logger.warning("FritzBox: Host nicht konfiguriert")
        return False
    return await _change_profile(identifier, blocked, host, user, password)


async def tv_status(identifier: str, config: dict = {}) -> bool:
    if USE_MOCK:
        from adapters.mock import mock_tv_status
        return mock_tv_status()
    host, user, password, allowed, _ = _get_cfg(config)
    if not host:
        return False
    sid = await _get_sid(host, user, password)
    if not sid:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            device_uid = await _get_device_uid(client, host, sid, identifier)
            if not device_uid:
                return False
            profile_id = await _get_profile_id(client, host, sid, allowed)
            if not profile_id:
                return False
            resp = await client.post(
                f"{_base_url(host)}/data.lua",
                data={"xhr": "1", "sid": sid, "lang": "de", "page": "netDev", "xhrId": "all"},
            )
            resp.raise_for_status()
            data = resp.json()
            all_devices = (
                data.get("data", {}).get("active", [])
                + data.get("data", {}).get("passive", [])
            )
            for dev in all_devices:
                uid = dev.get("UID") or dev.get("uid")
                if uid == device_uid:
                    return (dev.get("kisi_profile") or dev.get("profile")) == profile_id
    except Exception as e:
        logger.error("FritzBox: Fehler beim Statusabruf: %s", e)
    return False
