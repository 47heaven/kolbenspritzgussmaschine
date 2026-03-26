from .config import SafetyConfig
from .models import ErrorCode, FaultState


class SafeOutputs:
    def __init__(self, heater_percent=0.0, fan_enabled=True, valve_enabled=False):
        self.heater_percent = heater_percent
        self.fan_enabled = fan_enabled
        self.valve_enabled = valve_enabled


class SafetyManager:
    """Evaluate runtime conditions and define the machine safe state."""

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config

    def evaluate_temperature(self, temperature_c):
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

    def evaluate_communication(self, last_seen_at, now):
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
