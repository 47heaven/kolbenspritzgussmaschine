from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from time import sleep

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from kolbenspritzgussmaschine.pid_control import (
    ActuatorProtocol,
    InjectionMachinePidController,
    PidConfig,
    SensorProtocol,
)


@dataclass(slots=True)
class FirstOrderPlant(SensorProtocol, ActuatorProtocol):
    ambient_temperature: float = 22.0
    process_value: float = 22.0
    heater_output: float = 0.0
    heater_gain: float = 1.4
    cooling_gain: float = 0.02

    def read(self) -> float:
        return self.process_value

    def write(self, value: float) -> None:
        self.heater_output = max(0.0, min(100.0, value))

    def stop(self) -> None:
        self.heater_output = 0.0

    def step(self, dt: float) -> float:
        heat_in = (self.heater_output / 100.0) * self.heater_gain
        cooling = (self.process_value - self.ambient_temperature) * self.cooling_gain
        self.process_value += (heat_in - cooling) * dt
        return self.process_value


def main() -> None:
    sample_time, plant, controller = build_demo_controller()

    for step in range(180):
        telemetry = controller.update_once()
        plant.step(sample_time)
        print(
            f"{step:03d} "
            f"pv={telemetry.process_value:6.2f}C "
            f"sp={telemetry.setpoint:6.2f}C "
            f"out={telemetry.control_output:6.2f}% "
            f"err={telemetry.error:7.2f}"
        )
        sleep(sample_time)


def build_demo_controller() -> tuple[float, FirstOrderPlant, InjectionMachinePidController]:
    sample_time = 0.2
    plant = FirstOrderPlant()
    controller = InjectionMachinePidController(
        sensor=plant,
        actuator=plant,
        config=PidConfig(
            kp=8.0,
            ki=0.7,
            kd=1.2,
            setpoint=55.0,
            sample_time=sample_time,
            output_limits=(0.0, 100.0),
            starting_output=0.0,
        ),
    )
    return sample_time, plant, controller


if __name__ == "__main__":
    main()
