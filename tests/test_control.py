"""Offline controller and single-CLI tests without physical laser hardware."""

from __future__ import annotations

from typing import Self

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from cni_laser import ControlState, FL10xxCW, PowerSetting, Transaction
from cni_laser.cli import cli, command_request, main
from cni_laser.models.fl_10xx_cw import DEFAULT_PORT
from cni_laser.models.fl_10xx_cw.protocol import ACK_ERROR, ACK_OK


def test_model_exports_default_port() -> None:
    assert DEFAULT_PORT == "/dev/ttyUSB0"


class FakeConnection:
    def __init__(self, response: bytes) -> None:
        self.buffer = bytearray(response)
        self.writes: list[bytes] = []

    def reset_input_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)

    def flush(self) -> None:
        pass

    def read(self, size: int) -> bytes:
        part = bytes(self.buffer[:size])
        del self.buffer[:size]
        return part


def test_controller_get_state() -> None:
    fake = FakeConnection(bytes.fromhex("41 0A 00 00 00 00 00 00 4B 0D"))
    result = FL10xxCW(connection=fake).get_state()
    assert result.value is ControlState.OFF
    assert fake.writes == [bytes.fromhex("53 0A 00 00 00 00 00 00 5D 0D")]


def test_controller_get_power() -> None:
    fake = FakeConnection(bytes.fromhex("41 0A 01 00 00 00 00 02 4E 0D"))
    result = FL10xxCW(connection=fake).get_power()
    assert isinstance(result.value, PowerSetting)
    assert result.value.value == 2


def test_controller_set_power() -> None:
    fake = FakeConnection(ACK_OK)
    result = FL10xxCW(connection=fake).set_power(1)
    assert result.response == ACK_OK
    assert fake.writes == [bytes.fromhex("53 0A 01 01 00 00 00 01 60 0D")]


def test_controller_accepts_typed_power_setting() -> None:
    fake = FakeConnection(ACK_OK)
    result = FL10xxCW(connection=fake).set_power(PowerSetting(value=2))
    assert result.response == ACK_OK
    assert fake.writes == [bytes.fromhex("53 0A 01 01 00 00 00 02 61 0D")]


def test_controller_off_and_on() -> None:
    off = FakeConnection(ACK_OK)
    on = FakeConnection(ACK_OK)
    FL10xxCW(connection=off).off()
    FL10xxCW(connection=on).on()
    assert off.writes == [bytes.fromhex("53 0A 00 01 00 00 00 00 5E 0D")]
    assert on.writes == [bytes.fromhex("53 0A 00 01 00 00 00 01 5F 0D")]


def test_controller_rejects_error_ack() -> None:
    with pytest.raises(RuntimeError, match="rejected"):
        FL10xxCW(connection=FakeConnection(ACK_ERROR)).off()


def test_controller_rejects_missing_reply() -> None:
    with pytest.raises(TimeoutError):
        FL10xxCW(connection=FakeConnection(b"")).get_state()


def test_preview_does_not_open_device(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("Preview must not open serial hardware")

    monkeypatch.setattr("cni_laser.cli.FL10xxCW", forbid_open)
    assert main(["state"]) == 0
    assert main(["set-power", "1"]) == 0
    assert main(["on"]) == 0


def test_on_refuses_noninteractive_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    class NonInteractiveInput:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr("cni_laser.cli.sys.stdin", NonInteractiveInput())
    assert main(["--execute", "on"]) == 2


@pytest.mark.parametrize("answer", ["", "no", "wrong"])
def test_on_confirmation_cancelled(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    class InteractiveInput:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("cni_laser.cli.sys.stdin", InteractiveInput())
    monkeypatch.setattr("cni_laser.cli.click.confirm", lambda *args, **kwargs: answer == "yes")
    assert main(["--execute", "on"]) == 2


def test_cli_state_uses_controller(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeLaser:
        def __init__(self, port: str) -> None:
            assert port == "/dev/ttyUSB0"

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def get_state(self) -> Transaction:
            return Transaction[ControlState](
                request=bytes.fromhex("53 0A 00 00 00 00 00 00 5D 0D"),
                response=bytes.fromhex("41 0A 00 00 00 00 00 00 4B 0D"),
                value=ControlState.OFF,
            )

    monkeypatch.setattr("cni_laser.cli.FL10xxCW", FakeLaser)
    assert main(["--execute", "state"]) == 0
    output = capsys.readouterr().out
    assert "Control register: 0" in output
    assert "RX: 41 0A 00 00 00 00 00 00 4B 0D" in output


def test_command_request_mapping() -> None:
    assert command_request("power") == bytes.fromhex("53 0A 01 00 00 00 00 00 5E 0D")
    assert command_request("set-power", 3) == bytes.fromhex("53 0A 01 01 00 00 00 03 62 0D")
    assert command_request("off") == bytes.fromhex("53 0A 00 01 00 00 00 00 5E 0D")
    assert command_request("on") == bytes.fromhex("53 0A 00 01 00 00 00 01 5F 0D")


def test_controller_rejects_invalid_state_readback() -> None:
    fake = FakeConnection(bytes.fromhex("41 0A 00 00 00 00 00 02 4D 0D"))
    with pytest.raises(ValueError):
        FL10xxCW(connection=fake).get_state()


def test_controller_rejects_invalid_power_readback() -> None:
    fake = FakeConnection(bytes.fromhex("41 0A 01 00 00 00 00 00 4C 0D"))
    with pytest.raises(ValidationError):
        FL10xxCW(connection=fake).get_power()


def test_invalid_state_does_not_transmit() -> None:
    fake = FakeConnection(ACK_OK)
    with pytest.raises(TypeError, match="ControlState"):
        FL10xxCW(connection=fake).set_state(1)  # type: ignore[arg-type]
    assert fake.writes == []


def test_invalid_power_does_not_transmit() -> None:
    fake = FakeConnection(ACK_OK)
    with pytest.raises(ValidationError):
        FL10xxCW(connection=fake).set_power(True)
    assert fake.writes == []


def test_cli_list_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    class Port:
        device = "/dev/ttyUSB0"
        description = "USB-Serial Controller"
        vid = 0x067B
        pid = 0x23A3

        def __lt__(self, other: object) -> bool:
            return False

    monkeypatch.setattr("cni_laser.cli.list_ports.comports", lambda: [Port()])
    result = CliRunner().invoke(cli, ["ports"])
    assert result.exit_code == 0
    assert "/dev/ttyUSB0" in result.output
    assert "067B:23A3" in result.output


def test_cli_rejects_invalid_power_without_opening_port() -> None:
    result = CliRunner().invoke(cli, ["set-power", "101"])
    assert result.exit_code == 2
    assert "101" in result.output


def test_cli_lists_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for action in ("ports", "state", "power", "set-power", "off", "on"):
        assert action in result.output


def test_serial_port_validation() -> None:
    from pydantic import ValidationError

    from cni_laser import SerialPortName

    assert SerialPortName is not None
    with pytest.raises(ValidationError):
        FL10xxCW(port="  ")
    with pytest.raises(ValueError, match="finite"):
        FL10xxCW(timeout=float("nan"))
