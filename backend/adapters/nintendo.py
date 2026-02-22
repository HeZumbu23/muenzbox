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

try:
    from pynintendoparental import NintendoParental
    _LIBRARY_AVAILABLE = True
except ImportError:
    _LIBRARY_AVAILABLE = False
    logger.warning("pynintendoparental nicht installiert – Nintendo-Integration deaktiviert")


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
        parental = NintendoParental(NINTENDO_TOKEN)
        await parental.update()
        devices = parental.devices
        if not devices:
            logger.error("Nintendo: Keine Geräte gefunden – Token korrekt? Gerät in Kindersicherungs-App registriert?")
            return False
        device = list(devices.values())[0]
        await device.set_max_daily_playtime(minutes)
        logger.info("Nintendo: Switch freigegeben für %d Minuten", minutes)
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
        parental = NintendoParental(NINTENDO_TOKEN)
        await parental.update()
        devices = parental.devices
        if not devices:
            logger.error("Nintendo: Keine Geräte gefunden")
            return False
        device = list(devices.values())[0]
        await device.set_max_daily_playtime(0)
        logger.info("Nintendo: Switch gesperrt")
        return True
    except Exception:
        logger.exception("Nintendo: Fehler beim Sperren")
        return False
