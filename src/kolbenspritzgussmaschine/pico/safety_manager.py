try:
    from time import monotonic
except ImportError:
    from time import ticks_ms

    def monotonic():
        return ticks_ms() / 1000.0

from ..config import SafetyConfig
from ..models import FaultState
from ..safety_manager import SafetyManager


class PicoSafetyManager(SafetyManager):
    """Microcontroller-focused safety helper with communication watchdog."""

    def __init__(self, config: SafetyConfig) -> None:
        super().__init__(config)
        self._last_command_at = None

    def note_command_received(self) -> None:
        self._last_command_at = monotonic()

    def evaluate_watchdog(self):
        return self.evaluate_communication(self._last_command_at, monotonic())

    def apply_safe_state(self, heater, fan, valve) -> None:
        outputs = self.safe_outputs()
        heater.set_power_percent(outputs.heater_percent)
        fan.set_enabled(outputs.fan_enabled)
        valve.set_enabled(outputs.valve_enabled)
