from __future__ import annotations

from threading import Event, Lock, Thread
from time import monotonic, sleep
from typing import Callable, Protocol

from ..communication.client import PicoControllerClient
from ..config import MachineConfig, OperatingMode, RuntimeMode
from ..machine_controller import MachineController
from ..models import ErrorCode, MachineStatus
from ..simulated_hardware import SimulatedThermalPlant, build_simulated_machine


class MachineGateway(Protocol):
    mode: RuntimeMode

    def set_mode(self, mode: OperatingMode) -> None:
        ...

    def acknowledge_fault(self) -> None:
        ...

    def all_outputs_off(self) -> None:
        ...

    def set_target_temperature(self, value_c: float) -> None:
        ...

    def set_overtemperature_limit(self, value_c: float) -> None:
        ...

    def trigger_heater_test(self, duration_s: float) -> None:
        ...

    def set_pid_parameters(self, kp: float, ki: float, kd: float, setpoint_c: float) -> None:
        ...

    def set_heating_enabled(self, enabled: bool) -> None:
        ...

    def set_fan_enabled(self, enabled: bool) -> None:
        ...

    def set_valve_enabled(self, enabled: bool) -> None:
        ...

    def poll_status(self) -> MachineStatus:
        ...

    def shutdown(self) -> None:
        ...


class SimulationGateway:
    mode = RuntimeMode.SIMULATION

    def __init__(self, config: MachineConfig) -> None:
        self.config = config
        self.plant, hardware = build_simulated_machine(config)
        self.controller = MachineController(hardware, config)

    @property
    def simulated_plant(self) -> SimulatedThermalPlant:
        return self.plant

    def set_mode(self, mode: OperatingMode) -> None:
        self.controller.set_mode(mode)

    def acknowledge_fault(self) -> None:
        self.controller.acknowledge_fault()

    def all_outputs_off(self) -> None:
        self.controller.all_outputs_off()

    def set_target_temperature(self, value_c: float) -> None:
        self.controller.set_target_temperature(value_c)

    def set_overtemperature_limit(self, value_c: float) -> None:
        self.controller.set_overtemperature_limit(value_c)

    def trigger_heater_test(self, duration_s: float) -> None:
        self.controller.start_heater_test(duration_s)

    def set_pid_parameters(self, kp: float, ki: float, kd: float, setpoint_c: float) -> None:
        self.controller.update_pid_parameters(kp, ki, kd, setpoint_c)

    def set_heating_enabled(self, enabled: bool) -> None:
        self.controller.heating_enabled = enabled
        if enabled and self.controller.mode == OperatingMode.OFF:
            self.controller.set_mode(OperatingMode.AUTO)
        if not enabled and self.controller.mode == OperatingMode.AUTO:
            self.controller.heating_enabled = False

    def set_fan_enabled(self, enabled: bool) -> None:
        self.controller.set_fan_enabled(enabled)

    def set_valve_enabled(self, enabled: bool) -> None:
        self.controller.set_valve_enabled(enabled)

    def poll_status(self) -> MachineStatus:
        self.plant.advance(self.config.control_interval_s)
        return self.controller.tick()

    def shutdown(self) -> None:
        self.controller.all_outputs_off()


class PicoGateway:
    mode = RuntimeMode.SERIAL

    def __init__(self, client: PicoControllerClient) -> None:
        self.client = client

    def set_mode(self, mode: OperatingMode) -> None:
        self.client.set_mode(mode)

    def acknowledge_fault(self) -> None:
        self.client.acknowledge_fault()

    def all_outputs_off(self) -> None:
        self.client.all_outputs_off()

    def set_target_temperature(self, value_c: float) -> None:
        self.client.set_setpoint(value_c)

    def set_overtemperature_limit(self, value_c: float) -> None:
        self.client.set_overtemperature_limit(value_c)

    def trigger_heater_test(self, duration_s: float) -> None:
        self.client.trigger_heater_test(duration_s)

    def set_pid_parameters(self, kp: float, ki: float, kd: float, setpoint_c: float) -> None:
        self.client.set_pid_parameters(kp, ki, kd, setpoint_c)

    def set_heating_enabled(self, enabled: bool) -> None:
        self.client.set_heating_enabled(enabled)

    def set_fan_enabled(self, enabled: bool) -> None:
        self.client.set_fan_enabled(enabled)

    def set_valve_enabled(self, enabled: bool) -> None:
        self.client.set_valve_enabled(enabled)

    def poll_status(self) -> MachineStatus:
        return self.client.fetch_status()

    def shutdown(self) -> None:
        self.client.close()


class ControllerService:
    """Background polling service used by desktop or Raspberry Pi touch GUIs."""

    def __init__(self, gateway: MachineGateway, poll_interval_s: float = 0.2) -> None:
        self.gateway = gateway
        self.poll_interval_s = poll_interval_s
        self._latest_status = MachineStatus(
            timestamp=monotonic(),
            temperature_c=None,
            setpoint_c=0.0,
            heater_output_percent=0.0,
            heating_enabled=False,
            fan_enabled=False,
            valve_enabled=False,
        )
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._subscribers: list[Callable[[MachineStatus], None]] = []

    @property
    def mode(self) -> RuntimeMode:
        return self.gateway.mode

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.gateway.shutdown()

    def subscribe(self, callback: Callable[[MachineStatus], None]) -> None:
        self._subscribers.append(callback)

    def latest_status(self) -> MachineStatus:
        with self._lock:
            return self._latest_status

    def set_mode(self, mode: OperatingMode) -> None:
        self.gateway.set_mode(mode)

    def acknowledge_fault(self) -> None:
        self.gateway.acknowledge_fault()

    def all_outputs_off(self) -> None:
        self.gateway.all_outputs_off()

    def set_target_temperature(self, value_c: float) -> None:
        self.gateway.set_target_temperature(value_c)

    def set_overtemperature_limit(self, value_c: float) -> None:
        self.gateway.set_overtemperature_limit(value_c)

    def trigger_heater_test(self, duration_s: float) -> None:
        self.gateway.trigger_heater_test(duration_s)

    def set_pid_parameters(self, kp: float, ki: float, kd: float, setpoint_c: float) -> None:
        self.gateway.set_pid_parameters(kp, ki, kd, setpoint_c)

    def set_heating_enabled(self, enabled: bool) -> None:
        self.gateway.set_heating_enabled(enabled)

    def set_fan_enabled(self, enabled: bool) -> None:
        self.gateway.set_fan_enabled(enabled)

    def set_valve_enabled(self, enabled: bool) -> None:
        self.gateway.set_valve_enabled(enabled)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                status = self.gateway.poll_status()
            except Exception as exc:
                status = MachineStatus(
                    timestamp=monotonic(),
                    temperature_c=None,
                    setpoint_c=self.latest_status().setpoint_c,
                    heater_output_percent=0.0,
                    heating_enabled=False,
                    fan_enabled=True,
                    valve_enabled=False,
                    fault_code=ErrorCode.COMMUNICATION_TIMEOUT,
                    fault_message=str(exc),
                    mode=OperatingMode.FAULT,
                    sensor_ok=False,
                    communication_ok=False,
                    heater_on=False,
                    fan_auto_active=False,
                    overtemperature_limit_c=self.latest_status().overtemperature_limit_c,
                    test_seconds_remaining=0.0,
                )
            with self._lock:
                self._latest_status = status
            for callback in self._subscribers:
                callback(status)
            sleep(self.poll_interval_s)
