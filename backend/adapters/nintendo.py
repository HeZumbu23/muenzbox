"""
Nintendo Switch Parental Controls Adapter.
Uses the pynintendoparental library to control daily play time limits.

Session start: add_extra_time(minutes) – wie "Weiter verlängern" in der App,
               gibt exakt coins*30 Min extra unabhängig von bisheriger Spielzeit
Session end:   update_max_daily_playtime(0) – setzt Tageslimit auf 0 (sperrt)

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
    from pynintendoauth.exceptions import HttpException as NintendoHttpException
    _LIBRARY_AVAILABLE = True
except ImportError:
    NintendoHttpException = None
    _LIBRARY_AVAILABLE = False
    logger.warning("pynintendoparental nicht installiert – Nintendo-Integration deaktiviert")


async def _get_first_device():
    """Authenticate and return (http_session, device). Caller must close session."""
    http_session = aiohttp.ClientSession()
    auth = Authenticator(NINTENDO_TOKEN, http_session)
    await auth.async_complete_login(use_session_token=True)
    parental = await NintendoParental.create(
        auth, timezone=NINTENDO_TZ, lang=NINTENDO_LANG
    )
    devices = parental.devices
    if not devices:
        await http_session.close()
        logger.error(
            "Nintendo: Keine Geräte gefunden – Token korrekt? "
            "Gerät in Kindersicherungs-App registriert?"
        )
        return None, None
    return http_session, list(devices.values())[0]


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
        session, device = await _get_first_device()
        if device is None:
            return False
        async with session:
            await device.add_extra_time(minutes)
        logger.info("Nintendo: Switch freigegeben für %d Minuten (extra time)", minutes)
        return True
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
        session, device = await _get_first_device()
        if device is None:
            return False
        async with session:
            await device.update_max_daily_playtime(0)
        logger.info("Nintendo: Switch gesperrt")
        return True
    except Exception as e:
        if NintendoHttpException and isinstance(e, NintendoHttpException) and e.status == 409:
            logger.warning("Nintendo: Switch bereits gesperrt (409 Conflict) – wird als Erfolg gewertet")
            return True
        logger.exception("Nintendo: Fehler beim Sperren")
        return False
