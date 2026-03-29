from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from .pid_control import ActuatorProtocol, SensorProtocol


class TemperatureSensor(Protocol):
    def read_temperature(self) -> float:
        """Return the measured temperature in degree Celsius."""


class HeaterOutput(Protocol):
    def set_power_percent(self, value: float) -> None:
        """Apply heater power in the range 0..100 percent."""

    def disable(self) -> None:
        """Switch the heater output into a safe off state."""


class FanOutput(Protocol):
    def set_enabled(self, enabled: bool) -> None:
        """Switch the cooling fan on or off."""

    def disable(self) -> None:
        """Switch the fan into its configured safe off state."""


class ValveOutput(Protocol):
    def set_enabled(self, enabled: bool) -> None:
        """Switch the pneumatic valve on or off."""

    def disable(self) -> None:
        """Switch the valve into its configured safe off state."""


@dataclass(slots=True)
class MachineHardware:
    sensor: TemperatureSensor
    heater: HeaterOutput
    fan: FanOutput
    valve: ValveOutput


@dataclass(slots=True)
class TemperatureSensorAdapter(SensorProtocol):
    sensor: TemperatureSensor

    def read(self) -> float:
        return self.sensor.read_temperature()


@dataclass(slots=True)
class HeaterActuatorAdapter(ActuatorProtocol):
    heater: HeaterOutput

    def write(self, value: float) -> None:
        self.heater.set_power_percent(value)

    def stop(self) -> None:
        self.heater.disable()


@dataclass(slots=True)
class RampingHeaterActuatorAdapter(ActuatorProtocol):
    heater: HeaterOutput
    ramp_up_seconds: float = 10.0
    _ramp_started_at: float | None = None

    def write(self, value: float) -> float:
        requested = max(0.0, min(100.0, value))
        if requested <= 0.0:
            self._ramp_started_at = None
            self.heater.set_power_percent(0.0)
            return 0.0

        now = monotonic()
        if self._ramp_started_at is None:
            self._ramp_started_at = now

        if self.ramp_up_seconds <= 0.0:
            applied = requested
        else:
            elapsed = max(0.0, now - self._ramp_started_at)
            ramp_limit = min(100.0, (elapsed / self.ramp_up_seconds) * 100.0)
            applied = min(requested, ramp_limit)

        self.heater.set_power_percent(applied)
        return applied

    def stop(self) -> None:
        self._ramp_started_at = None
        self.heater.disable()
