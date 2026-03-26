from __future__ import annotations

from dataclasses import dataclass
from random import uniform

from .config import MachineConfig
from .interfaces import FanOutput, HeaterOutput, MachineHardware, TemperatureSensor, ValveOutput


@dataclass(slots=True)
class SimulatedThermalPlant:
    ambient_temperature_c: float = 22.0
    process_temperature_c: float = 22.0
    heater_percent: float = 0.0
    fan_enabled: bool = False
    valve_enabled: bool = False
    heater_gain: float = 7.0
    passive_cooling_gain: float = 0.018
    fan_cooling_gain: float = 0.045
    valve_heat_loss_gain: float = 0.015
    sensor_noise_c: float = 0.15

    def advance(self, dt: float) -> None:
        heating = (self.heater_percent / 100.0) * self.heater_gain
        passive_cooling = (self.process_temperature_c - self.ambient_temperature_c) * self.passive_cooling_gain
        fan_cooling = self.fan_cooling_gain if self.fan_enabled else 0.0
        valve_heat_loss = self.valve_heat_loss_gain if self.valve_enabled else 0.0
        self.process_temperature_c += (heating - passive_cooling - fan_cooling - valve_heat_loss) * dt


@dataclass(slots=True)
class SimulatedTemperatureSensor(TemperatureSensor):
    plant: SimulatedThermalPlant

    def read_temperature(self) -> float:
        return self.plant.process_temperature_c + uniform(-self.plant.sensor_noise_c, self.plant.sensor_noise_c)


@dataclass(slots=True)
class SimulatedHeaterOutput(HeaterOutput):
    plant: SimulatedThermalPlant

    def set_power_percent(self, value: float) -> None:
        self.plant.heater_percent = max(0.0, min(100.0, value))

    def disable(self) -> None:
        self.plant.heater_percent = 0.0


@dataclass(slots=True)
class SimulatedFanOutput(FanOutput):
    plant: SimulatedThermalPlant

    def set_enabled(self, enabled: bool) -> None:
        self.plant.fan_enabled = enabled

    def disable(self) -> None:
        self.plant.fan_enabled = False


@dataclass(slots=True)
class SimulatedValveOutput(ValveOutput):
    plant: SimulatedThermalPlant

    def set_enabled(self, enabled: bool) -> None:
        self.plant.valve_enabled = enabled

    def disable(self) -> None:
        self.plant.valve_enabled = False


def build_simulated_machine(config: MachineConfig) -> tuple[SimulatedThermalPlant, MachineHardware]:
    plant = SimulatedThermalPlant(process_temperature_c=22.0)
    hardware = MachineHardware(
        sensor=SimulatedTemperatureSensor(plant),
        heater=SimulatedHeaterOutput(plant),
        fan=SimulatedFanOutput(plant),
        valve=SimulatedValveOutput(plant),
    )
    return plant, hardware
