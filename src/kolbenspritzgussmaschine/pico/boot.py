try:  # pragma: no cover - MicroPython only
    from machine import Pin
except ImportError:  # pragma: no cover
    Pin = None


def apply_safe_boot_pins() -> None:
    if Pin is None:
        return
    # Force the pneumatic valve output into the safe OFF level as early as possible.
    Pin(4, Pin.OUT, value=0)


apply_safe_boot_pins()
