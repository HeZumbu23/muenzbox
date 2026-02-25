"""
MikroTik RouterOS v7 REST API Adapter.

TV-IP is managed via Address-List "tv-blocked".
disabled=true  → IP is excluded from the list → TV is UNLOCKED (freigegeben)
disabled=false → IP is active in the list → TV is BLOCKED (gesperrt)

Set USE_MOCK_ADAPTERS=true to skip real hardware and use in-memory simulation.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"

MIKROTIK_HOST = os.getenv("MIKROTIK_HOST", "")
MIKROTIK_USER = os.getenv("MIKROTIK_USER", "")
MIKROTIK_PASS = os.getenv("MIKROTIK_PASS", "")
MIKROTIK_TV_COMMENT = os.getenv("MIKROTIK_TV_ADDRESS_LIST_COMMENT", "Fernseher")
TV_IP = os.getenv("TV_IP", "")

# Per-device cache: identifier → address-list entry id
_entry_id_cache: dict[str, str] = {}


def _base_url() -> str:
    return f"https://{MIKROTIK_HOST}/rest"


def _auth() -> tuple[str, str]:
    return (MIKROTIK_USER, MIKROTIK_PASS)


async def _get_entry_id(identifier: str) -> str | None:
    if identifier in _entry_id_cache:
        return _entry_id_cache[identifier]
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.get(
                f"{_base_url()}/ip/firewall/address-list",
                auth=_auth(),
                params={"comment": identifier},
            )
            resp.raise_for_status()
            entries = resp.json()
            if entries:
                _entry_id_cache[identifier] = entries[0][".id"]
                return _entry_id_cache[identifier]
    except Exception as e:
        logger.error("MikroTik: Fehler beim Laden der Address-List: %s", e)
    return None


async def tv_freigeben(identifier: str = MIKROTIK_TV_COMMENT) -> bool:
    """Unlock TV: set address-list entry to disabled=true."""
    if USE_MOCK:
        from adapters.mock import mock_tv_freigeben
        return mock_tv_freigeben()

    if not MIKROTIK_HOST:
        logger.warning("MikroTik: Host nicht konfiguriert")
        return False
    entry_id = await _get_entry_id(identifier)
    if not entry_id:
        logger.error("MikroTik: TV-Eintrag nicht gefunden (identifier=%s)", identifier)
        return False
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.patch(
                f"{_base_url()}/ip/firewall/address-list/{entry_id}",
                auth=_auth(),
                json={"disabled": "true"},
            )
            resp.raise_for_status()
            logger.info("MikroTik: TV freigegeben (identifier=%s)", identifier)
            return True
    except Exception as e:
        logger.error("MikroTik: Fehler beim Freigeben: %s", e)
        return False


async def tv_sperren(identifier: str = MIKROTIK_TV_COMMENT) -> bool:
    """Block TV: set address-list entry to disabled=false."""
    if USE_MOCK:
        from adapters.mock import mock_tv_sperren
        return mock_tv_sperren()

    if not MIKROTIK_HOST:
        logger.warning("MikroTik: Host nicht konfiguriert")
        return False
    entry_id = await _get_entry_id(identifier)
    if not entry_id:
        logger.error("MikroTik: TV-Eintrag nicht gefunden (identifier=%s)", identifier)
        return False
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.patch(
                f"{_base_url()}/ip/firewall/address-list/{entry_id}",
                auth=_auth(),
                json={"disabled": "false"},
            )
            resp.raise_for_status()
            logger.info("MikroTik: TV gesperrt (identifier=%s)", identifier)
            return True
    except Exception as e:
        logger.error("MikroTik: Fehler beim Sperren: %s", e)
        return False


async def tv_status(identifier: str = MIKROTIK_TV_COMMENT) -> bool:
    """Returns True if TV is currently unlocked (disabled=true)."""
    if USE_MOCK:
        from adapters.mock import mock_tv_status
        return mock_tv_status()

    if not MIKROTIK_HOST:
        return False
    entry_id = await _get_entry_id(identifier)
    if not entry_id:
        return False
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.get(
                f"{_base_url()}/ip/firewall/address-list/{entry_id}",
                auth=_auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("disabled", "false")).lower() == "true"
    except Exception as e:
        logger.error("MikroTik: Fehler beim Statusabruf: %s", e)
        return False
