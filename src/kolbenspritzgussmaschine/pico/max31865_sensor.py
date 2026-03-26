from math import sqrt

from ..config import TemperatureSensorConfig

try:  # pragma: no cover - MicroPython only
    from machine import Pin, SPI
except ImportError:  # pragma: no cover
    Pin = None
    SPI = None


class Max31865Sensor:
    """Minimal MAX31865 reader for PT100/PT1000 on the Pico.

    Prepared for the Adafruit PT100 board with 2-wire PT100 and 50 Hz filter.
    TODO: Validate calibration against the final installed sensor, cable length
    and the exact reference resistor on the real board.
    """

    CONFIG_REGISTER = 0x00
    RTD_MSB_REGISTER = 0x01
    HIGH_FAULT_MSB = 0x03
    LOW_FAULT_MSB = 0x05
    FAULT_STATUS_REGISTER = 0x07

    CONFIG_BIAS = 0x80
    CONFIG_AUTO = 0x40
    CONFIG_1SHOT = 0x20
    CONFIG_3WIRE = 0x10
    CONFIG_CLEAR_FAULT = 0x02
    CONFIG_50HZ_FILTER = 0x01

    def __init__(
        self,
        spi_bus: int,
        sck_pin: int,
        mosi_pin: int,
        miso_pin: int,
        cs_pin: int,
        sensor_config: TemperatureSensorConfig,
    ) -> None:
        if SPI is None or Pin is None:
            raise RuntimeError("Max31865Sensor requires MicroPython on the Pico.")
        self.sensor_config = sensor_config
        self.spi = SPI(
            spi_bus,
            baudrate=1_000_000,
            polarity=0,
            phase=1,
            sck=Pin(sck_pin),
            mosi=Pin(mosi_pin),
            miso=Pin(miso_pin),
        )
        self.cs = Pin(cs_pin, Pin.OUT, value=1)
        self.last_fault = 0
        self._configure()

    def _configure(self) -> None:
        config = self.CONFIG_BIAS | self.CONFIG_AUTO | self.CONFIG_CLEAR_FAULT
        if self.sensor_config.wires == 3:
            config |= self.CONFIG_3WIRE
        if self.sensor_config.filter_frequency_hz == 50:
            config |= self.CONFIG_50HZ_FILTER
        self._write_register(self.CONFIG_REGISTER, config)

    def _write_register(self, register: int, value: int) -> None:
        self.cs.value(0)
        self.spi.write(bytes([(register | 0x80) & 0xFF, value & 0xFF]))
        self.cs.value(1)

    def _read_registers(self, register: int, count: int) -> bytes:
        read_buffer = bytearray(count)
        self.cs.value(0)
        self.spi.write(bytes([register & 0x7F]))
        self.spi.readinto(read_buffer)
        self.cs.value(1)
        return bytes(read_buffer)

    def read_temperature(self) -> float:
        raw = self._read_registers(self.RTD_MSB_REGISTER, 2)
        combined = (raw[0] << 8) | raw[1]
        if combined & 0x01:
            self.last_fault = self._read_registers(self.FAULT_STATUS_REGISTER, 1)[0]
            self._clear_fault()
            raise RuntimeError(f"MAX31865 fault 0x{self.last_fault:02X}")
        rtd = combined >> 1
        if rtd == 0:
            raise RuntimeError("MAX31865 returned zero RTD value.")
        resistance = (rtd / 32768.0) * self.sensor_config.reference_resistor_ohms
        return self._resistance_to_temperature(resistance)

    def _clear_fault(self) -> None:
        config = self.CONFIG_BIAS | self.CONFIG_AUTO | self.CONFIG_CLEAR_FAULT
        if self.sensor_config.wires == 3:
            config |= self.CONFIG_3WIRE
        if self.sensor_config.filter_frequency_hz == 50:
            config |= self.CONFIG_50HZ_FILTER
        self._write_register(self.CONFIG_REGISTER, config)

    def _resistance_to_temperature(self, resistance_ohms: float) -> float:
        r0 = self.sensor_config.nominal_resistance_ohms
        a = 3.9083e-3
        b = -5.775e-7
        discriminant = a * a - 4 * b * (1 - resistance_ohms / r0)
        if discriminant < 0:
            raise RuntimeError("Invalid RTD resistance; discriminant below zero.")
        return (-a + sqrt(discriminant)) / (2 * b)
