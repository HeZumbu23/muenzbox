from pydantic import BaseModel
from typing import Optional


class ChildPublic(BaseModel):
    id: int
    name: str
    switch_coins: int
    tv_coins: int


class ChildStatus(BaseModel):
    id: int
    name: str
    switch_coins: int
    switch_coins_weekly: int
    switch_coins_max: int
    tv_coins: int
    tv_coins_weekly: int
    tv_coins_max: int
    allowed_from: str
    allowed_until: str
    weekend_from: str
    weekend_until: str
    is_weekend_or_holiday: bool = False


class ChildCreate(BaseModel):
    name: str
    pin: str
    switch_coins: int = 0
    switch_coins_weekly: int = 2
    switch_coins_max: int = 10
    tv_coins: int = 0
    tv_coins_weekly: int = 2
    tv_coins_max: int = 10
    allowed_from: str = "08:00"
    allowed_until: str = "20:00"
    weekend_from: str = "08:00"
    weekend_until: str = "20:00"


class ChildUpdate(BaseModel):
    name: Optional[str] = None
    pin: Optional[str] = None
    switch_coins: Optional[int] = None
    switch_coins_weekly: Optional[int] = None
    switch_coins_max: Optional[int] = None
    tv_coins: Optional[int] = None
    tv_coins_weekly: Optional[int] = None
    tv_coins_max: Optional[int] = None
    allowed_from: Optional[str] = None
    allowed_until: Optional[str] = None
    weekend_from: Optional[str] = None
    weekend_until: Optional[str] = None


class PinVerify(BaseModel):
    pin: str


class SessionStart(BaseModel):
    child_id: int
    type: str  # "switch" or "tv"
    coins: int = 1


class SessionResponse(BaseModel):
    id: int
    child_id: int
    type: str
    started_at: str
    ends_at: str
    coins_used: int
    status: str
    hardware_ok: bool = True


class CoinAdjust(BaseModel):
    type: str  # "switch" or "tv"
    delta: int
    reason: str = "admin_adjust"


class AdminVerify(BaseModel):
    pin: str
