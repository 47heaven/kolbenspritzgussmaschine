from ..config import DigitalOutputConfig

try:  # pragma: no cover - MicroPython only
    from machine import Pin
except ImportError:  # pragma: no cover
    Pin = None


class ActiveHighValveOutput:
    def __init__(self, config: DigitalOutputConfig) -> None:
        if Pin is None:
            raise RuntimeError("ActiveHighValveOutput requires MicroPython on the Pico.")
        self.config = config
        safe_off_level = 1 if not config.active_high else 0
        try:
            self._pin = Pin(config.pin, Pin.OUT, value=safe_off_level)
        except TypeError:
            self._pin = Pin(config.pin, Pin.OUT)
            self._pin.value(safe_off_level)
        self._enabled = False
        self.disable()

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        physical = enabled if self.config.active_high else not enabled
        self._pin.value(1 if physical else 0)

    def disable(self) -> None:
        self.set_enabled(False)
