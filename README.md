# Kolbenspritzgussmaschine

Dieses Repository enthaelt den aktuellen Softwarestand fuer eine studentisch entwickelte Kolbenspritzgussmaschine. Der Schwerpunkt liegt auf der Temperaturregelung, der Bedienoberflaeche und der Anbindung echter Hardware ueber einen Raspberry Pi Pico.

Die Dokumentation in dieser `README.md` ist der Einstieg fuer neue Personen im Projekt. Wenn du das System wirklich uebernehmen, erweitern oder in Betrieb nehmen willst, lies danach unbedingt auch die ausfuehrliche Architektur-Doku:

- [Architektur-Ueberblick](docs/architektur-ueberblick.md)

## Worum es in diesem Projekt geht

Die Maschine soll Kunststoff kontrolliert erwaermen und spaeter sicher verarbeiten. Damit das funktioniert, muss die Temperatur:

- gemessen werden
- mit einem Sollwert verglichen werden
- ueber die Heizung geregelt werden
- unter Sicherheitsgrenzen bleiben

Die Software ist so aufgebaut, dass sie in zwei Betriebswelten funktionieren kann:

- `Simulation`: fuer Entwicklung, Tests und UI-Arbeit ohne echte Hardware
- `Serial`: fuer den Betrieb mit Raspberry Pi oder PC als Bediengeraet und einem Raspberry Pi Pico als Hardware-Controller

## Fuer Nachfolger zuerst wichtig

Wenn du neu in das Projekt einsteigst, ist diese Reihenfolge sinnvoll:

1. Diese `README.md` lesen
2. [docs/architektur-ueberblick.md](docs/architektur-ueberblick.md) lesen
3. [docs/uebergabe-stand-2026-03-26.md](docs/uebergabe-stand-2026-03-26.md) lesen
4. Danach erst die wichtigsten Dateien im Code oeffnen:
   - `scripts/pid_touch_ui.py`
   - `src/kolbenspritzgussmaschine/services/controller_service.py`
   - `src/kolbenspritzgussmaschine/machine_controller.py`
   - `src/kolbenspritzgussmaschine/pico/runtime.py`

## Aktueller Funktionsumfang

Der aktuelle Stand umfasst bereits mehr als nur eine einfache PID-Demo:

- Touch-GUI als zentrale Bedienoberflaeche
- Simulationsmodus fuer Entwicklung ohne reale Maschine
- Service-Schicht zwischen GUI und Maschine
- Desktop-/Pi-seitige Regel- und Sicherheitslogik
- serielle JSON-Kommunikation zwischen Host und Pico
- Pico-Runtime in MicroPython fuer Sensor, Ausgaenge und lokale Regelung
- mehrere Hilfsskripte fuer Simulation, Plotting, Upload und serielle Tests

## Schnellstart

### Voraussetzungen

- Python 3
- `pip`
- fuer echten Serial-Betrieb: `pyserial`
- fuer Plot-Skripte: `matplotlib`

Installation:

```bash
pip install -r requirements.txt
```

## Wichtige Startpunkte

### 1. Hauptoberflaeche starten

```bash
python scripts/pid_touch_ui.py
```

Die GUI versucht standardmaessig zuerst, sich mit einem Pico ueber Serial zu verbinden. Falls das nicht klappt, startet sie automatisch im Simulationsmodus.

### 2. Reine Simulation in der Konsole

```bash
python scripts/pid_simulation.py
```

### 3. Live-Plot fuer das Regelverhalten

```bash
python scripts/pid_live_plot.py
```

### 4. Serielle Testkonsole fuer Pico-Kommandos

```bash
python scripts/serial_test_console.py
```

## Projektstruktur auf einen Blick

### `scripts/`

Hier liegen die direkt startbaren Werkzeuge.

- `pid_touch_ui.py`: wichtigste GUI, fuer Bedienung und Service/Test
- `pid_simulation.py`: einfacher Simulationseinstieg
- `pid_live_plot.py`: grafische Darstellung von Temperatur, Sollwert und Heizleistung
- `serial_test_console.py`: serielle Testkommunikation mit dem Pico
- `pico_upload_commands.ps1`: Befehle fuer Dateiuebertragung auf den Pico

### `src/kolbenspritzgussmaschine/`

Hier liegt die eigentliche Anwendungslogik.

- `config.py`: zentrale Konfigurationsobjekte
- `models.py`: Status- und Fehlerdaten
- `interfaces.py`: Hardware-Abstraktionen und Adapter
- `pid_control.py`: wiederverwendbarer PID-Kern
- `machine_controller.py`: zentrale Logik fuer Moduswechsel, Safety und Regelung
- `simulated_hardware.py`: einfache thermische Simulationshardware
- `safety_manager.py`: Plausibilitaets- und Sicherheitspruefungen
- `services/controller_service.py`: Hintergrund-Service fuer GUI und Gateways
- `communication/`: Serial-Protokoll und Client
- `pico/`: MicroPython-Code fuer den Raspberry Pi Pico

### `docs/`

Hier liegt die weiterfuehrende Dokumentation.

- `architektur-ueberblick.md`: neue Einsteiger- und Nachfolger-Doku
- `uebergabe-stand-2026-03-26.md`: Uebergabestatus und offene Punkte
- `hardware-architektur.md`: Hardwarezuordnung und Protokoll
- `hardware-test.md`: Testschritte fuer reale Hardware
- `pico-upload.md`: Upload-Anleitung fuer MicroPython/Pico
- `pid-regelung.md`: Hintergrund zur PID-Regelung

## Wie das System grob funktioniert

Vereinfacht arbeitet das Projekt in diesem Ablauf:

1. Die GUI oder ein Testskript gibt Sollwerte oder Befehle vor.
2. Ein `ControllerService` spricht mit einem Gateway.
3. Das Gateway arbeitet entweder:
   - lokal gegen die Simulation oder
   - ueber Serial gegen den Pico
4. Temperaturdaten und Ausgangszustaende werden als `MachineStatus` zurueckgeliefert.
5. Die GUI zeigt diese Werte an und erlaubt weitere Bedienung.

Wichtig: Die Desktop-Seite und die Pico-Seite sind bewusst entkoppelt. Dadurch kann dieselbe Bedienlogik sowohl mit Simulation als auch mit echter Hardware arbeiten.

## Betriebsmodi

Es gibt vier fachliche Maschinenmodi:

- `OFF`: alles sicher aus, keine aktive Regelung
- `TEST`: manuelle Tests, z. B. kurzer Heiztest
- `AUTO`: normale automatische Temperaturregelung
- `FAULT`: Fehlerzustand, Ausgaenge werden in sicheren Zustand gebracht

Zusaetzlich gibt es zwei technische Laufmodi:

- `SIMULATION`
- `SERIAL`

Diese beiden Begriffe sollte man nicht verwechseln:

- `AUTO/OFF/TEST/FAULT` beschreiben den Maschinenzustand
- `SIMULATION/SERIAL` beschreiben, woher Messwerte und Aktoren kommen

## Hardwarebild

Das aktuelle Zielbild ist:

- Host-Seite:
  - PC oder Raspberry Pi
  - GUI
  - Logging
  - Sollwerte
  - USB-Serial-Verbindung
- Pico-Seite:
  - PT100 ueber MAX31865 lesen
  - Heizung schalten
  - Luefter schalten
  - Ventil schalten
  - Safety lokal absichern

Aktuell dokumentierte Pinbelegung:

- GPIO2 = Heizung
- GPIO3 = Luefter
- GPIO4 = Ventil
- GPIO18 = SPI CLK
- GPIO16 = SPI MISO
- GPIO19 = SPI MOSI
- GPIO17 = SPI CS

## Wichtige Begriffe fuer Einsteiger

- `Istwert`: aktuell gemessene Temperatur
- `Sollwert`: Zieltemperatur
- `Stellwert`: Ausgang des Reglers, hier Heizleistung in Prozent
- `PID`: Regler aus proportionalem, integralem und differentialem Anteil
- `Gateway`: Schicht, die dieselbe Bedienlogik entweder mit Simulation oder echter Hardware verbindet
- `MachineStatus`: gemeinsames Statusobjekt fuer GUI, Services und Kommunikation

## Was fuer reale Hardware besonders kritisch ist

Die Software ist vorbereitet, aber reale Inbetriebnahme braucht Vorsicht. Besonders wichtig sind:

- Sensorfehler sauber erkennen
- Uebertemperatur abfangen
- Kommunikationsausfall beruecksichtigen
- Heiztests nur kurz und kontrolliert ausfuehren
- Grenzwerte mit realer Hardware verifizieren
- PID-Werte nicht blind aus der Simulation uebernehmen

## Empfehlenswerte Lesereihenfolge im Code

Wenn du das Projekt verstehen willst, hilft diese Reihenfolge:

1. `scripts/pid_touch_ui.py`
2. `src/kolbenspritzgussmaschine/services/controller_service.py`
3. `src/kolbenspritzgussmaschine/machine_controller.py`
4. `src/kolbenspritzgussmaschine/config.py`
5. `src/kolbenspritzgussmaschine/models.py`
6. `src/kolbenspritzgussmaschine/interfaces.py`
7. `src/kolbenspritzgussmaschine/pid_control.py`
8. `src/kolbenspritzgussmaschine/communication/client.py`
9. `src/kolbenspritzgussmaschine/pico/runtime.py`

## Offene Themen

Nach aktuellem Stand sind insbesondere diese Punkte noch wichtig:

- reale Sensor-Kalibrierung
- Validierung von `Rref` und PT100-Anbindung
- PID-Tuning an der echten Heizzone
- echte Serial-Inbetriebnahme mit Pico
- Absicherung und Test des Heizbetriebs
- spaeter sauberes Logging und Betriebsprotokollierung

## Weiterfuehrende Dokumentation

- [Architektur-Ueberblick](docs/architektur-ueberblick.md)
- [Uebergabe-Stand](docs/uebergabe-stand-2026-03-26.md)
- [Hardware-Architektur](docs/hardware-architektur.md)
- [Hardware-Test](docs/hardware-test.md)
- [Pico-Upload](docs/pico-upload.md)
- [PID-Regelung](docs/pid-regelung.md)
