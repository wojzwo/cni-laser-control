"""Command-line interface for CNI FL-10xx-CW serial laser controllers."""

from __future__ import annotations

import sys
from typing import NamedTuple

import click
import serial
from serial.tools import list_ports

from .models.fl_10xx_cw import DEFAULT_PORT, ControlState, FL10xxCW, Transaction
from .models.fl_10xx_cw.protocol import Channel, encode_get, encode_set
from .models.fl_10xx_cw.types import POWER_MAX, POWER_MIN


class _Options(NamedTuple):
    port: str
    execute: bool


def command_request(action: str, power: int | None = None) -> bytes:
    """Build a frame for preview without opening a serial connection."""
    if action == "state":
        return encode_get(Channel.CONTROL)
    if action == "power":
        return encode_get(Channel.POWER)
    if action == "set-power" and power is not None:
        return encode_set(Channel.POWER, power)
    if action == "on":
        return encode_set(Channel.CONTROL, ControlState.ON.value)
    if action == "off":
        return encode_set(Channel.CONTROL, ControlState.OFF.value)
    raise ValueError(f"Unsupported command or missing value: {action}")


def _run(laser: FL10xxCW, action: str, power: int | None) -> Transaction:
    if action == "state":
        return laser.get_state()
    if action == "power":
        return laser.get_power()
    if action == "set-power" and power is not None:
        return laser.set_power(power)
    if action == "on":
        return laser.on()
    if action == "off":
        return laser.off()
    raise ValueError(f"Unsupported command or missing value: {action}")


def _perform(options: _Options, action: str, power: int | None = None) -> int:
    try:
        request = command_request(action, power)
        click.echo(
            f"TX ({'requested' if options.execute else 'preview'}): {request.hex(' ').upper()}"
        )
        if not options.execute:
            click.echo("Preview only; no serial connection opened. Add --execute to transmit.")
            return 0

        if action == "on":
            if not sys.stdin.isatty():
                raise click.UsageError("ON requires an interactive terminal")
            if not click.confirm("Enable laser emission?", default=False):
                click.echo("Cancelled; no command transmitted.")
                return 2

        with FL10xxCW(options.port) as laser:
            result = _run(laser, action, power)
        click.echo(f"RX: {result.response.hex(' ').upper()}")
        if result.value is None:
            click.echo("Controller ACK: OK! This does not verify optical output.")
        elif action == "state":
            click.echo(f"Control register: {int(result.value)}")
            click.echo("Control register is not independent optical emission feedback.")
        else:
            click.echo(f"Power setting: {int(result.value)}")
        return 0
    except (serial.SerialException, OSError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="cni-laser-control")
@click.option(
    "--port",
    default=DEFAULT_PORT,
    show_default=True,
    help="Serial port (e.g. /dev/ttyUSB0 or COM7).",
)
@click.option("--execute", is_flag=True, help="Transmit to the controller (otherwise preview).")
@click.pass_context
def cli(context: click.Context, port: str, execute: bool) -> None:
    """Unofficial CNI laser control over binary RS-232."""
    context.obj = _Options(port=port, execute=execute)


@cli.command()
def ports() -> None:
    """List serial ports without contacting the laser."""
    detected = sorted(list_ports.comports())
    if not detected:
        click.echo("No serial ports detected.")
    for device in detected:
        identity = (
            f" [{device.vid:04X}:{device.pid:04X}]"
            if device.vid is not None and device.pid is not None
            else ""
        )
        click.echo(f"{device.device}: {device.description}{identity}")


@cli.command()
@click.pass_obj
def state(options: _Options) -> int:
    """Read software control register (0/1), not optical emission."""
    return _perform(options, "state")


@cli.command()
@click.pass_obj
def power(options: _Options) -> int:
    """Read current/power setting (1..100), not calibrated watts."""
    return _perform(options, "power")


@cli.command("set-power")
@click.argument("value", type=click.IntRange(POWER_MIN, POWER_MAX))
@click.pass_obj
def set_power(options: _Options, value: int) -> int:
    """Set the controller's current/power setting (1..100)."""
    return _perform(options, "set-power", value)


@cli.command()
@click.pass_obj
def off(options: _Options) -> int:
    """Request software OFF; not an emergency stop."""
    return _perform(options, "off")


@cli.command()
@click.pass_obj
def on(options: _Options) -> int:
    """Request emission ON; requires an interactive confirmation."""
    return _perform(options, "on")


def main(argv: list[str] | None = None) -> int:
    """Console entry point with a numeric exit status."""
    try:
        result = cli.main(args=argv, prog_name="cni-laser", standalone_mode=False)
        return int(result or 0)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.Abort:
        click.echo("Cancelled; no command transmitted.", err=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
