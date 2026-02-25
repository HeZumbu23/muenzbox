"""
Adapter dispatcher: routes TV control calls to the correct hardware adapter
based on the device's control_type ("mikrotik" or "fritzbox").
"""
from adapters import mikrotik_direct, fritzbox


async def tv_freigeben(control_type: str, identifier: str) -> bool:
    if control_type == "fritzbox":
        return await fritzbox.tv_freigeben(identifier)
    return await mikrotik_direct.tv_freigeben(identifier)


async def tv_sperren(control_type: str, identifier: str) -> bool:
    if control_type == "fritzbox":
        return await fritzbox.tv_sperren(identifier)
    return await mikrotik_direct.tv_sperren(identifier)
