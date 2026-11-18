"""CNI FL-10xx-CW laser driver using pyserial directly.

Only FL-1064-CW-20W has been hardware-verified.
"""

from __future__ import annotations

from math import isfinite
from types import TracebackType
from typing import Protocol, Self

import serial
from pydantic import TypeAdapter

from .protocol import (
    ACK_SIZE,
    BAUD_RATE,
    FRAME_SIZE,
    Channel,
    decode_get,
    encode_get,
    encode_set,
    validate_set_ack,
)
from .types import ControlState, PowerSetting, SerialPortName, Transaction

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_TIMEOUT = 2.0
_PORT_ADAPTER = TypeAdapter(SerialPortName)


class _SerialConnection(Protocol):
    """Minimal I/O contract required from an injected serial connection."""

    def reset_input_buffer(self) -> None: ...

    def write(self, data: bytes, /) -> int | None: ...

    def flush(self) -> None: ...

    def read(self, size: int) -> bytes: ...


class FL10xxCW:
    """RS-232 controller. Software readback is not optical emission feedback.

    Use as a context manager. An optional injected connection permits offline tests
    and caller-managed serial I/O without an extra transport abstraction.
    """

    def __init__(
        self,
        port: SerialPortName = DEFAULT_PORT,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        connection: _SerialConnection | None = None,
    ) -> None:
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("Timeout must be a positive finite number")
        validated_port = _PORT_ADAPTER.validate_python(port)
        self._owned_serial: serial.Serial | None = None
        if connection is None:
            device = serial.Serial(
                port=None,
                baudrate=BAUD_RATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
                write_timeout=timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            device.port = validated_port
            device.dtr = False
            device.rts = False
            self._owned_serial = device
            self._serial: _SerialConnection = device
        else:
            self._serial = connection

    def __enter__(self) -> Self:
        if self._owned_serial is not None:
            self._owned_serial.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._owned_serial is not None:
            self._owned_serial.close()

    def _exchange(self, request: bytes, expected_size: int) -> bytes:
        self._serial.reset_input_buffer()
        written = self._serial.write(request)
        if written != len(request):
            raise OSError(f"Partial serial write: {written}/{len(request)} bytes")
        self._serial.flush()
        response = self._serial.read(expected_size)
        if len(response) != expected_size:
            raise TimeoutError(
                f"Expected {expected_size} response bytes, received {len(response)}: "
                f"{response.hex(' ').upper()}"
            )
        return response

    def _read_register(self, channel: Channel) -> tuple[bytes, bytes, int]:
        request = encode_get(channel)
        response = self._exchange(request, FRAME_SIZE)
        return request, response, decode_get(response, channel)

    def _set_register(self, channel: Channel, value: int) -> Transaction[None]:
        request = encode_set(channel, value)
        response = self._exchange(request, ACK_SIZE)
        validate_set_ack(response)
        return Transaction[None](request=request, response=response)

    def get_state(self) -> Transaction[ControlState]:
        """Read the software control register, not measured optical emission."""
        request, response, value = self._read_register(Channel.CONTROL)
        return Transaction[ControlState](
            request=request, response=response, value=ControlState(value)
        )

    def get_power(self) -> Transaction[PowerSetting]:
        """Read the displayed setting, not calibrated optical power."""
        request, response, value = self._read_register(Channel.POWER)
        return Transaction[PowerSetting](
            request=request, response=response, value=PowerSetting(value=value)
        )

    def set_power(self, value: int | PowerSetting) -> Transaction[None]:
        """Set current/power percentage in the validated 1..100 range."""
        setting = value if isinstance(value, PowerSetting) else PowerSetting(value=value)
        return self._set_register(Channel.POWER, setting.value)

    def set_state(self, state: ControlState) -> Transaction[None]:
        """Request a software control state; not a safety-rated shutdown."""
        if not isinstance(state, ControlState):
            raise TypeError("State must be a ControlState value")
        return self._set_register(Channel.CONTROL, int(state))

    def on(self) -> Transaction[None]:
        """Request laser emission; hardware interlocks must remain independent."""
        return self.set_state(ControlState.ON)

    def off(self) -> Transaction[None]:
        """Request software OFF; not a safety-rated emergency shutdown."""
        return self.set_state(ControlState.OFF)
