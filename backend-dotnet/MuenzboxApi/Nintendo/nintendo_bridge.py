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


# ── Async implementation ───────────────────────────────────────────────────

async def _freigeben_async(token: str, tz: str, lang: str, minutes: int) -> bool:
    import aiohttp
    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator

    async with aiohttp.ClientSession() as session:
        auth = Authenticator(token, session)
        await auth.async_complete_login(use_session_token=True)
        parental = await NintendoParental.create(auth, timezone=tz, lang=lang)
        devices = parental.devices
        if not devices:
            print("[nintendo_bridge] Keine Geräte gefunden – Token korrekt?")
            return False
        device = list(devices.values())[0]
        await device.add_extra_time(minutes)
    return True


async def _sperren_async(token: str, tz: str, lang: str) -> bool:
    import aiohttp
    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator

    # Import exception class if available
    try:
        from pynintendoauth.exceptions import HttpException as NintendoHttpException
    except ImportError:
        NintendoHttpException = None

    async with aiohttp.ClientSession() as session:
        auth = Authenticator(token, session)
        await auth.async_complete_login(use_session_token=True)
        parental = await NintendoParental.create(auth, timezone=tz, lang=lang)
        devices = parental.devices
        if not devices:
            print("[nintendo_bridge] Keine Geräte gefunden – Token korrekt?")
            return False
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

def switch_freigeben_sync(token, tz, lang, minutes) -> bool:
    """Unlock Nintendo Switch for `minutes` minutes."""
    try:
        return asyncio.run(_freigeben_async(str(token), str(tz), str(lang), int(minutes)))
    except Exception as e:
        print(f"[nintendo_bridge] switch_freigeben_sync error: {e}")
        return False


def switch_sperren_sync(token, tz, lang) -> bool:
    """Lock Nintendo Switch by setting daily limit to 0."""
    try:
        return asyncio.run(_sperren_async(str(token), str(tz), str(lang)))
    except Exception as e:
        print(f"[nintendo_bridge] switch_sperren_sync error: {e}")
        return False
