"""
MikroTik RouterOS v7 REST API Adapter.

TV-IP is managed via Address-List "tv-blocked".
disabled=true  → IP is excluded from the list → TV is UNLOCKED (freigegeben)
disabled=false → IP is active in the list → TV is BLOCKED (gesperrt)

Credentials werden per config-Dict übergeben (aus der Geräteverwaltung).
Env-Vars MIKROTIK_* dienen nur noch als Fallback für bestehende Setups.

Set USE_MOCK_ADAPTERS=true to skip real hardware and use in-memory simulation.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"

# Per-device cache: identifier → address-list entry id
_entry_id_cache: dict[str, str] = {}


def _get_cfg(config: dict) -> tuple[str, str, str]:
    """Extract connection params from config dict, with env-var fallback."""
    host = config.get("host") or os.getenv("MIKROTIK_HOST", "")
    user = config.get("user") or os.getenv("MIKROTIK_USER", "")
    password = config.get("password") or os.getenv("MIKROTIK_PASS", "")
    return host, user, password


async def _get_entry_id(host: str, user: str, password: str, identifier: str) -> str | None:
    cache_key = f"{host}:{identifier}"
    if cache_key in _entry_id_cache:
        return _entry_id_cache[cache_key]
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.get(
                f"https://{host}/rest/ip/firewall/address-list",
                auth=(user, password),
                params={"comment": identifier},
            )
            resp.raise_for_status()
            entries = resp.json()
            if entries:
                _entry_id_cache[cache_key] = entries[0][".id"]
                return _entry_id_cache[cache_key]
    except Exception as e:
        logger.error("MikroTik: Fehler beim Laden der Address-List: %s", e)
    return None


async def tv_freigeben(identifier: str, config: dict = {}) -> bool:
    """Unlock TV: set address-list entry to disabled=true."""
    if USE_MOCK:
        from adapters.mock import mock_tv_freigeben
        return mock_tv_freigeben()
    host, user, password = _get_cfg(config)
    if not host:
        logger.warning("MikroTik: Host nicht konfiguriert")
        return False
    entry_id = await _get_entry_id(host, user, password, identifier)
    if not entry_id:
        logger.error("MikroTik: TV-Eintrag nicht gefunden (identifier=%s)", identifier)
        return False
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.patch(
                f"https://{host}/rest/ip/firewall/address-list/{entry_id}",
                auth=(user, password),
                json={"disabled": "true"},
            )
            resp.raise_for_status()
            logger.info("MikroTik: TV freigegeben (identifier=%s)", identifier)
            return True
    except Exception as e:
        logger.error("MikroTik: Fehler beim Freigeben: %s", e)
        return False


async def tv_sperren(identifier: str, config: dict = {}) -> bool:
    """Block TV: set address-list entry to disabled=false."""
    if USE_MOCK:
        from adapters.mock import mock_tv_sperren
        return mock_tv_sperren()
    host, user, password = _get_cfg(config)
    if not host:
        logger.warning("MikroTik: Host nicht konfiguriert")
        return False
    entry_id = await _get_entry_id(host, user, password, identifier)
    if not entry_id:
        logger.error("MikroTik: TV-Eintrag nicht gefunden (identifier=%s)", identifier)
        return False
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.patch(
                f"https://{host}/rest/ip/firewall/address-list/{entry_id}",
                auth=(user, password),
                json={"disabled": "false"},
            )
            resp.raise_for_status()
            logger.info("MikroTik: TV gesperrt (identifier=%s)", identifier)
            return True
    except Exception as e:
        logger.error("MikroTik: Fehler beim Sperren: %s", e)
        return False


async def tv_status(identifier: str, config: dict = {}) -> bool:
    """Returns True if TV is currently unlocked (disabled=true)."""
    if USE_MOCK:
        from adapters.mock import mock_tv_status
        return mock_tv_status()
    host, user, password = _get_cfg(config)
    if not host:
        return False
    entry_id = await _get_entry_id(host, user, password, identifier)
    if not entry_id:
        return False
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.get(
                f"https://{host}/rest/ip/firewall/address-list/{entry_id}",
                auth=(user, password),
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("disabled", "false")).lower() == "true"
    except Exception as e:
        logger.error("MikroTik: Fehler beim Statusabruf: %s", e)
        return False
