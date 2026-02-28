"""
Adapter dispatcher: routes TV control calls to the correct hardware adapter
based on the device's control_type ("fritzbox" or "mikrotik").
Config dict contains per-device credentials stored in the devices.config column.
"""
from adapters import mikrotik_direct, fritzbox


async def tv_freigeben(control_type: str, identifier: str, config: dict = {}) -> bool:
    if control_type == "fritzbox":
        return await fritzbox.tv_freigeben(identifier, config)
    if control_type == "mikrotik":
        return await mikrotik_direct.tv_freigeben(identifier, config)
    return False  # schedule_only / none


async def tv_sperren(control_type: str, identifier: str, config: dict = {}) -> bool:
    if control_type == "fritzbox":
        return await fritzbox.tv_sperren(identifier, config)
    if control_type == "mikrotik":
        return await mikrotik_direct.tv_sperren(identifier, config)
    return False  # schedule_only / none
