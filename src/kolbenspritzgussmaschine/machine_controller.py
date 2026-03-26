from __future__ import annotations

from time import monotonic

from .config import MachineConfig, OperatingMode, PidConfig
from .interfaces import HeaterActuatorAdapter, MachineHardware, TemperatureSensorAdapter
from .models import ErrorCode, FaultState, MachineStatus
from .pid_control import InjectionMachinePidController, PidTelemetry
from .safety_manager import SafetyManager


class MachineController:
    """Owns the control loop and safe state transitions for one machine."""

    def __init__(self, hardware: MachineHardware, config: MachineConfig) -> None:
        self.hardware = hardware
        self.config = config
        self.safety = SafetyManager(config.safety)
        self.pid_controller = self._build_pid_controller(config.pid)
        self.mode = OperatingMode.OFF
        self.heating_enabled = False
        self.fan_enabled = False
        self.valve_enabled = False
        self.fan_auto_active = False
        self.fault = FaultState(ErrorCode.NONE, "")
        self._last_telemetry: PidTelemetry | None = None
        self._heater_test_deadline: float | None = None
        self._fan_auto_until: float | None = None
        self._apply_outputs()

    def _build_pid_controller(self, pid_config: PidConfig) -> InjectionMachinePidController:
        return InjectionMachinePidController(
            sensor=TemperatureSensorAdapter(self.hardware.sensor),
            actuator=HeaterActuatorAdapter(self.hardware.heater),
            config=pid_config,
            max_stale_seconds=self.config.safety.controller_timeout_s,
        )

    def update_pid_parameters(self, kp: float, ki: float, kd: float, setpoint_c: float) -> None:
        self.config.pid.kp = kp
        self.config.pid.ki = ki
        self.config.pid.kd = kd
        self.config.pid.setpoint = setpoint_c
        was_enabled = self.heating_enabled and self.mode == OperatingMode.AUTO
        self.pid_controller = self._build_pid_controller(self.config.pid)
        self.pid_controller.set_setpoint(setpoint_c)
        if was_enabled:
            self.pid_controller.enable(last_output=0.0)

    def set_target_temperature(self, temperature_c: float) -> None:
        self.config.pid.setpoint = temperature_c
        self.pid_controller.set_setpoint(temperature_c)

    def set_mode(self, mode: OperatingMode) -> None:
        if self.fault.code != ErrorCode.NONE and mode != OperatingMode.FAULT:
            raise RuntimeError("Cannot leave FAULT without acknowledge_fault().")
        self.mode = mode
        self._heater_test_deadline = None
        if mode == OperatingMode.OFF:
            self.heating_enabled = False
            self.hardware.heater.disable()
        elif mode == OperatingMode.TEST:
            self.heating_enabled = False
            self.hardware.heater.disable()
        elif mode == OperatingMode.AUTO:
            self.heating_enabled = True
            self.pid_controller.enable(last_output=0.0)
        elif mode == OperatingMode.FAULT:
            self.trip_fault(FaultState(ErrorCode.INVALID_STATE, "Fault mode requested."))

    def acknowledge_fault(self) -> None:
        self.fault = FaultState(ErrorCode.NONE, "")
        self.mode = OperatingMode.OFF
        self.heating_enabled = False
        self._heater_test_deadline = None
        self._apply_outputs()

    def set_overtemperature_limit(self, temperature_c: float) -> None:
        self.config.safety.overtemperature_c = temperature_c

    def start_heater_test(self, duration_s: float | None = None) -> None:
        if self.mode != OperatingMode.TEST:
            raise RuntimeError("Heater test requires TEST mode.")
        if self.fault.code != ErrorCode.NONE:
            raise RuntimeError("Heater test blocked while fault is active.")
        duration = duration_s if duration_s is not None else self.config.safety.heater_test_default_duration_s
        duration = max(0.1, min(duration, self.config.safety.heater_test_duration_limit_s))
        temperature = self.hardware.sensor.read_temperature()
        fault = self.safety.evaluate_temperature(temperature)
        if fault is not None:
            self.trip_fault(fault)
            raise RuntimeError(fault.message)
        self._heater_test_deadline = monotonic() + duration

    def set_fan_enabled(self, enabled: bool) -> None:
        self.fan_enabled = enabled
        if self.fault.code == ErrorCode.NONE:
            self.hardware.fan.set_enabled(enabled)

    def set_valve_enabled(self, enabled: bool) -> None:
        self.valve_enabled = enabled
        if self.fault.code == ErrorCode.NONE:
            self.hardware.valve.set_enabled(enabled)

    def clear_fault(self) -> None:
        self.acknowledge_fault()

    def trip_fault(self, fault: FaultState) -> None:
        self.fault = fault
        self.mode = OperatingMode.FAULT
        self.heating_enabled = False
        self._heater_test_deadline = None
        self.pid_controller.disable()
        safe_outputs = self.safety.safe_outputs()
        self.hardware.heater.set_power_percent(safe_outputs.heater_percent)
        self.hardware.fan.set_enabled(safe_outputs.fan_enabled)
        self.hardware.valve.set_enabled(safe_outputs.valve_enabled)

    def all_outputs_off(self) -> None:
        self.heating_enabled = False
        self._heater_test_deadline = None
        self.hardware.heater.disable()
        self.hardware.fan.disable()
        self.hardware.valve.disable()

    def _apply_outputs(self) -> None:
        self.hardware.heater.disable()
        self.hardware.fan.set_enabled(self.fan_enabled)
        self.hardware.valve.set_enabled(self.valve_enabled)

    def tick(self) -> MachineStatus:
        now = monotonic()
        try:
            temperature_c = self.hardware.sensor.read_temperature()
            sensor_ok = True
        except Exception as exc:
            self.trip_fault(FaultState(ErrorCode.SENSOR_FAULT, str(exc)))
            return self._build_status(now, None, sensor_ok=False)

        fault = self.safety.evaluate_temperature(temperature_c)
        if fault is not None:
            self.trip_fault(fault)
            return self._build_status(now, temperature_c, sensor_ok=True)

        self._apply_fan_automation(now, temperature_c)

        if self.mode == OperatingMode.AUTO and self.heating_enabled and self.fault.code == ErrorCode.NONE:
            self._last_telemetry = self.pid_controller.update_from_measurement(temperature_c)
        elif self.mode == OperatingMode.TEST and self._heater_test_deadline is not None and now < self._heater_test_deadline:
            self.hardware.heater.set_power_percent(100.0)
            self._last_telemetry = None
        else:
            self._heater_test_deadline = None
            self.hardware.heater.disable()
            self._last_telemetry = None

        self.hardware.fan.set_enabled(self.fan_enabled or self.fan_auto_active)
        self.hardware.valve.set_enabled(self.valve_enabled if self.fault.code == ErrorCode.NONE else False)
        return self._build_status(now, temperature_c, sensor_ok=True)

    def _apply_fan_automation(self, now: float, temperature_c: float) -> None:
        self.fan_auto_active = False
        if not self.config.fan_control.auto_enabled:
            return
        if temperature_c >= self.config.fan_control.auto_temperature_threshold_c:
            self._fan_auto_until = now + self.config.fan_control.auto_hold_seconds
        if self._fan_auto_until is not None and now < self._fan_auto_until:
            self.fan_auto_active = True

    def _build_status(self, timestamp: float, temperature_c: float | None, *, sensor_ok: bool) -> MachineStatus:
        heater_output = 0.0
        heater_on = False
        if self._last_telemetry is not None and self.fault.code == ErrorCode.NONE:
            heater_output = self._last_telemetry.control_output
            heater_on = heater_output > 0.0
        elif self._heater_test_deadline is not None and timestamp < self._heater_test_deadline:
            heater_output = 100.0
            heater_on = True
        remaining = 0.0
        if self._heater_test_deadline is not None:
            remaining = max(0.0, self._heater_test_deadline - timestamp)
        return MachineStatus(
            timestamp=timestamp,
            temperature_c=temperature_c,
            setpoint_c=self.config.pid.setpoint,
            heater_output_percent=heater_output,
            heating_enabled=self.heating_enabled,
            fan_enabled=self.fan_enabled or self.fan_auto_active if self.fault.code == ErrorCode.NONE else True,
            valve_enabled=self.valve_enabled if self.fault.code == ErrorCode.NONE else False,
            fault_code=self.fault.code,
            fault_message=self.fault.message,
            mode=self.mode,
            sensor_ok=sensor_ok,
            communication_ok=True,
            heater_on=heater_on,
            fan_auto_active=self.fan_auto_active,
            overtemperature_limit_c=self.config.safety.overtemperature_c,
            test_seconds_remaining=remaining,
        )
