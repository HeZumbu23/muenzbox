"""
Nintendo Switch Parental Controls – Python bridge for Python.NET.

Called from NintendoAdapter.cs via Python.Runtime (pythonnet).
Wraps the async pynintendoparental library with synchronous entry points
so the .NET side can call them without managing Python's event loop.

Functions exported to .NET:
  switch_freigeben_sync(token, tz, lang, minutes) -> bool
  switch_sperren_sync(token, tz, lang)            -> bool
"""

import asyncio
import aiohttp


# ── Async implementation ───────────────────────────────────────────────────

async def _freigeben_async(token: str, tz: str, lang: str, minutes: int, timeout_seconds: int) -> bool:
    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator

    timeout = aiohttp.ClientTimeout(total=max(1, int(timeout_seconds)))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        auth = Authenticator(token, session)
        await auth.async_complete_login(use_session_token=True)
        parental = await NintendoParental.create(auth, timezone=tz, lang=lang)
        devices = parental.devices
        if not devices:
            raise RuntimeError("Keine Geräte gefunden – Token korrekt?")
        device = list(devices.values())[0]
        await device.add_extra_time(minutes)
    return True


async def _sperren_async(token: str, tz: str, lang: str, timeout_seconds: int) -> bool:
    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator

    # Import exception class if available
    try:
        from pynintendoauth.exceptions import HttpException as NintendoHttpException
    except ImportError:
        NintendoHttpException = None

    timeout = aiohttp.ClientTimeout(total=max(1, int(timeout_seconds)))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        auth = Authenticator(token, session)
        await auth.async_complete_login(use_session_token=True)
        parental = await NintendoParental.create(auth, timezone=tz, lang=lang)
        devices = parental.devices
        if not devices:
            raise RuntimeError("Keine Geräte gefunden – Token korrekt?")
        device = list(devices.values())[0]
        try:
            await device.update_max_daily_playtime(0)
        except Exception as e:
            if NintendoHttpException and isinstance(e, NintendoHttpException):
                status = getattr(e, "status", None)
                if status == 409:
                    print("[nintendo_bridge] Switch bereits gesperrt (409) – gilt als Erfolg")
                    return True
            raise
    return True


# ── Synchronous wrappers (called from .NET via Python.NET) ─────────────────

def switch_freigeben_sync(token, tz, lang, minutes, timeout_seconds=20) -> bool:
    """Unlock Nintendo Switch for `minutes` minutes."""
    try:
        return asyncio.run(asyncio.wait_for(
            _freigeben_async(str(token), str(tz), str(lang), int(minutes), int(timeout_seconds)),
            timeout=max(1, int(timeout_seconds))
        ))
    except Exception as e:
        raise RuntimeError(f"switch_freigeben_sync failed: {e}") from e


def switch_sperren_sync(token, tz, lang, timeout_seconds=20) -> bool:
    """Lock Nintendo Switch by setting daily limit to 0."""
    try:
        return asyncio.run(asyncio.wait_for(
            _sperren_async(str(token), str(tz), str(lang), int(timeout_seconds)),
            timeout=max(1, int(timeout_seconds))
        ))
    except Exception as e:
        raise RuntimeError(f"switch_sperren_sync failed: {e}") from e
