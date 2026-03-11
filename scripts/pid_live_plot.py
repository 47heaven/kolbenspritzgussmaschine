from __future__ import annotations

"""Animierter Plot fuer die PID-Simulation.

Diese Datei visualisiert dieselbe Demo-Konfiguration wie ``pid_simulation.py``:
- aktueller Prozesswert ("Istwert")
- Zielwert ("Sollwert")
- Reglerausgang ("Stellwert")

Warum diese Datei nuetzlich ist:
- Ueberschwingen, Einschwingzeit und Schwingen sind schneller erkennbar als in Textform.
- Sie hilft beim Tuning der PID-Werte, bevor echte Hardware angeschlossen wird.

So geht der spaetere Weg zu realen Daten:
- Die Plot-Logik kann bleiben.
- Die simulierte Datenquelle wird durch einen Regler ersetzt, der echte Sensorwerte liest
  und einen echten Aktor ansteuert.
- Der Plot braucht nur aktuelle Telemetriedaten. Ob sie aus der Simulation oder aus
  der Maschine kommen, ist ihm egal.
"""

from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from scripts._bootstrap import ensure_project_paths

# Fuer dieses Skript werden sowohl Projektwurzel als auch ``src`` im Importpfad benoetigt,
# weil sowohl aus ``scripts`` als auch aus dem Paket unter ``src`` importiert wird.
ensure_project_paths(include_project_root=True)

from scripts.pid_simulation import build_demo_controller


def main() -> None:
    """Startet die Simulation und aktualisiert den Plot fortlaufend."""
    sample_time, plant, controller = build_demo_controller()
    history_seconds = 60.0

    # Es wird nur ein gleitendes Zeitfenster gespeichert, damit der Plot lesbar bleibt.
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
        """Berechnet einen neuen Regelschritt und zeichnet die Daten neu."""
        nonlocal elapsed_time

        # Der PID-Regler berechnet aus der aktuellen Temperatur einen neuen Stellwert.
        telemetry = controller.update_once()

        # Die Simulation wird weitergefuehrt, damit der naechste Frame neue Werte sieht.
        plant.step(sample_time)
        elapsed_time += sample_time

        # Die neuesten Werte werden in den Verlaufsspeichern abgelegt.
        times.append(elapsed_time)
        process_values.append(telemetry.process_value)
        setpoints.append(telemetry.setpoint)
        outputs.append(telemetry.control_output)

        x_values = list(times)

        # Die neuen Daten werden an die Matplotlib-Linienobjekte uebergeben.
        process_line.set_data(x_values, list(process_values))
        setpoint_line.set_data(x_values, list(setpoints))
        output_line.set_data(x_values, list(outputs))

        if x_values:
            # Der sichtbare Bereich wird automatisch angepasst, damit das Verhalten gut lesbar bleibt.
            ax_process.set_xlim(max(0.0, x_values[0]), x_values[-1] + sample_time)
            process_min = min(min(process_values), min(setpoints))
            process_max = max(max(process_values), max(setpoints))
            margin = max(1.0, (process_max - process_min) * 0.15)
            ax_process.set_ylim(process_min - margin, process_max + margin)

        # Die aktuellen Werte stehen zusaetzlich im Diagrammtitel.
        ax_process.set_title(
            f"Ist={telemetry.process_value:.2f} C | "
            f"Soll={telemetry.setpoint:.2f} C | "
            f"Stellwert={telemetry.control_output:.1f} %"
        )
        return process_line, setpoint_line, output_line

    # Matplotlib ruft ``update`` periodisch auf. Das ist hier der sichtbare Demo-Regelkreis.
    anim = FuncAnimation(
        fig,
        update,
        interval=int(sample_time * 1000),
        blit=False,
        cache_frame_data=False,
    )

    # Die Referenz bleibt erhalten, damit Python die Animation nicht vorzeitig entfernt.
    fig._pid_animation = anim
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
