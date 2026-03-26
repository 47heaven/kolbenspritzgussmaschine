try:
    from enum import Enum
    _MICROPYTHON_ENUM_FALLBACK = False
except ImportError:
    _MICROPYTHON_ENUM_FALLBACK = True
    class Enum:
        _value2member_map_ = None

        def __new__(cls, value):
            mapping = getattr(cls, "_value2member_map_", None)
            if mapping is not None and value in mapping:
                return mapping[value]
            self = object.__new__(cls)
            self._value_ = value
            return self

        @property
        def value(self):
            return self._value_

        def __str__(self):
            return str(self._value_)

        def __repr__(self):
            return str(self._value_)

        def __eq__(self, other):
            if isinstance(other, Enum):
                return self.value == other.value
            return self.value == other

        @classmethod
        def _finalize_members(cls):
            mapping = {}
            for key, value in list(cls.__dict__.items()):
                if key.startswith("_") or callable(value):
                    continue
                member = cls.__new__(cls, value)
                setattr(cls, key, member)
                mapping[value] = member
            cls._value2member_map_ = mapping


if _MICROPYTHON_ENUM_FALLBACK:
    class RuntimeMode(Enum):
        SIMULATION = "simulation"
        SERIAL = "serial"


    class OperatingMode(Enum):
        OFF = "off"
        TEST = "test"
        AUTO = "auto"
        FAULT = "fault"


    class SensorElement(Enum):
        PT100 = "pt100"
        PT1000 = "pt1000"
else:
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


if getattr(RuntimeMode, "_value2member_map_", None) is None:
    RuntimeMode._finalize_members()
if getattr(OperatingMode, "_value2member_map_", None) is None:
    OperatingMode._finalize_members()
if getattr(SensorElement, "_value2member_map_", None) is None:
    SensorElement._finalize_members()


class PidConfig:
    def __init__(
        self,
        kp,
        ki,
        kd,
        setpoint,
        sample_time=0.5,
        output_limits=(0.0, 100.0),
        starting_output=0.0,
        proportional_on_measurement=False,
        differential_on_measurement=True,
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.sample_time = sample_time
        self.output_limits = output_limits
        self.starting_output = starting_output
        self.proportional_on_measurement = proportional_on_measurement
        self.differential_on_measurement = differential_on_measurement


class TemperatureSensorConfig:
    def __init__(
        self,
        element=SensorElement.PT100,
        reference_resistor_ohms=430.0,
        nominal_resistance_ohms=100.0,
        wires=2,
        filter_frequency_hz=50,
    ):
        self.element = element
        self.reference_resistor_ohms = reference_resistor_ohms
        self.nominal_resistance_ohms = nominal_resistance_ohms
        self.wires = wires
        self.filter_frequency_hz = filter_frequency_hz

    @classmethod
    def for_element(cls, element):
        if element == SensorElement.PT1000:
            return cls(
                element=element,
                reference_resistor_ohms=4300.0,
                nominal_resistance_ohms=1000.0,
            )
        return cls(element=element)


class SafetyConfig:
    def __init__(
        self,
        min_plausible_temp_c=0.0,
        max_plausible_temp_c=320.0,
        overtemperature_c=250.0,
        communication_timeout_s=3.0,
        controller_timeout_s=1.5,
        heater_test_duration_limit_s=5.0,
        heater_test_default_duration_s=2.0,
    ):
        self.min_plausible_temp_c = min_plausible_temp_c
        self.max_plausible_temp_c = max_plausible_temp_c
        self.overtemperature_c = overtemperature_c
        self.communication_timeout_s = communication_timeout_s
        self.controller_timeout_s = controller_timeout_s
        self.heater_test_duration_limit_s = heater_test_duration_limit_s
        self.heater_test_default_duration_s = heater_test_default_duration_s


class DigitalOutputConfig:
    def __init__(self, pin, active_high=True, initial_enabled=False):
        self.pin = pin
        self.active_high = active_high
        self.initial_enabled = initial_enabled


class HeaterOutputConfig(DigitalOutputConfig):
    def __init__(
        self,
        pin,
        active_high=True,
        initial_enabled=False,
        control_period_s=0.5,
        time_window_s=2.0,
    ):
        DigitalOutputConfig.__init__(self, pin, active_high=active_high, initial_enabled=initial_enabled)
        self.control_period_s = control_period_s
        self.time_window_s = time_window_s


class FanControlConfig:
    def __init__(self, auto_enabled=False, auto_temperature_threshold_c=120.0, auto_hold_seconds=30.0):
        self.auto_enabled = auto_enabled
        self.auto_temperature_threshold_c = auto_temperature_threshold_c
        self.auto_hold_seconds = auto_hold_seconds


class SerialConfig:
    def __init__(self, port="/dev/ttyACM0", baudrate=115200, timeout_s=1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout_s = timeout_s


class MachineConfig:
    def __init__(
        self,
        mode=RuntimeMode.SIMULATION,
        control_interval_s=0.5,
        status_interval_s=0.25,
        pid=None,
        sensor=None,
        safety=None,
        heater=None,
        fan=None,
        valve=None,
        fan_control=None,
        max31865_spi_bus=0,
        max31865_sck_pin=18,
        max31865_mosi_pin=19,
        max31865_miso_pin=16,
        max31865_cs_pin=17,
        serial=None,
    ):
        self.mode = mode
        self.control_interval_s = control_interval_s
        self.status_interval_s = status_interval_s
        self.pid = pid if pid is not None else PidConfig(
            kp=8.0,
            ki=0.7,
            kd=1.2,
            setpoint=200.0,
            sample_time=0.5,
            output_limits=(0.0, 100.0),
        )
        self.sensor = sensor if sensor is not None else TemperatureSensorConfig.for_element(SensorElement.PT100)
        self.safety = safety if safety is not None else SafetyConfig()
        self.heater = heater if heater is not None else HeaterOutputConfig(pin=2)
        self.fan = fan if fan is not None else DigitalOutputConfig(pin=3)
        self.valve = valve if valve is not None else DigitalOutputConfig(pin=4)
        self.fan_control = fan_control if fan_control is not None else FanControlConfig()
        self.max31865_spi_bus = max31865_spi_bus
        self.max31865_sck_pin = max31865_sck_pin
        self.max31865_mosi_pin = max31865_mosi_pin
        self.max31865_miso_pin = max31865_miso_pin
        self.max31865_cs_pin = max31865_cs_pin
        self.serial = serial if serial is not None else SerialConfig()
        # TODO: Validate PT100 calibration and exact Rref against the installed Adafruit board.
