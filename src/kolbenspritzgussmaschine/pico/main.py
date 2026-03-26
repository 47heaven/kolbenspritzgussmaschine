from __future__ import annotations

from ..config import MachineConfig, SensorElement, TemperatureSensorConfig
from .runtime import run_forever


def build_pico_config() -> MachineConfig:
    config = MachineConfig()
    config.sensor = TemperatureSensorConfig.for_element(SensorElement.PT100)
    config.sensor.wires = 2
    config.sensor.filter_frequency_hz = 50
    config.max31865_sck_pin = 18
    config.max31865_miso_pin = 16
    config.max31865_mosi_pin = 19
    config.max31865_cs_pin = 17
    config.heater.pin = 2
    config.fan.pin = 3
    config.valve.pin = 4
    config.heater.time_window_s = 2.0
    config.heater.control_period_s = 0.5
    config.control_interval_s = 0.5
    config.pid.sample_time = 0.5
    config.safety.overtemperature_c = 250.0
    # TODO: Validate PID tuning, overtemperature threshold and fan automation threshold on the real machine.
    return config


def main() -> None:
    run_forever(build_pico_config())


if __name__ == "__main__":
    main()
