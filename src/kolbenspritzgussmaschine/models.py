from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import OperatingMode


class ErrorCode(str, Enum):
    NONE = "none"
    SENSOR_FAULT = "sensor_fault"
    TEMPERATURE_OUT_OF_RANGE = "temperature_out_of_range"
    OVERTEMPERATURE = "overtemperature"
    COMMUNICATION_TIMEOUT = "communication_timeout"
    CONTROLLER_TIMEOUT = "controller_timeout"
    INVALID_STATE = "invalid_state"
    COMMAND_REJECTED = "command_rejected"


@dataclass(slots=True)
class FaultState:
    code: ErrorCode
    message: str


@dataclass(slots=True)
class MachineStatus:
    timestamp: float
    temperature_c: float | None
    setpoint_c: float
    heater_output_percent: float
    heating_enabled: bool
    fan_enabled: bool
    valve_enabled: bool
    fault_code: ErrorCode = ErrorCode.NONE
    fault_message: str = ""
    mode: OperatingMode = OperatingMode.OFF
    sensor_ok: bool = False
    communication_ok: bool = True
    heater_on: bool = False
    fan_auto_active: bool = False
    overtemperature_limit_c: float = 250.0
    test_seconds_remaining: float = 0.0
