# PID-Regelung fuer die Kolbenspritzgussmaschine

## Geeignete Python-Basis

Als bestehende Grundlage eignet sich `simple-pid` gut:

- GitHub: <https://github.com/m-lundberg/simple-pid>
- Doku: <https://simple-pid.readthedocs.io/en/latest/user_guide.html>

Warum passend:

- keine externen Laufzeitabhaengigkeiten
- `sample_time`, `output_limits` und `auto_mode` sind direkt eingebaut
- `output_limits` begrenzt den Stellwert und reduziert Integral-Windup
- `components` liefert P-, I- und D-Anteil zum Tuning

## Wie der Regelkreis fuer deine Maschine aussieht

Der Aufbau ist immer gleich:

1. Sensor lesen
2. Istwert mit Sollwert vergleichen
3. PID berechnet den Stellwert
4. Stellwert auf Heizung, Ventil, Pumpe oder Servo schreiben
5. Mit fester Zykluszeit wiederholen

Typische Groessen fuer eine Kolbenspritzgussmaschine:

- Temperaturregelung der Heizzone
- Druckregelung beim Einspritzen
- Positions- oder Geschwindigkeitsregelung des Kolbens

Fuer den ersten Einstieg ist Temperaturregelung am einfachsten, weil das System traeger und damit gut beherrschbar ist.

## Projektdateien

- `src/kolbenspritzgussmaschine/pid_control.py`: wiederverwendbarer PID-Controller
- `scripts/pid_simulation.py`: einfache Temperatursimulation zum Starten und Tuning

## Integration auf echter Hardware

Du musst nur zwei Schnittstellen anbinden:

- `SensorProtocol.read()`: liest den Istwert, zum Beispiel Druck in bar oder Temperatur in Grad Celsius
- `ActuatorProtocol.write(value)`: schreibt den Stellwert, zum Beispiel PWM 0 bis 100 Prozent

Wichtig fuer reale Hardware:

- feste Zykluszeit, zum Beispiel 50 ms bis 200 ms
- harte Stellwertgrenzen
- sichere Stop-Funktion in `ActuatorProtocol.stop()`
- Watchdog oder Timeout, falls Messwerte ausbleiben
- niemals direkt auf Produktbetrieb tunen

## Praktisches Vorgehen beim Tuning

1. Erst nur `Kp` erhoehen, bis die Groesse schnell reagiert, aber noch nicht stark schwingt.
2. Dann `Ki` langsam erhoehen, bis die bleibende Regelabweichung verschwindet.
3. `Kd` nur so weit erhoehen, dass Ueberschwingen und Zittern kleiner werden.
4. Messwerte und `pid.components` loggen.
5. Mit kleinen Sollwertspruengen testen, erst danach mit realen Lastwechseln.

## Beispielstart

```powershell
$env:PYTHONPATH = "E:\\vsCode\\kolbenspritzgussmaschine\\src"
.\\.venv\\Scripts\\python.exe .\\scripts\\pid_simulation.py
```

Danach ersetzt du die Simulationsklasse durch deine echten Sensor- und Aktuator-Klassen.

## Live-Plot in Echtzeit

Fuer eine grafische Darstellung gibt es `scripts/pid_live_plot.py`.

```powershell
.\\.venv\\Scripts\\python.exe .\\scripts\\pid_live_plot.py
```

Das Fenster zeigt:

- Istwert
- Sollwert
- Stellwert in Prozent

Das gleiche Muster kannst du spaeter mit deinen echten Messdaten verwenden, indem du statt der Simulation deinen realen Sensor und Aktuator an den Controller haengst.
