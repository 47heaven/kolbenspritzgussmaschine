from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from ..config import OperatingMode
from ..models import ErrorCode, MachineStatus
from .protocol import (
    acknowledge_fault_command,
    all_outputs_off_command,
    decode_message,
    encode_message,
    heater_test_command,
    ping_command,
    set_fan_command,
    set_heating_command,
    set_mode_command,
    set_overtemperature_limit_command,
    set_pid_command,
    set_setpoint_command,
    set_valve_command,
    status_command,
)

try:
    import serial  # type: ignore[import-not-found]
except ImportError:
    serial = None


class LineTransport(Protocol):
    def write(self, data: bytes) -> int:
        ...

    def readline(self) -> bytes:
        ...

    def close(self) -> None:
        ...


class SerialLineTransport:
    """USB-serial transport for Raspberry Pi <-> Pico communication."""

    def __init__(self, port: str, baudrate: int, timeout_s: float = 1.0) -> None:
        if serial is None:
            raise RuntimeError("pyserial is required for SerialLineTransport but is not installed.")
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout_s)

    def write(self, data: bytes) -> int:
        return int(self._serial.write(data))

    def readline(self) -> bytes:
        return bytes(self._serial.readline())

    def close(self) -> None:
        self._serial.close()


@dataclass(slots=True)
class MockLineTransport:
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    _buffer: bytes = b""

    def write(self, data: bytes) -> int:
        request = decode_message(data)
        response = self.handler(request)
        self._buffer = encode_message(response)
        return len(data)

    def readline(self) -> bytes:
        data = self._buffer
        self._buffer = b""
        return data

    def close(self) -> None:
        self._buffer = b""


class PicoControllerClient:
    def __init__(self, transport: LineTransport) -> None:
        self.transport = transport

    def close(self) -> None:
        self.transport.close()

    def _roundtrip(self, message: dict[str, Any]) -> dict[str, Any]:
        self.transport.write(encode_message(message))
        response = decode_message(self.transport.readline())
        if response.get("type") == "error":
            raise RuntimeError(response.get("message", "Unknown Pico error"))
        return response

    def ping(self) -> dict[str, Any]:
        return self._roundtrip(ping_command())

    def set_mode(self, mode: OperatingMode) -> dict[str, Any]:
        return self._roundtrip(set_mode_command(mode.value))

    def acknowledge_fault(self) -> dict[str, Any]:
        return self._roundtrip(acknowledge_fault_command())

    def all_outputs_off(self) -> dict[str, Any]:
        return self._roundtrip(all_outputs_off_command())

    def set_setpoint(self, value_c: float) -> dict[str, Any]:
        return self._roundtrip(set_setpoint_command(value_c))

    def set_overtemperature_limit(self, value_c: float) -> dict[str, Any]:
        return self._roundtrip(set_overtemperature_limit_command(value_c))

    def set_heating_enabled(self, enabled: bool) -> dict[str, Any]:
        return self._roundtrip(set_heating_command(enabled))

    def set_fan_enabled(self, enabled: bool) -> dict[str, Any]:
        return self._roundtrip(set_fan_command(enabled))

    def set_valve_enabled(self, enabled: bool) -> dict[str, Any]:
        return self._roundtrip(set_valve_command(enabled))

    def trigger_heater_test(self, duration_s: float) -> dict[str, Any]:
        return self._roundtrip(heater_test_command(duration_s))

    def set_pid_parameters(self, kp: float, ki: float, kd: float, setpoint_c: float) -> dict[str, Any]:
        return self._roundtrip(set_pid_command(kp, ki, kd, setpoint_c))

    def fetch_status(self) -> MachineStatus:
        response = self._roundtrip(status_command())
        return MachineStatus(
            timestamp=float(response["timestamp"]),
            temperature_c=response.get("temperature_c"),
            setpoint_c=float(response["setpoint_c"]),
            heater_output_percent=float(response["heater_output_percent"]),
            heating_enabled=bool(response["heating_enabled"]),
            fan_enabled=bool(response["fan_enabled"]),
            valve_enabled=bool(response["valve_enabled"]),
            fault_code=ErrorCode(str(response.get("fault_code", ErrorCode.NONE.value))),
            fault_message=str(response.get("fault_message", "")),
            mode=OperatingMode(str(response.get("mode", OperatingMode.OFF.value))),
            sensor_ok=bool(response.get("sensor_ok", False)),
            communication_ok=bool(response.get("communication_ok", True)),
            heater_on=bool(response.get("heater_on", False)),
            fan_auto_active=bool(response.get("fan_auto_active", False)),
            overtemperature_limit_c=float(response.get("overtemperature_limit_c", 250.0)),
            test_seconds_remaining=float(response.get("test_seconds_remaining", 0.0)),
        )
