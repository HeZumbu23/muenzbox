"""
MikroTik RouterOS v7 REST API Adapter.

TV-IP is managed via Address-List "tv-blocked".
disabled=true  → IP is excluded from the list → TV is UNLOCKED (freigegeben)
disabled=false → IP is active in the list → TV is BLOCKED (gesperrt)
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

MIKROTIK_HOST = os.getenv("MIKROTIK_HOST", "")
MIKROTIK_USER = os.getenv("MIKROTIK_USER", "")
MIKROTIK_PASS = os.getenv("MIKROTIK_PASS", "")
MIKROTIK_TV_COMMENT = os.getenv("MIKROTIK_TV_ADDRESS_LIST_COMMENT", "Fernseher")
TV_IP = os.getenv("TV_IP", "")

_tv_entry_id: str | None = None


def _base_url() -> str:
    return f"https://{MIKROTIK_HOST}/rest"


def _auth() -> tuple[str, str]:
    return (MIKROTIK_USER, MIKROTIK_PASS)


async def _get_tv_entry_id() -> str | None:
    global _tv_entry_id
    if _tv_entry_id:
        return _tv_entry_id
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.get(
                f"{_base_url()}/ip/firewall/address-list",
                auth=_auth(),
                params={"comment": MIKROTIK_TV_COMMENT},
            )
            resp.raise_for_status()
            entries = resp.json()
            if entries:
                _tv_entry_id = entries[0][".id"]
                return _tv_entry_id
    except Exception as e:
        logger.error("MikroTik: Fehler beim Laden der Address-List: %s", e)
    return None


async def tv_freigeben() -> bool:
    """Unlock TV: set address-list entry to disabled=true."""
    if not MIKROTIK_HOST:
        logger.warning("MikroTik: Host nicht konfiguriert, simuliere Freigabe")
        return True
    entry_id = await _get_tv_entry_id()
    if not entry_id:
        logger.error("MikroTik: TV-Eintrag nicht gefunden")
        return False
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.patch(
                f"{_base_url()}/ip/firewall/address-list/{entry_id}",
                auth=_auth(),
                json={"disabled": "true"},
            )
            resp.raise_for_status()
            logger.info("MikroTik: TV freigegeben")
            return True
    except Exception as e:
        logger.error("MikroTik: Fehler beim Freigeben: %s", e)
        return False


async def tv_sperren() -> bool:
    """Block TV: set address-list entry to disabled=false."""
    if not MIKROTIK_HOST:
        logger.warning("MikroTik: Host nicht konfiguriert, simuliere Sperrung")
        return True
    entry_id = await _get_tv_entry_id()
    if not entry_id:
        logger.error("MikroTik: TV-Eintrag nicht gefunden")
        return False
    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.patch(
                f"{_base_url()}/ip/firewall/address-list/{entry_id}",
                auth=_auth(),
                json={"disabled": "false"},
            )
            resp.raise_for_status()
            logger.info("MikroTik: TV gesperrt")
            return True
    except Exception as e:
        logger.error("MikroTik: Fehler beim Sperren: %s", e)
        return False


async def tv_status() -> bool:
    """Returns True if TV is currently unlocked (disabled=true)."""
    if not MIKROTIK_HOST:
        return False
    entry_id = await _get_tv_entry_id()
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
