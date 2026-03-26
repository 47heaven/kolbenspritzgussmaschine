from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RuntimeMode(str, Enum):
    SIMULATION = "simulation"
    SERIAL = "serial"


class OperatingMode(str, Enum):
    OFF = "off"
    TEST = "test"
    AUTO = "auto"
    FAULT = "fault"


class SensorElement(str, Enum):
    PT100 = "pt100"
    PT1000 = "pt1000"


@dataclass(slots=True)
class PidConfig:
    kp: float
    ki: float
    kd: float
    setpoint: float
    sample_time: float = 0.5
    output_limits: tuple[float | None, float | None] = (0.0, 100.0)
    starting_output: float = 0.0
    proportional_on_measurement: bool = False
    differential_on_measurement: bool = True


@dataclass(slots=True)
class TemperatureSensorConfig:
    element: SensorElement = SensorElement.PT100
    reference_resistor_ohms: float = 430.0
    nominal_resistance_ohms: float = 100.0
    wires: int = 2
    filter_frequency_hz: int = 50

    @classmethod
    def for_element(cls, element: SensorElement) -> "TemperatureSensorConfig":
        if element == SensorElement.PT1000:
            return cls(
                element=element,
                reference_resistor_ohms=4300.0,
                nominal_resistance_ohms=1000.0,
            )
        return cls(element=element)


@dataclass(slots=True)
class SafetyConfig:
    min_plausible_temp_c: float = 0.0
    max_plausible_temp_c: float = 320.0
    overtemperature_c: float = 250.0
    communication_timeout_s: float = 3.0
    controller_timeout_s: float = 1.5
    heater_test_duration_limit_s: float = 5.0
    heater_test_default_duration_s: float = 2.0


@dataclass(slots=True)
class DigitalOutputConfig:
    pin: int
    active_high: bool = True
    initial_enabled: bool = False


@dataclass(slots=True)
class HeaterOutputConfig(DigitalOutputConfig):
    control_period_s: float = 0.5
    time_window_s: float = 2.0


@dataclass(slots=True)
class FanControlConfig:
    auto_enabled: bool = False
    auto_temperature_threshold_c: float = 120.0
    auto_hold_seconds: float = 30.0


@dataclass(slots=True)
class SerialConfig:
    port: str = "/dev/ttyACM0"
    baudrate: int = 115200
    timeout_s: float = 1.0


@dataclass(slots=True)
class MachineConfig:
    mode: RuntimeMode = RuntimeMode.SIMULATION
    control_interval_s: float = 0.5
    status_interval_s: float = 0.25
    pid: PidConfig = field(
        default_factory=lambda: PidConfig(
            kp=8.0,
            ki=0.7,
            kd=1.2,
            setpoint=200.0,
            sample_time=0.5,
            output_limits=(0.0, 100.0),
        )
    )
    sensor: TemperatureSensorConfig = field(
        default_factory=lambda: TemperatureSensorConfig.for_element(SensorElement.PT100)
    )
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    heater: HeaterOutputConfig = field(default_factory=lambda: HeaterOutputConfig(pin=2))
    fan: DigitalOutputConfig = field(default_factory=lambda: DigitalOutputConfig(pin=3))
    valve: DigitalOutputConfig = field(default_factory=lambda: DigitalOutputConfig(pin=4))
    fan_control: FanControlConfig = field(default_factory=FanControlConfig)
    max31865_spi_bus: int = 0
    max31865_sck_pin: int = 18
    max31865_mosi_pin: int = 19
    max31865_miso_pin: int = 16
    max31865_cs_pin: int = 17
    serial: SerialConfig = field(default_factory=SerialConfig)
    # TODO: Validate PT100 calibration and exact Rref against the installed Adafruit board.
