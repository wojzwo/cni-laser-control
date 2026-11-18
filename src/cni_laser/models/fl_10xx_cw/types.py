"""Validated public values and serial transaction results for FL-10xx-CW."""

from __future__ import annotations

from enum import IntEnum
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

POWER_MIN = 1
POWER_MAX = 100

SerialPortName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ControlState(IntEnum):
    """Software control register, not measured optical emission."""

    OFF = 0
    ON = 1


class PowerSetting(BaseModel):
    """Controller current/power setting, not calibrated optical watts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Annotated[StrictInt, Field(ge=POWER_MIN, le=POWER_MAX)]

    def __int__(self) -> int:
        return self.value


ValueT = TypeVar("ValueT")


class Transaction(BaseModel, Generic[ValueT]):
    """Raw exchange and validated optional decoded register value."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    request: bytes
    response: bytes
    value: ValueT | None = None
