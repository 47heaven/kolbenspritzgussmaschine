from __future__ import annotations

import json
from typing import Any


def encode_message(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line: bytes | str) -> dict[str, Any]:
    text = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
    return json.loads(text.strip())


def ping_command() -> dict[str, Any]:
    return {"type": "ping"}


def status_command() -> dict[str, Any]:
    return {"type": "get_status"}


def set_mode_command(mode: str) -> dict[str, Any]:
    return {"type": "set_mode", "mode": mode}


def acknowledge_fault_command() -> dict[str, Any]:
    return {"type": "ack_fault"}


def all_outputs_off_command() -> dict[str, Any]:
    return {"type": "all_outputs_off"}


def set_setpoint_command(value_c: float) -> dict[str, Any]:
    return {"type": "set_setpoint", "value_c": value_c}


def set_overtemperature_limit_command(value_c: float) -> dict[str, Any]:
    return {"type": "set_overtemperature_limit", "value_c": value_c}


def set_heating_command(enabled: bool) -> dict[str, Any]:
    return {"type": "set_heating", "enabled": enabled}


def set_fan_command(enabled: bool) -> dict[str, Any]:
    return {"type": "set_fan", "enabled": enabled}


def set_valve_command(enabled: bool) -> dict[str, Any]:
    return {"type": "set_valve", "enabled": enabled}


def heater_test_command(duration_s: float) -> dict[str, Any]:
    return {"type": "heater_test", "duration_s": duration_s}


def set_pid_command(kp: float, ki: float, kd: float, setpoint_c: float) -> dict[str, Any]:
    return {"type": "set_pid", "kp": kp, "ki": ki, "kd": kd, "setpoint_c": setpoint_c}
