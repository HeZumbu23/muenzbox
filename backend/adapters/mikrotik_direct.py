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
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"

# Per-device cache: identifier → address-list entry id
_entry_id_cache: dict[str, str] = {}


def _get_cfg(config: dict) -> tuple[str, str, str]:
    """Extract connection params from config dict, with env-var fallback."""
    host = (config.get("host") or os.getenv("MIKROTIK_HOST", "")).strip()
    user = (config.get("user") or os.getenv("MIKROTIK_USER", "")).strip()
    password = (config.get("password") or os.getenv("MIKROTIK_PASS", "")).strip()
    return host, user, password


def _base_urls(host: str) -> list[str]:
    """Return base URLs for RouterOS REST API.

    - If host already includes a scheme, respect it.
    - Otherwise prefer HTTPS and fallback to HTTP for setups without TLS.
    """
    if not host:
        return []
    parsed = urlparse(host)
    if parsed.scheme:
        return [host.rstrip("/")]
    clean_host = host.rstrip("/")
    return [f"https://{clean_host}", f"http://{clean_host}"]


async def _get_entry_id(host: str, user: str, password: str, identifier: str) -> str | None:
    cache_key = f"{host}:{identifier}"
    if cache_key in _entry_id_cache:
        return _entry_id_cache[cache_key]
    base_urls = _base_urls(host)
    if not base_urls:
        return None
    last_error = None
    for base_url in base_urls:
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.get(
                    f"{base_url}/rest/ip/firewall/address-list",
                    auth=(user, password),
                    params={"comment": identifier},
                )
                resp.raise_for_status()
                entries = resp.json()
                if entries:
                    _entry_id_cache[cache_key] = entries[0][".id"]
                    return _entry_id_cache[cache_key]
                return None
        except httpx.TransportError as e:
            last_error = e
            continue
        except Exception as e:
            logger.error("MikroTik: Fehler beim Laden der Address-List: %s", e)
            return None

    if last_error:
        logger.error("MikroTik: Fehler beim Laden der Address-List: %s", last_error)
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
        for base_url in _base_urls(host):
            try:
                async with httpx.AsyncClient(verify=False, timeout=10) as client:
                    resp = await client.patch(
                        f"{base_url}/rest/ip/firewall/address-list/{entry_id}",
                        auth=(user, password),
                        json={"disabled": "true"},
                    )
                    resp.raise_for_status()
                    logger.info("MikroTik: TV freigegeben (identifier=%s)", identifier)
                    return True
            except httpx.TransportError:
                continue
        logger.error("MikroTik: Fehler beim Freigeben: Keine Verbindung zu %s", host)
        return False
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
        for base_url in _base_urls(host):
            try:
                async with httpx.AsyncClient(verify=False, timeout=10) as client:
                    resp = await client.patch(
                        f"{base_url}/rest/ip/firewall/address-list/{entry_id}",
                        auth=(user, password),
                        json={"disabled": "false"},
                    )
                    resp.raise_for_status()
                    logger.info("MikroTik: TV gesperrt (identifier=%s)", identifier)
                    return True
            except httpx.TransportError:
                continue
        logger.error("MikroTik: Fehler beim Sperren: Keine Verbindung zu %s", host)
        return False
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
        for base_url in _base_urls(host):
            try:
                async with httpx.AsyncClient(verify=False, timeout=10) as client:
                    resp = await client.get(
                        f"{base_url}/rest/ip/firewall/address-list/{entry_id}",
                        auth=(user, password),
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return str(data.get("disabled", "false")).lower() == "true"
            except httpx.TransportError:
                continue
        logger.error("MikroTik: Fehler beim Statusabruf: Keine Verbindung zu %s", host)
        return False
    except Exception as e:
        logger.error("MikroTik: Fehler beim Statusabruf: %s", e)
        return False
