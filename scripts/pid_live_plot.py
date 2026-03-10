from __future__ import annotations

from collections import deque
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scripts.pid_simulation import build_demo_controller


def main() -> None:
    sample_time, plant, controller = build_demo_controller()
    history_seconds = 60.0
    history_length = max(50, int(history_seconds / sample_time))

    times = deque(maxlen=history_length)
    process_values = deque(maxlen=history_length)
    setpoints = deque(maxlen=history_length)
    outputs = deque(maxlen=history_length)

    fig, (ax_process, ax_output) = plt.subplots(2, 1, sharex=True, figsize=(11, 7))
    fig.suptitle("PID Live Plot")

    process_line, = ax_process.plot([], [], label="Istwert", linewidth=2.0)
    setpoint_line, = ax_process.plot([], [], label="Sollwert", linestyle="--", linewidth=1.5)
    output_line, = ax_output.plot([], [], label="Stellwert", color="tab:red", linewidth=2.0)

    ax_process.set_ylabel("Temperatur [C]")
    ax_output.set_ylabel("Stellwert [%]")
    ax_output.set_xlabel("Zeit [s]")
    ax_output.set_ylim(0.0, 100.0)
    ax_process.grid(True, alpha=0.3)
    ax_output.grid(True, alpha=0.3)
    ax_process.legend(loc="upper right")
    ax_output.legend(loc="upper right")

    elapsed_time = 0.0

    def update(_frame: int):
        nonlocal elapsed_time

        telemetry = controller.update_once()
        plant.step(sample_time)
        elapsed_time += sample_time

        times.append(elapsed_time)
        process_values.append(telemetry.process_value)
        setpoints.append(telemetry.setpoint)
        outputs.append(telemetry.control_output)

        x_values = list(times)
        process_line.set_data(x_values, list(process_values))
        setpoint_line.set_data(x_values, list(setpoints))
        output_line.set_data(x_values, list(outputs))

        if x_values:
            ax_process.set_xlim(max(0.0, x_values[0]), x_values[-1] + sample_time)
            process_min = min(min(process_values), min(setpoints))
            process_max = max(max(process_values), max(setpoints))
            margin = max(1.0, (process_max - process_min) * 0.15)
            ax_process.set_ylim(process_min - margin, process_max + margin)

        ax_process.set_title(
            f"Ist={telemetry.process_value:.2f} C | "
            f"Soll={telemetry.setpoint:.2f} C | "
            f"Stellwert={telemetry.control_output:.1f} %"
        )
        return process_line, setpoint_line, output_line

    anim = FuncAnimation(
        fig,
        update,
        interval=int(sample_time * 1000),
        blit=False,
        cache_frame_data=False,
    )
    fig._pid_animation = anim
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
