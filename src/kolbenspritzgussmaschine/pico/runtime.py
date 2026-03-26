import sys
from time import sleep

from ..communication.protocol import decode_message, encode_message
from ..config import MachineConfig, OperatingMode
from ..models import ErrorCode, FaultState, MachineStatus
from .fan_output import ActiveHighFanOutput
from .heater_output import TimeProportionalHeaterOutput
from .max31865_sensor import Max31865Sensor
from .pid_loop import SimplePidLoop
from .safety_manager import PicoSafetyManager
from .valve_output import ActiveHighValveOutput

try:
    from time import monotonic
except ImportError:
    from time import ticks_ms

    def monotonic():
        return ticks_ms() / 1000.0

try:  # pragma: no cover - MicroPython only
    import uselect as select
except ImportError:  # pragma: no cover
    select = None


def _safe_flush_stdout() -> None:
    flush = getattr(sys.stdout, "flush", None)
    if flush is not None:
        flush()


class PicoRuntime:
    def __init__(self, config: MachineConfig) -> None:
        self.config = config
        self.sensor = Max31865Sensor(
            spi_bus=config.max31865_spi_bus,
            sck_pin=config.max31865_sck_pin,
            mosi_pin=config.max31865_mosi_pin,
            miso_pin=config.max31865_miso_pin,
            cs_pin=config.max31865_cs_pin,
            sensor_config=config.sensor,
        )
        self.heater = TimeProportionalHeaterOutput(config.heater)
        self.fan = ActiveHighFanOutput(config.fan)
        self.valve = ActiveHighValveOutput(config.valve)
        self.safety = PicoSafetyManager(config.safety)
        self.pid = SimplePidLoop(
            kp=config.pid.kp,
            ki=config.pid.ki,
            kd=config.pid.kd,
            sample_time_s=config.control_interval_s,
        )
        self.pid.setpoint = config.pid.setpoint
        self.mode = OperatingMode.OFF
        self.heating_enabled = False
        self.fan_enabled = False
        self.valve_enabled = False
        self.fan_auto_active = False
        self.fault = FaultState(ErrorCode.NONE, "")
        self.temperature_c = None
        self.sensor_ok = False
        self.heater_output_percent = 0.0
        self.heater_test_until = None
        self.fan_auto_until = None
        self._last_control_at = monotonic()
        self._apply_safe_boot_state()
        self._read_temperature()

    def _apply_safe_boot_state(self) -> None:
        self.heater.disable()
        self.fan.disable()
        self.valve.disable()

    def _set_fault(self, code: ErrorCode, message: str) -> None:
        self.fault = FaultState(code, message)
        self.mode = OperatingMode.FAULT
        self.heating_enabled = False
        self.heater_test_until = None
        self.heater_output_percent = 0.0
        self.safety.apply_safe_state(self.heater, self.fan, self.valve)

    def _clear_fault(self) -> None:
        self.fault = FaultState(ErrorCode.NONE, "")
        self.mode = OperatingMode.OFF
        self.heating_enabled = False
        self.heater_test_until = None
        self.heater_output_percent = 0.0
        self.pid.reset()
        self._apply_safe_boot_state()

    def _read_temperature(self) -> None:
        try:
            self.temperature_c = self.sensor.read_temperature()
            self.sensor_ok = True
        except Exception as exc:
            self.temperature_c = None
            self.sensor_ok = False
            self._set_fault(ErrorCode.SENSOR_FAULT, str(exc))
            return
        fault = self.safety.evaluate_temperature(self.temperature_c)
        if fault is not None:
            self._set_fault(fault.code, fault.message)

    def _apply_fan_logic(self, now: float) -> None:
        self.fan_auto_active = False
        if self.config.fan_control.auto_enabled and self.temperature_c is not None:
            if self.temperature_c >= self.config.fan_control.auto_temperature_threshold_c:
                self.fan_auto_until = now + self.config.fan_control.auto_hold_seconds
            if self.fan_auto_until is not None and now < self.fan_auto_until:
                self.fan_auto_active = True
        fan_on = self.fan_enabled or self.fan_auto_active
        if self.mode == OperatingMode.FAULT:
            fan_on = True
        self.fan.set_enabled(fan_on)

    def _update_control(self, now: float) -> None:
        if self.fault.code != ErrorCode.NONE:
            self.heater_output_percent = 0.0
            self.heater.disable()
            return
        if self.mode == OperatingMode.AUTO and self.heating_enabled and self.temperature_c is not None:
            self.heater_output_percent = self.pid.compute(self.temperature_c)
            self.heater.set_power_percent(self.heater_output_percent)
        elif self.mode == OperatingMode.TEST and self.heater_test_until is not None and now < self.heater_test_until and self.sensor_ok:
            self.heater_output_percent = 100.0
            self.heater.set_power_percent(100.0)
        else:
            self.heater_test_until = None
            self.heater_output_percent = 0.0
            self.heater.disable()
        self.heater.update()
        self.valve.set_enabled(self.valve_enabled if self.mode != OperatingMode.FAULT else False)
        self._apply_fan_logic(now)

    def tick(self):
        now = monotonic()
        watchdog_fault = self.safety.evaluate_watchdog()
        if watchdog_fault is not None and self.mode != OperatingMode.FAULT:
            self._set_fault(watchdog_fault.code, watchdog_fault.message)
        if now - self._last_control_at >= self.config.control_interval_s:
            self._last_control_at = now
            self._read_temperature()
            self._update_control(now)
        else:
            self.heater.update()
        return self.build_status(now)

    def build_status(self, now=None):
        now = monotonic() if now is None else now
        remaining = 0.0
        if self.heater_test_until is not None:
            remaining = max(0.0, self.heater_test_until - now)
        return MachineStatus(
            timestamp=now,
            temperature_c=self.temperature_c,
            setpoint_c=self.pid.setpoint,
            heater_output_percent=self.heater_output_percent,
            heating_enabled=self.heating_enabled,
            fan_enabled=self.fan.is_enabled,
            valve_enabled=self.valve.is_enabled,
            fault_code=self.fault.code,
            fault_message=self.fault.message,
            mode=self.mode,
            sensor_ok=self.sensor_ok,
            communication_ok=self.fault.code != ErrorCode.COMMUNICATION_TIMEOUT,
            heater_on=self.heater.is_on,
            fan_auto_active=self.fan_auto_active,
            overtemperature_limit_c=self.config.safety.overtemperature_c,
            test_seconds_remaining=remaining,
        )

    def handle_command(self, request):
        self.safety.note_command_received()
        command = str(request.get("type", ""))
        try:
            if command == "ping":
                return {"type": "pong", "timestamp": monotonic()}
            if command == "get_status":
                return self._status_response()
            if command == "set_mode":
                requested = OperatingMode(str(request["mode"]))
                if self.fault.code != ErrorCode.NONE and requested != OperatingMode.FAULT:
                    raise RuntimeError("Fault active; acknowledge first.")
                self.mode = requested
                if requested != OperatingMode.AUTO:
                    self.heating_enabled = False
                if requested == OperatingMode.OFF:
                    self.heater.disable()
                    self.valve.disable()
                return self._ack()
            if command == "ack_fault":
                self._clear_fault()
                return self._ack()
            if command == "all_outputs_off":
                self.heating_enabled = False
                self.heater_test_until = None
                self.fan_enabled = False
                self.valve_enabled = False
                self.heater.disable()
                self.fan.disable()
                self.valve.disable()
                return self._ack()
            if command == "set_setpoint":
                self.pid.setpoint = float(request["value_c"])
                return self._ack()
            if command == "set_overtemperature_limit":
                self.config.safety.overtemperature_c = float(request["value_c"])
                return self._ack()
            if command == "set_heating":
                enabled = bool(request["enabled"])
                if enabled and self.mode != OperatingMode.AUTO:
                    raise RuntimeError("Heating can only be enabled in AUTO mode.")
                self.heating_enabled = enabled
                if not enabled:
                    self.heater.disable()
                return self._ack()
            if command == "set_fan":
                self.fan_enabled = bool(request["enabled"])
                return self._ack()
            if command == "set_valve":
                self.valve_enabled = bool(request["enabled"])
                return self._ack()
            if command == "heater_test":
                if self.mode != OperatingMode.TEST:
                    raise RuntimeError("Heater test requires TEST mode.")
                if not self.sensor_ok:
                    raise RuntimeError("Heater test requires sensor OK.")
                duration_s = min(float(request.get("duration_s", self.config.safety.heater_test_default_duration_s)), self.config.safety.heater_test_duration_limit_s)
                self.heater_test_until = monotonic() + duration_s
                return self._ack()
            if command == "set_pid":
                kp = float(request["kp"])
                ki = float(request["ki"])
                kd = float(request["kd"])
                setpoint_c = float(request["setpoint_c"])
                self.pid.update_parameters(kp, ki, kd, setpoint_c)
                return self._ack()
            raise RuntimeError(f"Unknown command: {command}")
        except Exception as exc:
            response = {"type": "error", "message": str(exc)}
            try:
                response["status"] = self._status_payload()
            except Exception:
                pass
            return response

    def _ack(self):
        payload = self._status_payload()
        payload["type"] = "ack"
        return payload

    def _status_response(self):
        payload = self._status_payload()
        payload["type"] = "status"
        return payload

    def _status_payload(self):
        status = self.build_status()
        return {
            "timestamp": status.timestamp,
            "temperature_c": status.temperature_c,
            "setpoint_c": status.setpoint_c,
            "heater_output_percent": status.heater_output_percent,
            "heating_enabled": status.heating_enabled,
            "fan_enabled": status.fan_enabled,
            "valve_enabled": status.valve_enabled,
            "fault_code": status.fault_code.value,
            "fault_message": status.fault_message,
            "mode": status.mode.value,
            "sensor_ok": status.sensor_ok,
            "communication_ok": status.communication_ok,
            "heater_on": status.heater_on,
            "fan_auto_active": status.fan_auto_active,
            "overtemperature_limit_c": status.overtemperature_limit_c,
            "test_seconds_remaining": status.test_seconds_remaining,
        }


def run_forever(config: MachineConfig) -> None:
    runtime = PicoRuntime(config)
    poller = select.poll() if select is not None else None
    if poller is not None:
        poller.register(sys.stdin, select.POLLIN)

    while True:
        try:
            runtime.tick()
            if poller is None:
                sleep(0.05)
                continue
            events = poller.poll(50)
            if not events:
                continue
            line = sys.stdin.readline()
            if not line:
                continue
            try:
                request = decode_message(line)
                response = runtime.handle_command(request)
            except Exception as exc:
                response = {"type": "error", "message": str(exc)}
            sys.stdout.write(encode_message(response).decode("utf-8"))
            _safe_flush_stdout()
        except Exception as exc:
            try:
                sys.stdout.write(encode_message({"type": "error", "message": str(exc)}).decode("utf-8"))
                _safe_flush_stdout()
            except Exception:
                pass
            sleep(0.1)
