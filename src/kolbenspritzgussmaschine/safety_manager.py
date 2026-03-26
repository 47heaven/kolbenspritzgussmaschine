from __future__ import annotations

from dataclasses import dataclass

from .config import SafetyConfig
from .models import ErrorCode, FaultState


@dataclass(slots=True)
class SafeOutputs:
    heater_percent: float = 0.0
    fan_enabled: bool = True
    valve_enabled: bool = False


class SafetyManager:
    """Evaluate runtime conditions and define the machine safe state."""

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config

    def evaluate_temperature(self, temperature_c: float) -> FaultState | None:
        if temperature_c < self.config.min_plausible_temp_c:
            return FaultState(
                ErrorCode.TEMPERATURE_OUT_OF_RANGE,
                f"Temperature {temperature_c:.1f} C below plausible minimum.",
            )
        if temperature_c > self.config.max_plausible_temp_c:
            return FaultState(
                ErrorCode.TEMPERATURE_OUT_OF_RANGE,
                f"Temperature {temperature_c:.1f} C above plausible maximum.",
            )
        if temperature_c >= self.config.overtemperature_c:
            return FaultState(
                ErrorCode.OVERTEMPERATURE,
                f"Temperature {temperature_c:.1f} C exceeds overtemperature limit.",
            )
        return None

    def evaluate_communication(self, last_seen_at: float | None, now: float) -> FaultState | None:
        if last_seen_at is None:
            return None
        if now - last_seen_at > self.config.communication_timeout_s:
            return FaultState(
                ErrorCode.COMMUNICATION_TIMEOUT,
                "Communication with controller timed out.",
            )
        return None

    def safe_outputs(self) -> SafeOutputs:
        return SafeOutputs()
