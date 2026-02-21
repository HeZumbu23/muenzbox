"""
Zentraler Mock-Zustand für Simulations-Modus.
Wird von mikrotik_direct und nintendo importiert wenn USE_MOCK_ADAPTERS=true.
"""
import logging
from datetime import datetime

logger = logging.getLogger("adapters.mock")

# Simulierter Gerätezustand
_state: dict = {
    "tv_unlocked": False,
    "switch_minutes": 0,  # 0 = gesperrt
    "log": [],            # Protokoll der letzten Aktionen
}

MAX_LOG = 20


def _log(msg: str):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg}
    _state["log"].insert(0, entry)
    if len(_state["log"]) > MAX_LOG:
        _state["log"].pop()
    logger.info("[MOCK] %s", msg)


# --- TV ---

def mock_tv_freigeben() -> bool:
    _state["tv_unlocked"] = True
    _log("TV freigegeben ✅")
    return True


def mock_tv_sperren() -> bool:
    _state["tv_unlocked"] = False
    _log("TV gesperrt 🔒")
    return True


def mock_tv_status() -> bool:
    return _state["tv_unlocked"]


# --- Switch ---

def mock_switch_freigeben(minutes: int) -> bool:
    _state["switch_minutes"] = minutes
    _log(f"Switch freigegeben für {minutes} Minuten ✅")
    return True


def mock_switch_sperren() -> bool:
    _state["switch_minutes"] = 0
    _log("Switch gesperrt 🔒")
    return True


def get_mock_status() -> dict:
    return {
        "tv_unlocked": _state["tv_unlocked"],
        "switch_minutes": _state["switch_minutes"],
        "switch_unlocked": _state["switch_minutes"] > 0,
        "log": list(_state["log"]),
    }
