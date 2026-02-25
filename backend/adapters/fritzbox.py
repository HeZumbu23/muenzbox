"""
FritzBox LUA Interface Adapter.

Steuert Geräte-Zugangsprofile über die FritzBox LUA-Schnittstelle.
- Gerät wird per FritzBox-Gerätename (Hostname) identifiziert
- Freigabe: Zugangsprofil auf FRITZBOX_ALLOWED_PROFILE setzen (Standard: "Standard")
- Sperrung: Zugangsprofil auf FRITZBOX_BLOCKED_PROFILE setzen (Standard: "Gesperrt")

Unterstützt Login via PBKDF2-SHA256 (FRITZ!OS >= 7.24) und MD5 (ältere Versionen).

Set USE_MOCK_ADAPTERS=true to skip real hardware and use in-memory simulation.
"""
import hashlib
import hmac
import logging
import os
import time
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"

FRITZBOX_HOST = os.getenv("FRITZBOX_HOST", "fritz.box")
FRITZBOX_USER = os.getenv("FRITZBOX_USER", "")
FRITZBOX_PASS = os.getenv("FRITZBOX_PASS", "")
FRITZBOX_ALLOWED_PROFILE = os.getenv("FRITZBOX_ALLOWED_PROFILE", "Standard")
FRITZBOX_BLOCKED_PROFILE = os.getenv("FRITZBOX_BLOCKED_PROFILE", "Gesperrt")

# SID cache: {"sid": str, "expires_at": float}
_sid_cache: dict = {}
_SID_TTL = 18 * 60  # 18 minutes (FritzBox invalidates after 20 min idle)


def _base_url() -> str:
    return f"http://{FRITZBOX_HOST}"


def _sid_is_valid() -> bool:
    return (
        bool(_sid_cache.get("sid"))
        and _sid_cache.get("sid") != "0000000000000000"
        and time.monotonic() < _sid_cache.get("expires_at", 0)
    )


def _invalidate_sid() -> None:
    _sid_cache.clear()


def _compute_pbkdf2_response(challenge: str, password: str) -> str:
    """Compute PBKDF2-SHA256 challenge response for FRITZ!OS >= 7.24."""
    # challenge format: "2$<iter1>$<salt1>$<iter2>$<salt2>"
    parts = challenge.split("$")
    iter1 = int(parts[1])
    salt1 = bytes.fromhex(parts[2])
    iter2 = int(parts[3])
    salt2 = bytes.fromhex(parts[4])

    hash1 = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt1, iter1)
    hash2 = hashlib.pbkdf2_hmac("sha256", hash1, salt2, iter2)
    return f"{challenge}${hash2.hex()}"


def _compute_md5_response(challenge: str, password: str) -> str:
    """Compute MD5 challenge response for older FRITZ!OS versions."""
    response_str = f"{challenge}-{password}"
    md5 = hashlib.md5(response_str.encode("utf-16-le")).hexdigest()
    return f"{challenge}-{md5}"


async def _login() -> str | None:
    """Authenticate with FritzBox and return a valid SID."""
    if not FRITZBOX_PASS:
        logger.warning("FritzBox: Passwort nicht konfiguriert (FRITZBOX_PASS)")
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Step 1: Get challenge
            resp = await client.get(f"{_base_url()}/login_sid.lua?version=2")
            resp.raise_for_status()
            root = ET.fromstring(resp.text)

            sid = root.findtext("SID", "0000000000000000")
            if sid != "0000000000000000":
                # Already logged in (session still valid from another path)
                _sid_cache["sid"] = sid
                _sid_cache["expires_at"] = time.monotonic() + _SID_TTL
                return sid

            challenge = root.findtext("Challenge", "")
            if not challenge:
                logger.error("FritzBox: Kein Challenge in Login-Antwort")
                return None

            # Step 2: Compute response based on algorithm
            if challenge.startswith("2$"):
                response = _compute_pbkdf2_response(challenge, FRITZBOX_PASS)
            else:
                response = _compute_md5_response(challenge, FRITZBOX_PASS)

            # Step 3: Submit credentials
            resp = await client.post(
                f"{_base_url()}/login_sid.lua?version=2",
                data={"username": FRITZBOX_USER, "response": response},
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)

            sid = root.findtext("SID", "0000000000000000")
            if sid == "0000000000000000":
                logger.error("FritzBox: Login fehlgeschlagen (ungültige Zugangsdaten?)")
                return None

            _sid_cache["sid"] = sid
            _sid_cache["expires_at"] = time.monotonic() + _SID_TTL
            logger.info("FritzBox: Login erfolgreich (SID=%s...)", sid[:4])
            return sid

    except Exception as e:
        logger.error("FritzBox: Login-Fehler: %s", e)
        return None


async def _get_sid(force_refresh: bool = False) -> str | None:
    """Return a valid SID, logging in if necessary."""
    if not force_refresh and _sid_is_valid():
        return _sid_cache["sid"]
    return await _login()


async def _get_device_uid(client: httpx.AsyncClient, sid: str, device_name: str) -> str | None:
    """Find the FritzBox device UID by hostname."""
    resp = await client.post(
        f"{_base_url()}/data.lua",
        data={"xhr": "1", "sid": sid, "lang": "de", "page": "netDev", "xhrId": "all"},
    )
    resp.raise_for_status()
    data = resp.json()

    devices = data.get("data", {})
    # Devices can be in "active" or "passive" list
    all_devices = devices.get("active", []) + devices.get("passive", [])
    for dev in all_devices:
        if dev.get("name") == device_name:
            return dev.get("UID") or dev.get("uid")

    logger.error("FritzBox: Gerät '%s' nicht gefunden", device_name)
    return None


async def _get_profile_id(client: httpx.AsyncClient, sid: str, profile_name: str) -> str | None:
    """Find the FritzBox access profile ID by name."""
    resp = await client.post(
        f"{_base_url()}/data.lua",
        data={"xhr": "1", "sid": sid, "lang": "de", "page": "kidProfils"},
    )
    resp.raise_for_status()
    data = resp.json()

    profiles = data.get("data", {}).get("profiles", [])
    for profile in profiles:
        if profile.get("Name") == profile_name or profile.get("name") == profile_name:
            return profile.get("Id") or profile.get("id")

    logger.error("FritzBox: Profil '%s' nicht gefunden", profile_name)
    return None


async def _set_profile(device_uid: str, profile_id: str, sid: str) -> bool:
    """Assign an access profile to a device."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_base_url()}/data.lua",
            data={
                "xhr": "1",
                "sid": sid,
                "lang": "de",
                "page": "kids_device",
                "xhrId": "all",
                "dev": device_uid,
                "profile": profile_id,
                "apply": "",
            },
        )
        resp.raise_for_status()
    return True


async def _change_profile(identifier: str, profile_name: str) -> bool:
    """Core logic: change device access profile. Retries once on auth failure."""
    for attempt in range(2):
        sid = await _get_sid(force_refresh=(attempt > 0))
        if not sid:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                device_uid = await _get_device_uid(client, sid, identifier)
                if not device_uid:
                    return False

                profile_id = await _get_profile_id(client, sid, profile_name)
                if not profile_id:
                    return False

            await _set_profile(device_uid, profile_id, sid)
            logger.info(
                "FritzBox: Gerät '%s' → Profil '%s' gesetzt", identifier, profile_name
            )
            return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and attempt == 0:
                logger.warning("FritzBox: SID abgelaufen, erneuere Login...")
                _invalidate_sid()
                continue
            logger.error("FritzBox: HTTP-Fehler beim Profilwechsel: %s", e)
            return False
        except Exception as e:
            logger.error("FritzBox: Fehler beim Profilwechsel: %s", e)
            return False

    return False


async def tv_freigeben(identifier: str) -> bool:
    """Unlock TV: set access profile to FRITZBOX_ALLOWED_PROFILE."""
    if USE_MOCK:
        from adapters.mock import mock_tv_freigeben
        return mock_tv_freigeben()

    if not FRITZBOX_HOST:
        logger.warning("FritzBox: Host nicht konfiguriert")
        return False

    return await _change_profile(identifier, FRITZBOX_ALLOWED_PROFILE)


async def tv_sperren(identifier: str) -> bool:
    """Block TV: set access profile to FRITZBOX_BLOCKED_PROFILE."""
    if USE_MOCK:
        from adapters.mock import mock_tv_sperren
        return mock_tv_sperren()

    if not FRITZBOX_HOST:
        logger.warning("FritzBox: Host nicht konfiguriert")
        return False

    return await _change_profile(identifier, FRITZBOX_BLOCKED_PROFILE)


async def tv_status(identifier: str) -> bool:
    """Returns True if TV is currently unlocked (access profile = FRITZBOX_ALLOWED_PROFILE)."""
    if USE_MOCK:
        from adapters.mock import mock_tv_status
        return mock_tv_status()

    if not FRITZBOX_HOST:
        return False

    sid = await _get_sid()
    if not sid:
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            device_uid = await _get_device_uid(client, sid, identifier)
            if not device_uid:
                return False

            profile_id = await _get_profile_id(client, sid, FRITZBOX_ALLOWED_PROFILE)
            if not profile_id:
                return False

            # Check current profile assignment via netDev detail
            resp = await client.post(
                f"{_base_url()}/data.lua",
                data={
                    "xhr": "1",
                    "sid": sid,
                    "lang": "de",
                    "page": "netDev",
                    "xhrId": "all",
                },
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
                    current_profile = dev.get("kisi_profile") or dev.get("profile")
                    return current_profile == profile_id

    except Exception as e:
        logger.error("FritzBox: Fehler beim Statusabruf: %s", e)

    return False
