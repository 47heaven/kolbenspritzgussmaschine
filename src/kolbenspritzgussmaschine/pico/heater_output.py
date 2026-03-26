try:
    from time import ticks_diff, ticks_ms
except ImportError:
    from time import monotonic

    def ticks_ms():
        return int(monotonic() * 1000)

    def ticks_diff(current, previous):
        return current - previous

from ..config import HeaterOutputConfig

try:  # pragma: no cover - MicroPython only
    from machine import Pin
except ImportError:  # pragma: no cover
    Pin = None


class TimeProportionalHeaterOutput:
    """Time-proportional active-high heater output for a MOSFET stage.

    The Pico main loop should call update() frequently. The output stays on for a
    fraction of each time window according to the requested power percentage.
    """

    def __init__(self, config: HeaterOutputConfig) -> None:
        if Pin is None:
            raise RuntimeError("TimeProportionalHeaterOutput requires MicroPython on the Pico.")
        self.config = config
        self._pin = Pin(config.pin, Pin.OUT, value=0)
        self._window_ms = int(config.time_window_s * 1000)
        self._window_started_ms = ticks_ms()
        self._power_percent = 0.0
        self._is_on = False
        self.disable()

    @property
    def is_on(self) -> bool:
        return self._is_on

    def set_power_percent(self, value: float) -> None:
        self._power_percent = max(0.0, min(100.0, value))

    def disable(self) -> None:
        self._power_percent = 0.0
        self._write(False)

    def update(self, now_ms=None) -> None:
        now_ms = ticks_ms() if now_ms is None else now_ms
        elapsed_ms = ticks_diff(now_ms, self._window_started_ms)
        if elapsed_ms >= self._window_ms:
            self._window_started_ms = now_ms
            elapsed_ms = 0
        on_time_ms = int(self._window_ms * (self._power_percent / 100.0))
        self._write(on_time_ms > 0 and elapsed_ms < on_time_ms)

    def _write(self, enabled: bool) -> None:
        self._is_on = enabled
        physical = enabled if self.config.active_high else not enabled
        self._pin.value(1 if physical else 0)
