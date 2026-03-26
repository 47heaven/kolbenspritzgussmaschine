try:
    from enum import Enum
    _MICROPYTHON_ENUM_FALLBACK = False
except ImportError:
    _MICROPYTHON_ENUM_FALLBACK = True
    class Enum:
        _value2member_map_ = None

        def __new__(cls, value):
            mapping = getattr(cls, "_value2member_map_", None)
            if mapping is not None and value in mapping:
                return mapping[value]
            self = object.__new__(cls)
            self._value_ = value
            return self

        @property
        def value(self):
            return self._value_

        def __str__(self):
            return str(self._value_)

        def __repr__(self):
            return str(self._value_)

        def __eq__(self, other):
            if isinstance(other, Enum):
                return self.value == other.value
            return self.value == other

        @classmethod
        def _finalize_members(cls):
            mapping = {}
            for key, value in list(cls.__dict__.items()):
                if key.startswith("_") or callable(value):
                    continue
                member = cls.__new__(cls, value)
                setattr(cls, key, member)
                mapping[value] = member
            cls._value2member_map_ = mapping

from .config import OperatingMode


if _MICROPYTHON_ENUM_FALLBACK:
    class ErrorCode(Enum):
        NONE = "none"
        SENSOR_FAULT = "sensor_fault"
        TEMPERATURE_OUT_OF_RANGE = "temperature_out_of_range"
        OVERTEMPERATURE = "overtemperature"
        COMMUNICATION_TIMEOUT = "communication_timeout"
        CONTROLLER_TIMEOUT = "controller_timeout"
        INVALID_STATE = "invalid_state"
        COMMAND_REJECTED = "command_rejected"
else:
    class ErrorCode(str, Enum):
        NONE = "none"
        SENSOR_FAULT = "sensor_fault"
        TEMPERATURE_OUT_OF_RANGE = "temperature_out_of_range"
        OVERTEMPERATURE = "overtemperature"
        COMMUNICATION_TIMEOUT = "communication_timeout"
        CONTROLLER_TIMEOUT = "controller_timeout"
        INVALID_STATE = "invalid_state"
        COMMAND_REJECTED = "command_rejected"


if getattr(ErrorCode, "_value2member_map_", None) is None:
    ErrorCode._finalize_members()


class FaultState:
    def __init__(self, code, message):
        self.code = code
        self.message = message


class MachineStatus:
    def __init__(
        self,
        timestamp,
        temperature_c,
        setpoint_c,
        heater_output_percent,
        heating_enabled,
        fan_enabled,
        valve_enabled,
        fault_code=ErrorCode.NONE,
        fault_message="",
        mode=OperatingMode.OFF,
        sensor_ok=False,
        communication_ok=True,
        heater_on=False,
        fan_auto_active=False,
        overtemperature_limit_c=250.0,
        test_seconds_remaining=0.0,
    ):
        self.timestamp = timestamp
        self.temperature_c = temperature_c
        self.setpoint_c = setpoint_c
        self.heater_output_percent = heater_output_percent
        self.heating_enabled = heating_enabled
        self.fan_enabled = fan_enabled
        self.valve_enabled = valve_enabled
        self.fault_code = fault_code
        self.fault_message = fault_message
        self.mode = mode
        self.sensor_ok = sensor_ok
        self.communication_ok = communication_ok
        self.heater_on = heater_on
        self.fan_auto_active = fan_auto_active
        self.overtemperature_limit_c = overtemperature_limit_c
        self.test_seconds_remaining = test_seconds_remaining
