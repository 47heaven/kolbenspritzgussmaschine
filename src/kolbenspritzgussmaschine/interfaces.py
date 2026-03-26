from __future__ import annotations

from dataclasses import dataclass
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
