from __future__ import annotations

from pathlib import Path
import sys
from time import sleep

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from kolbenspritzgussmaschine.config import MachineConfig
from kolbenspritzgussmaschine.services.controller_service import SimulationGateway


def main() -> None:
    sample_time, gateway = build_demo_controller()

    for step in range(180):
        status = gateway.poll_status()
        print(
            f"{step:03d} "
            f"pv={status.temperature_c:6.2f}C "
            f"sp={status.setpoint_c:6.2f}C "
            f"out={status.heater_output_percent:6.2f}% "
            f"fault={status.fault_code.value}"
        )
        sleep(sample_time)


def build_demo_controller() -> tuple[float, SimulationGateway]:
    config = MachineConfig()
    config.pid.setpoint = 230.0
    config.pid.sample_time = config.control_interval_s
    gateway = SimulationGateway(config)
    gateway.set_target_temperature(config.pid.setpoint)
    gateway.set_heating_enabled(True)
    return config.control_interval_s, gateway


if __name__ == "__main__":
    main()
