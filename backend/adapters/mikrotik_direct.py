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
from urllib.parse import quote, urlparse
from typing import Any

logger = logging.getLogger(__name__)

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"

# Per-device cache: identifier → address-list entry id
_entry_id_cache: dict[str, str] = {}


def _get_cfg(config: dict) -> tuple[str, str, str]:
    """Extract connection params from config dict, with env-var fallback."""
    host = (config.get("host") or os.getenv("MIKROTIK_HOST", "")).strip()
    user = (
        config.get("user")
        or config.get("username")
        or os.getenv("MIKROTIK_USER", "")
        or os.getenv("MIKROTIK_USERNAME", "")
    ).strip()
    password = (config.get("password") or os.getenv("MIKROTIK_PASS", "")).strip()
    if password == "***":
        # Defensive fallback for accidentally persisted masked values.
        password = ""
    return host, user, password


def _has_credentials(user: str, password: str) -> bool:
    return bool(user and password)




def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def _find_entry_id(entries: list[dict], identifier: str) -> str | None:
    """Find best matching address-list entry for identifier."""
    ident = _normalized(identifier)
    if not ident:
        return None

    # 1) exact comment match (trimmed + case-insensitive)
    for entry in entries:
        if _normalized(entry.get("comment")) == ident:
            return entry.get(".id")

    # 2) fallback: contains match in comment (helps with accidental prefixes/suffixes)
    for entry in entries:
        comment = _normalized(entry.get("comment"))
        if comment and (ident in comment or comment in ident):
            return entry.get(".id")

    return None



def _entry_url(base_url: str, entry_id: str) -> str:
    # RouterOS ids look like "*1"; encode safely for path usage ("*" -> "%2A").
    return f"{base_url}/rest/ip/firewall/address-list/{quote(str(entry_id), safe='')}"


async def _patch_disabled(
    host: str,
    user: str,
    password: str,
    entry_id: str,
    disabled: bool,
) -> bool:
    """Patch disabled flag with payload fallbacks for RouterOS version quirks."""
    payloads = [{"disabled": disabled}, {"disabled": str(disabled).lower()}]

    for base_url in _base_urls(host):
        for payload in payloads:
            try:
                async with httpx.AsyncClient(verify=False, timeout=10) as client:
                    resp = await client.patch(
                        _entry_url(base_url, entry_id),
                        auth=(user, password),
                        json=payload,
                    )
                    resp.raise_for_status()
                    return True
            except httpx.HTTPStatusError as e:
                # Retry with alternate payload format on explicit validation errors.
                if e.response is not None and e.response.status_code == 400:
                    logger.warning(
                        "MikroTik: PATCH 400 mit payload=%s (entry_id=%s), versuche Fallback",
                        payload,
                        entry_id,
                    )
                    continue
                logger.error("MikroTik: PATCH Fehler: %s", e)
                break
            except httpx.TransportError:
                break

    return False


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
                # Try server-side filtering first (if supported by RouterOS REST).
                resp = await client.get(
                    f"{base_url}/rest/ip/firewall/address-list",
                    auth=(user, password),
                    params={"comment": identifier},
                )
                resp.raise_for_status()
                entries = resp.json()
                entry_id = _find_entry_id(entries, identifier)
                if entry_id:
                    _entry_id_cache[cache_key] = entry_id
                    return entry_id

                # Fallback: fetch full list and perform local matching.
                resp_all = await client.get(
                    f"{base_url}/rest/ip/firewall/address-list",
                    auth=(user, password),
                )
                resp_all.raise_for_status()
                all_entries = resp_all.json()
                entry_id = _find_entry_id(all_entries, identifier)
                if entry_id:
                    _entry_id_cache[cache_key] = entry_id
                    return entry_id

                logger.warning(
                    "MikroTik: Kein Address-List Eintrag mit passendem comment gefunden (identifier=%s)",
                    identifier,
                )
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
    if not _has_credentials(user, password):
        logger.warning("MikroTik: Zugangsdaten unvollständig (user/password)")
        return False
    entry_id = await _get_entry_id(host, user, password, identifier)
    if not entry_id:
        logger.error("MikroTik: TV-Eintrag nicht gefunden (identifier=%s)", identifier)
        return False
    try:
        if await _patch_disabled(host, user, password, entry_id, True):
            logger.info("MikroTik: TV freigegeben (identifier=%s)", identifier)
            return True
        logger.error("MikroTik: Fehler beim Freigeben: Keine Verbindung oder Request ungültig (%s)", host)
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
    if not _has_credentials(user, password):
        logger.warning("MikroTik: Zugangsdaten unvollständig (user/password)")
        return False
    entry_id = await _get_entry_id(host, user, password, identifier)
    if not entry_id:
        logger.error("MikroTik: TV-Eintrag nicht gefunden (identifier=%s)", identifier)
        return False
    try:
        if await _patch_disabled(host, user, password, entry_id, False):
            logger.info("MikroTik: TV gesperrt (identifier=%s)", identifier)
            return True
        logger.error("MikroTik: Fehler beim Sperren: Keine Verbindung oder Request ungültig (%s)", host)
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
    if not _has_credentials(user, password):
        logger.warning("MikroTik: Zugangsdaten unvollständig (user/password)")
        return False
    entry_id = await _get_entry_id(host, user, password, identifier)
    if not entry_id:
        return False
    try:
        for base_url in _base_urls(host):
            try:
                async with httpx.AsyncClient(verify=False, timeout=10) as client:
                    resp = await client.get(
                        _entry_url(base_url, entry_id),
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
