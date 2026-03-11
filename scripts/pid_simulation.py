from __future__ import annotations

"""Kleine Konsolen-Demo fuer den PID-Regler.

Diese Datei spricht noch nicht mit echter Hardware.
Stattdessen simuliert sie einen beheizten Prozess ("Plant") und gibt jeden PID-Zyklus in der Konsole aus.

Warum diese Datei nuetzlich ist:
- Reglerparameter koennen getestet werden, ohne Hardware zu gefaehrden.
- Der Regelkreis wird verstaendlich, bevor echte Sensoren und Heizungen angeschlossen werden.
- ``pid_live_plot.py`` verwendet dieselbe Demo-Konfiguration erneut.

So kann die Simulation spaeter ersetzt werden:
- ``FirstOrderPlant`` wird durch Klassen ersetzt, die echte Temperatursensoren lesen
  und einen echten Heizausgang ansteuern.
- ``InjectionMachinePidController`` aus dem Paket kann bleiben. Er arbeitet bereits
  mit den abstrakten Schnittstellen ``SensorProtocol`` und ``ActuatorProtocol``.
"""

from dataclasses import dataclass
from time import sleep

from scripts._bootstrap import ensure_project_paths

# Macht das lokale Paket importierbar, wenn dieses Skript direkt gestartet wird.
ensure_project_paths()

from kolbenspritzgussmaschine.pid_control import (
    ActuatorProtocol,
    InjectionMachinePidController,
    PidConfig,
    SensorProtocol,
)


@dataclass(slots=True)
class FirstOrderPlant(SensorProtocol, ActuatorProtocol):
    """Sehr einfaches thermisches Prozessmodell fuer Tests.

    Das Modell nimmt an:
    - die Heizung bringt Energie ein, abhaengig vom aktuellen Ausgangswert
    - der Prozess verliert Waerme an die Umgebung

    Das ist nur eine grobe Annaeherung, reicht aber aus, um zu zeigen,
    wie der PID-Regler ueber die Zeit reagiert.

    Fuer echte Hardware spaeter gilt:
    - ``read()`` wuerde eine gemessene Temperatur vom Sensor holen
    - ``write()`` wuerde einen Leistungswert an Heiztreiber oder SSR senden
    - ``stop()`` wuerde die Heizung in einen sicheren Aus-Zustand bringen
    - ``step()`` wuerde entfallen, weil sich die reale Maschine selbst veraendert
    """
    ambient_temperature: float = 22.0
    process_value: float = 22.0
    heater_output: float = 0.0
    heater_gain: float = 1.4
    cooling_gain: float = 0.02

    def read(self) -> float:
        """Liefert den aktuellen simulierten Prozesswert.

        Fuer den PID-Regler sieht das genauso aus wie ein echter Sensorwert.
        """
        return self.process_value

    def write(self, value: float) -> None:
        """Speichert den Heizbefehl des Reglers.

        Der Ausgang wird auf 0 bis 100 Prozent begrenzt, damit sich der simulierte
        Aktor wie eine reale Heizansteuerung mit gueltigen Grenzen verhaelt.
        """
        self.heater_output = max(0.0, min(100.0, value))

    def stop(self) -> None:
        """Sicherer Zustand fuer den Aktor im Fehlerfall."""
        self.heater_output = 0.0

    def step(self, dt: float) -> float:
        """Fuehrt die Simulation um einen Zeitschritt weiter.

        ``heat_in`` beschreibt, wie stark die Heizung den Prozess erwaermt.
        ``cooling`` beschreibt, wie stark der Prozess Richtung Umgebungstemperatur abkuehlt.
        """
        heat_in = (self.heater_output / 100.0) * self.heater_gain
        cooling = (self.process_value - self.ambient_temperature) * self.cooling_gain
        self.process_value += (heat_in - cooling) * dt
        return self.process_value


def main() -> None:
    """Startet den simulierten Regelkreis und gibt Telemetriedaten in der Konsole aus."""
    sample_time, plant, controller = build_demo_controller()

    # Fuehrt eine feste Anzahl an Regelschritten aus, damit das Skript selbststaendig endet.
    for step in range(180):
        # 1) Simulierte Temperatur lesen
        # 2) PID-Regler neuen Heizwert berechnen lassen
        # 3) Diesen Wert wieder an die simulierte Anlage schreiben
        telemetry = controller.update_once()

        # Simulation weiterlaufen lassen, damit der naechste Durchlauf einen neuen Wert sieht.
        plant.step(sample_time)

        # Die wichtigsten Reglerwerte fuer Verstaendnis und Tuning ausgeben.
        print(
            f"{step:03d} "
            f"pv={telemetry.process_value:6.2f}C "
            f"sp={telemetry.setpoint:6.2f}C "
            f"out={telemetry.control_output:6.2f}% "
            f"err={telemetry.error:7.2f}"
        )
        sleep(sample_time)


def build_demo_controller() -> tuple[float, FirstOrderPlant, InjectionMachinePidController]:
    """Erzeugt eine lauffaehige Demo-Konfiguration fuer Konsole und Plot.

    Rueckgabewerte:
    - ``sample_time``: wie oft der Regelkreis ausgefuehrt wird
    - ``plant``: der simulierte Prozess
    - ``controller``: der PID-Wrapper fuer diesen Prozess

    Diese Funktion ist ein guter Ort, um mit PID-Parametern zu experimentieren.
    """
    sample_time = 0.2
    plant = FirstOrderPlant()
    controller = InjectionMachinePidController(
        sensor=plant,
        actuator=plant,
        config=PidConfig(
            # Diese Werte bestimmen, wie stark der Regler reagiert.
            kp=8.0,
            ki=0.7,
            kd=1.2,
            # Gewuenschte Zieltemperatur in Grad Celsius.
            setpoint=55.0,
            sample_time=sample_time,
            output_limits=(0.0, 100.0),
            starting_output=0.0,
        ),
    )
    return sample_time, plant, controller


if __name__ == "__main__":
    main()
