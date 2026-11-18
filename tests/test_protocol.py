"""Protocol fixtures from the manual and tested FL-1064-CW-20W communication."""

import pytest

from cni_laser.models.fl_10xx_cw.protocol import (
    ACK_ERROR,
    ACK_OK,
    Channel,
    checksum,
    decode_get,
    encode_get,
    encode_set,
    validate_set_ack,
)


@pytest.mark.parametrize(
    ("channel", "value", "hex_frame"),
    [
        (Channel.CONTROL, 0, "53 0A 00 01 00 00 00 00 5E 0D"),
        (Channel.CONTROL, 1, "53 0A 00 01 00 00 00 01 5F 0D"),
        (Channel.POWER, 1, "53 0A 01 01 00 00 00 01 60 0D"),
        (Channel.POWER, 100, "53 0A 01 01 00 00 00 64 C3 0D"),
    ],
)
def test_encode_set(channel: Channel, value: int, hex_frame: str) -> None:
    assert encode_set(channel, value) == bytes.fromhex(hex_frame)


@pytest.mark.parametrize(
    ("channel", "hex_frame"),
    [
        (Channel.CONTROL, "53 0A 00 00 00 00 00 00 5D 0D"),
        (Channel.POWER, "53 0A 01 00 00 00 00 00 5E 0D"),
    ],
)
def test_encode_get(channel: Channel, hex_frame: str) -> None:
    assert encode_get(channel) == bytes.fromhex(hex_frame)


@pytest.mark.parametrize(
    ("channel", "value", "hex_frame"),
    [
        (Channel.CONTROL, 0, "41 0A 00 00 00 00 00 00 4B 0D"),
        (Channel.CONTROL, 1, "41 0A 00 00 00 00 00 01 4C 0D"),
        (Channel.POWER, 1, "41 0A 01 00 00 00 00 01 4D 0D"),
        (Channel.POWER, 2, "41 0A 01 00 00 00 00 02 4E 0D"),
        (Channel.POWER, 3, "41 0A 01 00 00 00 00 03 4F 0D"),
    ],
)
def test_observed_get_replies(channel: Channel, value: int, hex_frame: str) -> None:
    assert decode_get(bytes.fromhex(hex_frame), channel) == value


def test_checksum_is_low_byte_of_sum() -> None:
    assert checksum(bytes.fromhex("FF 02")) == 1


@pytest.mark.parametrize("value", [-1, 2, True])
def test_control_value_validation(value: object) -> None:
    with pytest.raises(ValueError):
        encode_set(Channel.CONTROL, value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, 101, -10, 1.5])
def test_power_value_validation(value: object) -> None:
    with pytest.raises(ValueError):
        encode_set(Channel.POWER, value)  # type: ignore[arg-type]


def test_reject_undocumented_channel() -> None:
    with pytest.raises(ValueError):
        encode_get(0x02)  # type: ignore[arg-type]


def test_get_rejects_invalid_checksum() -> None:
    with pytest.raises(ValueError, match="checksum"):
        decode_get(bytes.fromhex("41 0A 00 00 00 00 00 00 00 0D"), Channel.CONTROL)


def test_get_rejects_other_channel() -> None:
    with pytest.raises(ValueError, match="Unexpected"):
        decode_get(bytes.fromhex("41 0A 01 00 00 00 00 01 4D 0D"), Channel.CONTROL)


def test_get_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="Unexpected"):
        decode_get(bytes.fromhex("41 07 4F 4B 21 03 0D"), Channel.CONTROL)


def test_set_acknowledgment() -> None:
    validate_set_ack(ACK_OK)
    with pytest.raises(RuntimeError, match="rejected"):
        validate_set_ack(ACK_ERROR)
    with pytest.raises(RuntimeError, match="Unexpected"):
        validate_set_ack(b"")
