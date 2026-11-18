"""RS-232 frames for the CNI FL-10xx-CW controller family.

Protocol behavior has been verified on FL-1064-CW-20W.
"""

from enum import IntEnum

from .types import POWER_MAX, POWER_MIN, ControlState

BAUD_RATE = 115200
REQUEST_START = 0x53
RESPONSE_START = 0x41
FRAME_END = 0x0D
FRAME_SIZE = 10
ACK_SIZE = 7
DATA_SIZE = 4
DATA_START = 4
DATA_END = DATA_START + DATA_SIZE
CHECKSUM_INDEX = FRAME_SIZE - 2
CHECKSUM_MASK = 0xFF

ACK_OK = bytes.fromhex("41 07 4F 4B 21 03 0D")
ACK_ERROR = bytes.fromhex("41 07 45 52 52 31 0D")


class Channel(IntEnum):
    CONTROL = 0x00
    POWER = 0x01


class Command(IntEnum):
    GET = 0x00
    SET = 0x01


def checksum(data: bytes) -> int:
    """Sum bytes modulo 256; this is not a CRC."""
    return sum(data) & CHECKSUM_MASK


def _encode(channel: Channel, command: Command, value: int) -> bytes:
    body = bytes((REQUEST_START, FRAME_SIZE, channel, command)) + value.to_bytes(
        DATA_SIZE, byteorder="big"
    )
    return body + bytes((checksum(body), FRAME_END))


def encode_get(channel: Channel) -> bytes:
    """Encode a read request with a zero-filled data field."""
    return _encode(Channel(channel), Command.GET, 0)


def encode_set(channel: Channel, value: int) -> bytes:
    """Encode a validated controller-state or power-setting request."""
    channel = Channel(channel)
    if type(value) is not int:
        raise ValueError("SET value must be an integer")
    if channel == Channel.CONTROL and value not in (ControlState.OFF.value, ControlState.ON.value):
        raise ValueError("Control state must be 0 or 1")
    if channel == Channel.POWER and not POWER_MIN <= value <= POWER_MAX:
        raise ValueError(f"Power setting must be {POWER_MIN}..{POWER_MAX}")
    return _encode(channel, Command.SET, value)


def decode_get(response: bytes, channel: Channel) -> int:
    """Validate an observed CNI GET response and return its 32-bit value."""
    channel = Channel(channel)
    if (
        len(response) != FRAME_SIZE
        or response[0] != RESPONSE_START
        or response[1] != FRAME_SIZE
        or response[2] != channel
        or response[3] != Command.GET
        or response[-1] != FRAME_END
    ):
        raise ValueError(f"Unexpected GET response: {response.hex(' ').upper()}")
    if checksum(response[:CHECKSUM_INDEX]) != response[CHECKSUM_INDEX]:
        raise ValueError(f"Invalid GET checksum: {response.hex(' ').upper()}")
    return int.from_bytes(response[DATA_START:DATA_END], byteorder="big")


def validate_set_ack(response: bytes) -> None:
    """Validate an exact 7-byte ACK from the device.

    The manual's 9-byte SET response diagram conflicts with the observed
    7-byte frames. Both known 7-byte responses contain a valid byte-sum
    checksum; compare the complete documented responses exactly.
    """
    if response == ACK_ERROR:
        raise RuntimeError("CNI controller rejected SET command (ERR1)")
    if response != ACK_OK:
        raise RuntimeError(f"Unexpected SET acknowledgment: {response.hex(' ').upper()}")
