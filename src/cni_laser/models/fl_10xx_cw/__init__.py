"""FL-10xx-CW controller interface (tested on FL-1064-CW-20W)."""

from .laser import DEFAULT_PORT, FL10xxCW
from .types import ControlState, PowerSetting, SerialPortName, Transaction

__all__ = [
    "DEFAULT_PORT",
    "ControlState",
    "FL10xxCW",
    "PowerSetting",
    "SerialPortName",
    "Transaction",
]
