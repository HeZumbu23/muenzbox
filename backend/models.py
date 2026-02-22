from pydantic import BaseModel
from typing import Optional


class ChildPublic(BaseModel):
    id: int
    name: str
    switch_coins: int
    tv_coins: int


class TimeSlot(BaseModel):
    von: str  # "HH:MM"
    bis: str  # "HH:MM"


class ChildStatus(BaseModel):
    id: int
    name: str
    switch_coins: int
    switch_coins_weekly: int
    switch_coins_max: int
    tv_coins: int
    tv_coins_weekly: int
    tv_coins_max: int
    allowed_periods: list[TimeSlot]
    weekend_periods: list[TimeSlot]
    is_weekend_or_holiday: bool = False


_DEFAULT_PERIODS = [TimeSlot(von="08:00", bis="20:00")]


class ChildCreate(BaseModel):
    name: str
    pin: str
    switch_coins: int = 0
    switch_coins_weekly: int = 2
    switch_coins_max: int = 10
    tv_coins: int = 0
    tv_coins_weekly: int = 2
    tv_coins_max: int = 10
    allowed_periods: list[TimeSlot] = _DEFAULT_PERIODS
    weekend_periods: list[TimeSlot] = _DEFAULT_PERIODS


class ChildUpdate(BaseModel):
    name: Optional[str] = None
    pin: Optional[str] = None
    switch_coins: Optional[int] = None
    switch_coins_weekly: Optional[int] = None
    switch_coins_max: Optional[int] = None
    tv_coins: Optional[int] = None
    tv_coins_weekly: Optional[int] = None
    tv_coins_max: Optional[int] = None
    allowed_periods: Optional[list[TimeSlot]] = None
    weekend_periods: Optional[list[TimeSlot]] = None


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
