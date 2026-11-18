"""Public Pydantic models and typed validation boundaries."""

import pytest
from pydantic import BaseModel, ValidationError

from cni_laser import ControlState, PowerSetting, Transaction


def test_control_state_is_integer_compatible() -> None:
    assert ControlState.OFF == 0
    assert ControlState.ON == 1


@pytest.mark.parametrize("value", [1, 2, 100])
def test_power_setting_accepts_valid_values(value: int) -> None:
    setting = PowerSetting(value=value)
    assert isinstance(setting, BaseModel)
    assert setting.value == value
    assert int(setting) == value
    assert setting.model_dump() == {"value": value}


@pytest.mark.parametrize("value", [0, 101, -1, 1.2, True, "5", None])
def test_power_setting_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValidationError):
        PowerSetting(value=value)  # type: ignore[arg-type]


def test_power_setting_forbids_unknown_fields_and_mutation() -> None:
    with pytest.raises(ValidationError):
        PowerSetting(value=1, unit="watts")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        PowerSetting(value=1).value = 2


def test_typed_transaction_validates_value() -> None:
    result = Transaction[PowerSetting](
        request=b"\x53", response=b"\x41", value=PowerSetting(value=2)
    )
    assert result.value is not None
    assert result.value.value == 2
    assert result.model_dump()["value"] == {"value": 2}

    with pytest.raises(ValidationError):
        Transaction[PowerSetting](
            request=b"",
            response=b"",
            value={"value": "2"},  # type: ignore[arg-type]
        )


def test_transaction_rejects_unknown_fields_and_mutation() -> None:
    result = Transaction[ControlState](request=b"", response=b"", value=ControlState.OFF)
    with pytest.raises(ValidationError):
        result.request = b"modified"
    with pytest.raises(ValidationError):
        Transaction[ControlState](
            request=b"",
            response=b"",
            value=ControlState.OFF,
            extra=1,  # type: ignore[call-arg]
        )
