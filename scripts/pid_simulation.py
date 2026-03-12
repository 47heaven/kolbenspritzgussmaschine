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

from _bootstrap import ensure_project_paths

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
    """Einfaches thermisches Zwei-Zonen-Modell fuer Tests.

    Das Modell bildet zwei wichtige Beobachtungen aus eurem Aufbau ab:
    - die sensornahe Metallzone wird deutlich schneller warm als das innere Material
    - "Sensor auf Sollwert" bedeutet nicht automatisch, dass der Kern homogen warm ist

    Vereinfacht gibt es deshalb:
    - ``sensor_temperature``: heiznahe Wand-/Sensorzone
    - ``core_temperature``: traegerer Kern bzw. Materialbereich

    Fuer echte Hardware spaeter gilt:
    - ``read()`` wuerde eine gemessene Temperatur vom Sensor holen
    - ``write()`` wuerde einen Leistungswert an Heiztreiber oder SSR senden
    - ``stop()`` wuerde die Heizung in einen sicheren Aus-Zustand bringen
    - ``step()`` wuerde entfallen, weil sich die reale Maschine selbst veraendert
    """
    ambient_temperature: float = 22.0
    sensor_temperature: float = 22.0
    core_temperature: float = 22.0
    heater_output: float = 0.0
    heater_power_watts: float = 800.0
    wall_heat_capacity: float = 2200.0
    core_heat_capacity: float = 3200.0
    wall_loss_coefficient: float = 1.8
    core_loss_coefficient: float = 0.35
    wall_core_coupling: float = 6.0

    def read(self) -> float:
        """Liefert den aktuellen simulierten Prozesswert.

        Der Regler sieht hier bewusst nur die sensornahe Temperatur.
        Der eigentliche Kern kann dabei noch deutlich kuehler sein.
        """
        return self.sensor_temperature

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

        Energetische Idee:
        - die Heizleistung geht primaer in die metallnahe Zone
        - zwischen Wand und Kern fliesst Waerme nur begrenzt
        - beide Zonen verlieren Waerme an die Umgebung

        Dadurch laesst sich das reale Problem "heisse Wand, kalter Kern"
        wesentlich besser nachbilden als mit nur einem Temperaturwert.
        """
        heater_power = (self.heater_output / 100.0) * self.heater_power_watts
        wall_to_core = (self.sensor_temperature - self.core_temperature) * self.wall_core_coupling
        wall_loss = (self.sensor_temperature - self.ambient_temperature) * self.wall_loss_coefficient
        core_loss = (self.core_temperature - self.ambient_temperature) * self.core_loss_coefficient

        wall_net_power = heater_power - wall_to_core - wall_loss
        core_net_power = wall_to_core - core_loss

        self.sensor_temperature += (wall_net_power / self.wall_heat_capacity) * dt
        self.core_temperature += (core_net_power / self.core_heat_capacity) * dt
        return self.sensor_temperature

    @classmethod
    def empty_crucible(cls) -> "FirstOrderPlant":
        """Preset fuer den leeren Metallkoerper.

        Zielgroessen aus euren Angaben:
        - grob 4 bis 8 Minuten bis etwa 200 C
        - grob 6 bis 12 Minuten bis etwa 250 C
        """
        return cls(
            wall_heat_capacity=2000.0,
            core_heat_capacity=2600.0,
            wall_loss_coefficient=1.6,
            core_loss_coefficient=0.30,
            wall_core_coupling=7.5,
        )

    @classmethod
    def pla_shredder_charge(cls) -> "FirstOrderPlant":
        """Preset fuer einen gefuellten Tiegel mit PLA-Schredder.

        Das Material wird bewusst traeger modelliert:
        - die Wand wird frueh warm
        - der Kern folgt deutlich langsamer
        - nutzbare homogenere Schmelze braucht laenger plus Soak-Zeit
        """
        return cls(
            wall_heat_capacity=2400.0,
            core_heat_capacity=9000.0,
            wall_loss_coefficient=1.8,
            core_loss_coefficient=0.45,
            wall_core_coupling=2.2,
        )

    @classmethod
    def timelapse_demo(cls) -> "FirstOrderPlant":
        """Preset fuer eine kurze Vorfuehrung im Zeitraffer.

        Dieses Preset ist bewusst unrealistisch aggressiv ausgelegt, damit die
        sensornahe Zone bei einem 200-C-Sollwert in grob 30 Sekunden sichtbar
        hochlaeuft. Fuer reale Aussagen ueber das thermische Verhalten darf
        dieses Modell nicht verwendet werden.
        """
        return cls(
            heater_power_watts=2400.0,
            wall_heat_capacity=260.0,
            core_heat_capacity=520.0,
            wall_loss_coefficient=1.2,
            core_loss_coefficient=0.20,
            wall_core_coupling=12.0,
        )


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
    # Fuer die Vorfuehrung nutzen wir bewusst ein Zeitraffer-Preset.
    # Fuer realistischere Heizzeiten stattdessen ``empty_crucible()`` oder
    # ``pla_shredder_charge()`` verwenden.
    plant = FirstOrderPlant.timelapse_demo()
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
