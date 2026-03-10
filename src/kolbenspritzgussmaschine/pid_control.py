from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Protocol

from simple_pid import PID


class SensorProtocol(Protocol):
    def read(self) -> float:
        """Return the current process value."""


class ActuatorProtocol(Protocol):
    def write(self, value: float) -> None:
        """Apply a new actuator output."""

    def stop(self) -> None:
        """Drive the actuator into a defined safe state."""


@dataclass(slots=True)
class PidConfig:
    kp: float
    ki: float
    kd: float
    setpoint: float
    sample_time: float = 0.1
    output_limits: tuple[float | None, float | None] = (0.0, 100.0)
    starting_output: float = 0.0
    proportional_on_measurement: bool = False
    differential_on_measurement: bool = True


@dataclass(slots=True)
class PidTelemetry:
    timestamp: float
    process_value: float
    setpoint: float
    control_output: float
    error: float
    proportional: float
    integral: float
    derivative: float


class InjectionMachinePidController:
    """Wrap simple-pid with machine-oriented safety and telemetry hooks."""

    def __init__(
        self,
        sensor: SensorProtocol,
        actuator: ActuatorProtocol,
        config: PidConfig,
        *,
        max_stale_seconds: float = 1.0,
    ) -> None:
        self.sensor = sensor
        self.actuator = actuator
        self.config = config
        self.max_stale_seconds = max_stale_seconds
        self._last_update = 0.0
        self._pid = PID(
            config.kp,
            config.ki,
            config.kd,
            setpoint=config.setpoint,
            sample_time=config.sample_time,
            output_limits=config.output_limits,
            starting_output=config.starting_output,
            proportional_on_measurement=config.proportional_on_measurement,
            differential_on_measurement=config.differential_on_measurement,
        )

    @property
    def pid(self) -> PID:
        return self._pid

    def set_setpoint(self, value: float) -> None:
        self._pid.setpoint = value

    def enable(self, last_output: float | None = None) -> None:
        self._pid.set_auto_mode(True, last_output=last_output)

    def disable(self) -> None:
        self._pid.auto_mode = False
        self.actuator.stop()

    def update_once(self) -> PidTelemetry:
        process_value = self.sensor.read()
        output = float(self._pid(process_value))
        self.actuator.write(output)

        now = monotonic()
        self._last_update = now
        proportional, integral, derivative = self._pid.components
        return PidTelemetry(
            timestamp=now,
            process_value=process_value,
            setpoint=float(self._pid.setpoint),
            control_output=output,
            error=float(self._pid.setpoint - process_value),
            proportional=float(proportional),
            integral=float(integral),
            derivative=float(derivative),
        )

    def assert_fresh(self) -> None:
        if monotonic() - self._last_update > self.max_stale_seconds:
            self.disable()
            raise TimeoutError("PID loop data is stale; actuator was stopped.")

    def run_forever(self) -> None:
        while True:
            self.update_once()
            sleep(self.config.sample_time)

