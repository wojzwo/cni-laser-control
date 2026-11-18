# CNI Laser Control

Unofficial Python library and CLI for CNI laser controllers over RS-232.

**Hardware-tested:** CNI FL-1064-CW-20W with a Prolific PL2303GT USB–RS232 adapter on Linux/WSL2. Compatibility with other FL-10xx-CW models is unverified.

## Install

Python 3.11+ is required. From the repository root:

```bash
python -m pip install .
cni-laser --help
cni-laser ports
```

For development with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run pytest -q
uv run cni-laser --help
```

On WSL2, first attach the USB serial adapter using `usbipd` on Windows. The controller uses **115200 baud, 8N1** and binary packets. The default device is `/dev/ttyUSB0`; override it with `--port COM7` (Windows) or `--port /dev/ttyUSB1` (Linux).

## CLI

Commands **only show a preview** unless `--execute` is supplied **before** the subcommand:

```bash
cni-laser ports                 # List available serial ports
cni-laser state                 # Preview a read request (no I/O)
cni-laser --execute state       # Read software control register (0/1)
cni-laser --execute power       # Read displayed current/power setting
cni-laser --execute set-power 2 # Set displayed setting to 2 (range: 1–100)
cni-laser --execute off         # Request software OFF
cni-laser --execute on          # Request ON (interactive confirmation)
```

Each executed operation performs one request/response transaction and prints the received bytes in hexadecimal. Only one process can use a serial port at a time. `--version` prints the installed package version.

**Safety and disclaimer:** This software is provided **AS IS**, without warranty. It is not a safety-rated controller. `on` can enable invisible, high-power laser emission; `off`, `OK!` and the reported control register do not verify optical shutdown. Use independent interlocks and an emergency stop, and follow the manufacturer’s instructions.

## Python API

```python
from cni_laser import ControlState, FL10xxCW, PowerSetting, Transaction

with FL10xxCW("/dev/ttyUSB0") as laser:
    state: Transaction[ControlState] = laser.get_state()
    power: Transaction[PowerSetting] = laser.get_power()
    if state.value is not None and power.value is not None:
        print(state.value.name, power.value.value)
```

The model also provides `set_state(ControlState)`, `set_power(int | PowerSetting)`, `on()` and `off()`. Each method returns an immutable `Transaction[T]` with `.request`, `.response` and optional `.value`. The `PowerSetting` value is a validated Pydantic model, not a calibrated optical power measurement.

The protocol is documented in [docs/protocol.md](docs/protocol.md), including known discrepancies in the CNI manual. The manufacturer's individually supplied PDF is **not** redistributed. This is an independently implemented library and does not grant any rights to CNI documentation.

## Acknowledgments

Thanks to CNI Laser (Changchun New Industries Optoelectronics Tech. Co., Ltd.) for providing the technical documentation used as a reference for implementing the RS-232 communication protocol.

This is an independent, unofficial project and is not affiliated with or endorsed by CNI Laser.

