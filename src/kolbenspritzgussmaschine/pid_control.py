from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Protocol

try:
    from simple_pid import PID
except ModuleNotFoundError:
    class PID:
        """Minimal fallback implementation when ``simple_pid`` is unavailable."""

        def __init__(
            self,
            kp: float,
            ki: float,
            kd: float,
            *,
            setpoint: float = 0.0,
            sample_time: float | None = 0.01,
            output_limits: tuple[float | None, float | None] = (None, None),
            starting_output: float = 0.0,
            proportional_on_measurement: bool = False,
            differential_on_measurement: bool = True,
        ) -> None:
            self.kp = kp
            self.ki = ki
            self.kd = kd
            self.setpoint = setpoint
            self.sample_time = sample_time
            self.output_limits = output_limits
            self.proportional_on_measurement = proportional_on_measurement
            self.differential_on_measurement = differential_on_measurement
            self.auto_mode = True

            self._last_time: float | None = None
            self._last_input: float | None = None
            self._last_error = 0.0
            self._last_output = self._clamp(starting_output)
            self._proportional = 0.0
            self._integral = self._clamp(starting_output)
            self._derivative = 0.0

        @property
        def components(self) -> tuple[float, float, float]:
            return self._proportional, self._integral, self._derivative

        def set_auto_mode(self, enabled: bool, last_output: float | None = None) -> None:
            self.auto_mode = enabled
            if enabled:
                self._last_time = None
                self._last_input = None
                self._last_error = 0.0
                if last_output is not None:
                    clamped = self._clamp(last_output)
                    self._last_output = clamped
                    self._integral = clamped

        def __call__(self, input_: float) -> float:
            if not self.auto_mode:
                return self._last_output

            now = monotonic()
            if self._last_time is None:
                dt = self.sample_time if self.sample_time is not None else 0.0
            else:
                dt = now - self._last_time
                if self.sample_time is not None and dt < self.sample_time:
                    return self._last_output

            error = self.setpoint - input_
            d_input = 0.0 if self._last_input is None else input_ - self._last_input
            d_error = error - self._last_error

            if self.proportional_on_measurement:
                self._proportional -= self.kp * d_input
            else:
                self._proportional = self.kp * error

            if dt > 0.0:
                self._integral += self.ki * error * dt
                if self.differential_on_measurement:
                    self._derivative = -(self.kd * d_input) / dt
                else:
                    self._derivative = (self.kd * d_error) / dt
            else:
                self._derivative = 0.0

            self._integral = self._clamp(self._integral)
            output = self._clamp(self._proportional + self._integral + self._derivative)

            self._last_output = output
            self._last_input = input_
            self._last_error = error
            self._last_time = now
            return output

        def _clamp(self, value: float) -> float:
            lower, upper = self.output_limits
            if lower is not None and value < lower:
                return lower
            if upper is not None and value > upper:
                return upper
            return value

from .config import PidConfig


class SensorProtocol(Protocol):
    def read(self) -> float:
        """Return the current process value."""


class ActuatorProtocol(Protocol):
    def write(self, value: float) -> float:
        """Apply a new actuator output."""

    def stop(self) -> None:
        """Drive the actuator into a defined safe state."""


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

    def update_from_measurement(self, process_value: float) -> PidTelemetry:
        requested_output = float(self._pid(process_value))
        applied_output = float(self.actuator.write(requested_output))

        now = monotonic()
        self._last_update = now
        proportional, integral, derivative = self._pid.components
        return PidTelemetry(
            timestamp=now,
            process_value=process_value,
            setpoint=float(self._pid.setpoint),
            control_output=applied_output,
            error=float(self._pid.setpoint - process_value),
            proportional=float(proportional),
            integral=float(integral),
            derivative=float(derivative),
        )

    def update_once(self) -> PidTelemetry:
        process_value = self.sensor.read()
        return self.update_from_measurement(process_value)

    def assert_fresh(self) -> None:
        if monotonic() - self._last_update > self.max_stale_seconds:
            self.disable()
            raise TimeoutError("PID loop data is stale; actuator was stopped.")

    def run_forever(self) -> None:
        while True:
            self.update_once()
            sleep(self.config.sample_time)
