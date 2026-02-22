"""
Nintendo Switch Parental Controls Adapter.
Uses the pynintendoparental library to control daily play time limits.

Session start: Set daily limit to coins * 30 minutes
Session end:   Set daily limit to 0 (blocks play)

Set USE_MOCK_ADAPTERS=true to skip real hardware and use in-memory simulation.
"""
import os
import logging

logger = logging.getLogger(__name__)

USE_MOCK = os.getenv("USE_MOCK_ADAPTERS", "false").lower() == "true"
NINTENDO_TOKEN = os.getenv("NINTENDO_TOKEN", "")
NINTENDO_TZ = os.getenv("NINTENDO_TIMEZONE", "Europe/Berlin")
NINTENDO_LANG = os.getenv("NINTENDO_LANG", "de-DE")

try:
    import aiohttp
    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator
    _LIBRARY_AVAILABLE = True
except ImportError:
    _LIBRARY_AVAILABLE = False
    logger.warning("pynintendoparental nicht installiert – Nintendo-Integration deaktiviert")


async def _set_playtime(minutes: int) -> bool:
    """Shared helper: authenticate and set daily playtime limit."""
    async with aiohttp.ClientSession() as http_session:
        auth = Authenticator(NINTENDO_TOKEN, http_session)
        await auth.async_complete_login(use_session_token=True)
        parental = await NintendoParental.create(
            auth, timezone=NINTENDO_TZ, lang=NINTENDO_LANG
        )
        devices = parental.devices
        if not devices:
            logger.error(
                "Nintendo: Keine Geräte gefunden – Token korrekt? "
                "Gerät in Kindersicherungs-App registriert?"
            )
            return False
        device = list(devices.values())[0]
        await device.set_max_daily_playtime(minutes)
        return True


async def switch_freigeben(minutes: int = 30) -> bool:
    """Unlock Nintendo Switch by setting daily time limit to `minutes`."""
    if USE_MOCK:
        from adapters.mock import mock_switch_freigeben
        return mock_switch_freigeben(minutes)

    if not NINTENDO_TOKEN:
        logger.warning("Nintendo: Token nicht konfiguriert")
        return False
    if not _LIBRARY_AVAILABLE:
        logger.warning("Nintendo: Library nicht verfügbar")
        return False
    try:
        ok = await _set_playtime(minutes)
        if ok:
            logger.info("Nintendo: Switch freigegeben für %d Minuten", minutes)
        return ok
    except Exception:
        logger.exception("Nintendo: Fehler beim Freigeben")
        return False


async def switch_sperren() -> bool:
    """Lock Nintendo Switch by setting daily time limit to 0."""
    if USE_MOCK:
        from adapters.mock import mock_switch_sperren
        return mock_switch_sperren()

    if not NINTENDO_TOKEN:
        logger.warning("Nintendo: Token nicht konfiguriert")
        return False
    if not _LIBRARY_AVAILABLE:
        logger.warning("Nintendo: Library nicht verfügbar")
        return False
    try:
        ok = await _set_playtime(0)
        if ok:
            logger.info("Nintendo: Switch gesperrt")
        return ok
    except Exception:
        logger.exception("Nintendo: Fehler beim Sperren")
        return False
