"""
Nintendo Switch Parental Controls Adapter.
Uses the pynintendoparental library to control daily play time limits.

Session start: Set daily limit to coins * 30 minutes
Session end:   Set daily limit to 0 (blocks play)
"""
import os
import logging

logger = logging.getLogger(__name__)

NINTENDO_TOKEN = os.getenv("NINTENDO_TOKEN", "")

try:
    from pynintendoparental import NintendoParental

    _LIBRARY_AVAILABLE = True
except ImportError:
    _NINTENDO_LIBRARY_AVAILABLE = False
    logger.warning("pynintendoparental nicht installiert – Nintendo-Integration deaktiviert")
    _LIBRARY_AVAILABLE = False


async def switch_freigeben(minutes: int = 30) -> bool:
    """
    Unlock Nintendo Switch by setting daily time limit to `minutes`.
    """
    if not NINTENDO_TOKEN:
        logger.warning("Nintendo: Token nicht konfiguriert, simuliere Freigabe")
        return True
    if not _LIBRARY_AVAILABLE:
        logger.warning("Nintendo: Library nicht verfügbar, simuliere Freigabe")
        return True
    try:
        parental = NintendoParental(NINTENDO_TOKEN)
        await parental.update()
        devices = parental.devices
        if not devices:
            logger.error("Nintendo: Keine Geräte gefunden")
            return False
        device = list(devices.values())[0]
        await device.set_max_daily_playtime(minutes)
        logger.info("Nintendo: Switch freigegeben für %d Minuten", minutes)
        return True
    except Exception as e:
        logger.error("Nintendo: Fehler beim Freigeben: %s", e)
        return False


async def switch_sperren() -> bool:
    """
    Lock Nintendo Switch by setting daily time limit to 0.
    """
    if not NINTENDO_TOKEN:
        logger.warning("Nintendo: Token nicht konfiguriert, simuliere Sperrung")
        return True
    if not _LIBRARY_AVAILABLE:
        logger.warning("Nintendo: Library nicht verfügbar, simuliere Sperrung")
        return True
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
    except Exception as e:
        logger.error("Nintendo: Fehler beim Sperren: %s", e)
        return False
