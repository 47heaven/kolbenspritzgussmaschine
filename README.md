# Kolbenspritzgussmaschine

Dieses Repository enthaelt den aktuellen Software-Prototyp fuer eine studentisch entwickelte Kolbenspritzgussmaschine.

Der Schwerpunkt liegt im Moment auf der Temperaturregelung eines beheizten Systems mit einem PID-Regler. Noch arbeitet der Code mit einer Simulation. Die Struktur ist aber bereits so vorbereitet, dass spaeter reale Sensoren und Aktoren angebunden werden koennen.

## Ziel des Projekts

Die Maschine soll Kunststoff erhitzen und kontrolliert verarbeiten. Damit das sicher und reproduzierbar funktioniert, muss die Temperatur zuverlaessig geregelt werden.

Dafuer wird ein PID-Regler verwendet:
- Der Sensor liefert den aktuellen Istwert.
- Der Regler vergleicht Istwert und Sollwert.
- Daraus wird ein Stellwert fuer die Heizung berechnet.
- Die Heizung beeinflusst den Prozess.

## Aktueller Stand

Der aktuelle Code ist ein Lern- und Entwicklungsstand mit folgenden Bausteinen:
- ein wiederverwendbarer PID-Controller im Paket unter `src/`
- eine einfache thermische Simulation als Ersatz fuer reale Hardware
- ein Konsolenskript zur Beobachtung des Regelverhaltens
- ein Live-Plot zur Visualisierung von Istwert, Sollwert und Stellwert

## Projektstruktur

- `src/kolbenspritzgussmaschine/pid_control.py`
  Zentrale Reglerlogik mit Konfiguration, Telemetrie und Sicherheitsfunktionen.

- `src/kolbenspritzgussmaschine/__init__.py`
  Oeffentliche Paket-API fuer Importe aus anderen Modulen.

- `scripts/pid_simulation.py`
  Startet eine einfache Simulation und gibt Reglerwerte in der Konsole aus.

- `scripts/pid_live_plot.py`
  Zeigt die simulierten Reglerdaten als Live-Diagramm mit Matplotlib.

- `scripts/_bootstrap.py`
  Hilfsdatei, damit die Skripte beim direkten Starten die lokalen Module finden.

## So funktioniert der Regelkreis

Vereinfacht laeuft ein Zyklus so ab:

1. Der Sensor liefert einen Temperaturwert.
2. Der PID-Regler berechnet daraus einen neuen Stellwert.
3. Der Stellwert wird an die Heizung weitergegeben.
4. Die Temperatur aendert sich.
5. Der naechste Zyklus beginnt.

Im aktuellen Projekt wird dieser Ablauf nicht mit echter Hardware, sondern mit einer simulierten Anlage getestet.

## Installation

Voraussetzungen:
- Python 3
- `pip`

Abhaengigkeiten installieren:

```bash
pip install -r requirements.txt
```

Aktuell wird benoetigt:
- `simple-pid`
- fuer den Plot zusaetzlich `matplotlib`

Falls `matplotlib` noch fehlt:

```bash
pip install matplotlib
```

## Beispiele ausfuehren

Simulation in der Konsole starten:

```bash
python scripts/pid_simulation.py
```

Live-Plot starten:

```bash
python scripts/pid_live_plot.py
```

## Bedeutung der wichtigsten Begriffe

- Istwert:
  Der aktuell gemessene Wert, zum Beispiel die aktuelle Temperatur.

- Sollwert:
  Der Zielwert, den der Regler erreichen soll.

- Stellwert:
  Das Ausgangssignal des Reglers, zum Beispiel die Heizleistung in Prozent.

- PID:
  Eine Reglerart aus drei Anteilen:
  proportional, integral und differential.

## Wie der Umbau auf reale Hardware spaeter aussieht

Die vorhandene Struktur ist absichtlich so aufgebaut, dass der Kern des Reglers erhalten bleiben kann.

Spaeter muessen vor allem diese Teile ersetzt werden:
- Die Simulationsklasse `FirstOrderPlant` durch echte Hardwareklassen
- Das Lesen des Prozesswerts durch einen echten Temperatursensor
- Das Schreiben des Stellwerts an einen echten Heiztreiber oder ein SSR

Die zentrale Idee dabei:
- Eine Sensorklasse implementiert `read()`
- Eine Aktorklasse implementiert `write()` und `stop()`
- Beide werden an `InjectionMachinePidController` uebergeben

Damit kann dieselbe Reglerlogik weiterverwendet werden, egal ob die Daten aus einer Simulation oder von der realen Maschine kommen.

## Sicherheit

Bei realer Hardware muss Sicherheit deutlich strenger behandelt werden als in der aktuellen Simulation.

Wichtige Punkte fuer spaeter:
- Abschalten bei Sensorfehlern
- Abschalten bei ueberhoehter Temperatur
- Abschalten bei haengendem oder zu langsamem Regelkreis
- definierter sicherer Zustand fuer die Heizung

Im Code gibt es dafuer bereits erste Struktur, zum Beispiel ueber `stop()` und `assert_fresh()`.

## Naechste sinnvolle Schritte

- Reale Sensor- und Aktorklassen anlegen
- Messwerte sauber loggen
- Grenzwerte und Fehlerfaelle explizit behandeln
- GUI oder Bedienoberflaeche getrennt vom Regler aufbauen
- PID-Werte mit realen Messdaten abstimmen
