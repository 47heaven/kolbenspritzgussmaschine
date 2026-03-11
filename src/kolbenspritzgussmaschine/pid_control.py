from __future__ import annotations

"""Zentrale PID-Bausteine fuer das Projekt der Kolbenspritzgussmaschine.

Dieses Modul enthaelt die wiederverwendbare Reglerlogik.
Die Dateien in ``scripts/`` zeigen nur, wie man diese Logik benutzt.

Grundidee:
- ``SensorProtocol`` legt fest, wie Temperaturdaten gelesen werden
- ``ActuatorProtocol`` legt fest, wie der Heizausgang beschrieben wird
- ``InjectionMachinePidController`` verbindet beides ueber einen PID-Regler

So wird das Modul spaeter auf echte Hardware angepasst:
- Eine konkrete Sensorklasse mit ``read()`` implementieren
- Eine konkrete Aktorklasse mit ``write()`` und ``stop()`` implementieren
- Diese Objekte an ``InjectionMachinePidController`` uebergeben
- Die restliche Reglerlogik kann unveraendert bleiben
"""

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Protocol

try:
    from simple_pid import PID
except ModuleNotFoundError:
    class PID:
        """Einfache Ersatzimplementierung, falls ``simple-pid`` nicht installiert ist.

        Dadurch bleibt das Beispielprojekt fuer Lernzwecke lauffaehig.
        Fuer den produktiven Einsatz ist das externe, getestete Paket vorzuziehen.
        """

        def __init__(
            self,
            kp: float,
            ki: float,
            kd: float,
            *,
            setpoint: float = 0.0,
            sample_time: float | None = 0.01,
            output_limits: tuple[float | None, float | None] = (None, None),
            starting_output: float = 0.0,
            proportional_on_measurement: bool = False,
            differential_on_measurement: bool = True,
        ) -> None:
            self.kp = kp
            self.ki = ki
            self.kd = kd
            self.setpoint = setpoint
            self.sample_time = sample_time
            self.output_limits = output_limits
            self.proportional_on_measurement = proportional_on_measurement
            self.differential_on_measurement = differential_on_measurement
            self.auto_mode = True

            self._last_time: float | None = None
            self._last_input: float | None = None
            self._last_error = 0.0
            self._last_output = self._clamp(starting_output)
            self._proportional = 0.0
            self._integral = self._clamp(starting_output)
            self._derivative = 0.0

        @property
        def components(self) -> tuple[float, float, float]:
            return self._proportional, self._integral, self._derivative

        def set_auto_mode(self, enabled: bool, last_output: float | None = None) -> None:
            self.auto_mode = enabled
            if enabled:
                self._last_time = None
                self._last_input = None
                self._last_error = 0.0
                if last_output is not None:
                    clamped = self._clamp(last_output)
                    self._last_output = clamped
                    self._integral = clamped

        def __call__(self, input_: float) -> float:
            if not self.auto_mode:
                return self._last_output

            now = monotonic()
            if self._last_time is None:
                dt = self.sample_time if self.sample_time is not None else 0.0
            else:
                dt = now - self._last_time
                if self.sample_time is not None and dt < self.sample_time:
                    return self._last_output

            error = self.setpoint - input_
            d_input = 0.0 if self._last_input is None else input_ - self._last_input
            d_error = error - self._last_error

            if self.proportional_on_measurement:
                self._proportional -= self.kp * d_input
            else:
                self._proportional = self.kp * error

            if dt > 0.0:
                self._integral += self.ki * error * dt
                if self.differential_on_measurement:
                    self._derivative = -(self.kd * d_input) / dt
                else:
                    self._derivative = (self.kd * d_error) / dt
            else:
                self._derivative = 0.0

            self._integral = self._clamp(self._integral)
            output = self._clamp(self._proportional + self._integral + self._derivative)

            self._last_output = output
            self._last_input = input_
            self._last_error = error
            self._last_time = now
            return output

        def _clamp(self, value: float) -> float:
            lower, upper = self.output_limits
            if lower is not None and value < lower:
                return lower
            if upper is not None and value > upper:
                return upper
            return value


class SensorProtocol(Protocol):
    """Minimale Schnittstelle fuer alles, was einen Prozesswert liefern kann."""

    def read(self) -> float:
        """Liefert den aktuellen Prozesswert."""


class ActuatorProtocol(Protocol):
    """Minimale Schnittstelle fuer alles, was einen Reglerausgang empfangen kann."""

    def write(self, value: float) -> None:
        """Uebergibt einen neuen Stellwert an den Aktor."""

    def stop(self) -> None:
        """Versetzt den Aktor in einen definierten sicheren Zustand."""


@dataclass(slots=True)
class PidConfig:
    """Konfigurationswerte fuer den PID-Regler.

    Wichtige Tuning-Felder:
    - ``kp``: staerkere unmittelbare Reaktion auf den aktuellen Fehler
    - ``ki``: gleicht langfristige Abweichungen aus
    - ``kd``: reagiert auf Aenderungsgeschwindigkeit und kann Ueberschwingen reduzieren
    """
    kp: float
    ki: float
    kd: float
    setpoint: float
    sample_time: float = 0.1
    output_limits: tuple[float | None, float | None] = (0.0, 100.0)
    starting_output: float = 0.0
    proportional_on_measurement: bool = False
    differential_on_measurement: bool = True


@dataclass(slots=True)
class PidTelemetry:
    """Momentaufnahme eines einzelnen Reglerzyklus.

    Das ist nuetzlich fuer:
    - Logging
    - Plotten
    - Debugging
    - spaeteres Weitergeben an eine GUI
    """
    timestamp: float
    process_value: float
    setpoint: float
    control_output: float
    error: float
    proportional: float
    integral: float
    derivative: float


class InjectionMachinePidController:
    """Erweitert die PID-Bibliothek um maschinenorientiertes Verhalten.

    Aufgaben dieser Klasse:
    - aktuellen Prozesswert vom Sensor lesen
    - neuen Stellwert berechnen
    - Stellwert an den Aktor senden
    - Telemetrie fuer Logs, Plots oder GUIs bereitstellen
    - den Aktor stoppen, wenn Daten zu alt werden
    """

    def __init__(
        self,
        sensor: SensorProtocol,
        actuator: ActuatorProtocol,
        config: PidConfig,
        *,
        max_stale_seconds: float = 1.0,
    ) -> None:
        # ``sensor`` und ``actuator`` koennen heute Simulationen und spaeter reale Hardware sein.
        self.sensor = sensor
        self.actuator = actuator
        self.config = config
        self.max_stale_seconds = max_stale_seconds
        self._last_update = 0.0

        # Erzeugt das eigentliche PID-Objekt mit den gewaehlten Reglerparametern.
        self._pid = PID(
            config.kp,
            config.ki,
            config.kd,
            setpoint=config.setpoint,
            sample_time=config.sample_time,
            output_limits=config.output_limits,
            starting_output=config.starting_output,
            proportional_on_measurement=config.proportional_on_measurement,
            differential_on_measurement=config.differential_on_measurement,
        )

    @property
    def pid(self) -> PID:
        """Gibt das rohe PID-Objekt frei, falls spaeter feiner getunt werden soll."""
        return self._pid

    def set_setpoint(self, value: float) -> None:
        """Aendert den Sollwert waehrend der Regler laeuft."""
        self._pid.setpoint = value

    def enable(self, last_output: float | None = None) -> None:
        """Aktiviert den automatischen PID-Betrieb.

        ``last_output`` kann beim Wiedereinschalten uebergeben werden, um einen harten Sprung zu vermeiden.
        """
        self._pid.set_auto_mode(True, last_output=last_output)

    def disable(self) -> None:
        """Deaktiviert die automatische Regelung und setzt den Aktor in einen sicheren Zustand."""
        self._pid.auto_mode = False
        self.actuator.stop()

    def update_once(self) -> PidTelemetry:
        """Fuehrt genau einen Reglerzyklus aus.

        Reihenfolge:
        1. Sensorwert lesen
        2. PID-Ausgang berechnen
        3. Ausgang an den Aktor schreiben
        4. Telemetriedaten fuer Anzeige oder Auswertung zurueckgeben
        """
        process_value = self.sensor.read()
        output = float(self._pid(process_value))
        self.actuator.write(output)

        now = monotonic()
        self._last_update = now
        proportional, integral, derivative = self._pid.components
        return PidTelemetry(
            timestamp=now,
            process_value=process_value,
            setpoint=float(self._pid.setpoint),
            control_output=output,
            error=float(self._pid.setpoint - process_value),
            proportional=float(proportional),
            integral=float(integral),
            derivative=float(derivative),
        )

    def assert_fresh(self) -> None:
        """Loest einen Sicherheitsfehler aus, wenn der Regelkreis zu lange nicht aktualisiert wurde.

        In einer realen Maschine schuetzt das vor Situationen, in denen das Programm haengt,
        die Heizung aber sonst auf dem letzten Ausgangswert stehen bleiben wuerde.
        """
        if monotonic() - self._last_update > self.max_stale_seconds:
            self.disable()
            raise TimeoutError("PID loop data is stale; actuator was stopped.")

    def run_forever(self) -> None:
        """Fuehrt den Regelkreis dauerhaft mit der konfigurierten Zykluszeit aus.

        Das ist die einfachste Form einer spaeteren Produktionsschleife.
        In einer groesseren Anwendung koennte stattdessen ``update_once()`` aus
        einem eigenen Thread, Prozess oder Async-Task heraus aufgerufen werden.
        """
        while True:
            self.update_once()
            sleep(self.config.sample_time)

