# Uebergabe: Kolbenspritzgussmaschine

Stand: 2026-03-26

## Kurzfassung

Dieses Repository wurde von einer reinen PID-/Simulationsbasis in Richtung echter Hardware fuer eine Desktop-Spritzgussmaschine erweitert.

Wichtig:

- Die bestehende GUI wurde bewusst **nicht** durch ein neues Minimal-Frontend ersetzt.
- Die Hauptoberflaeche bleibt `scripts/pid_touch_ui.py`.
- Der Service-/Testmodus ist ein **separates Fenster** innerhalb dieser GUI.
- Die Architekturtrennung bleibt bestehen:
  - GUI / Bedienung
  - Service / Gateway
  - Domaaenenlogik / Regelung
  - Hardware-Abstraktion
  - Pi <-> Pico Kommunikation
  - Pico-Runtime fuer echte Hardware

## Zielarchitektur

- Raspberry Pi / PC:
  - GUI
  - Logging
  - Sollwerte
  - USB-Serial-Kommunikation zum Pico
- Raspberry Pi Pico mit MicroPython:
  - MAX31865 / PT100 lesen
  - Heizung ansteuern
  - Luefter ansteuern
  - Ventil ansteuern
  - Safety
  - einfache lokale Regelungslogik

## Konkrete Hardwarekonfiguration

### Temperatursensor

- PT100
- 2-Leiter
- MAX31865 Adafruit PT100-Board
- SPI am Pico:
  - GPIO18 = CLK
  - GPIO16 = MISO / SDO
  - GPIO19 = MOSI / SDI
  - GPIO17 = CS
- 50-Hz-Filter vorbereitet
- Rref zentral in `src/kolbenspritzgussmaschine/config.py`

### Ausgaenge

- GPIO2 = Heizung
- GPIO3 = Luefter
- GPIO4 = Pneumatikventil
- alle active high

### Heizung

- 24 V
- 4 x 200 W Heizpatronen
- aktuell als eine Heizzone
- zeitproportionale Ansteuerung, keine hochfrequente PWM
- Regel-/Schalttakt vorbereitet ueber:
  - `control_interval_s = 0.5`
  - `time_window_s = 2.0`
- initiale Overtemperature-Grenze: `250 C`

### Betriebsmodi

- `OFF`
- `TEST`
- `AUTO`
- `FAULT`

## Wichtigste Dateien und aktueller Zweck

### GUI / Bedienung

- `scripts/pid_touch_ui.py`
  - Hauptoberflaeche
  - historische GUI-Struktur weitgehend wiederhergestellt
  - Service-/Testfenster integriert
- `scripts/pid_live_plot.py`
  - separater Live-Plot fuer Simulation
- `scripts/pid_simulation.py`
  - lokale Simulationsbasis
- `scripts/serial_test_console.py`
  - serielle Testkonsole fuer direkte Pico-Kommandos ohne GUI
- `scripts/pico_upload_commands.ps1`
  - mpremote-Befehlsliste fuer Pico-Dateiuebertragung

### Dokumentation

- `docs/pid-regelung.md`
  - PID-Grundlagen / bisherige Simulationsdoku
- `docs/hardware-architektur.md`
  - konkrete Hardwarearchitektur und Protokoll
- `docs/hardware-test.md`
  - Schritt-fuer-Schritt-Hardwaretest
- `docs/pico-upload.md`
  - MicroPython-/Upload-Anleitung

### Gemeinsame Python-Architektur

- `src/kolbenspritzgussmaschine/config.py`
  - zentrale Konfiguration fuer Sensor, IO, PID, Safety, Serial
- `src/kolbenspritzgussmaschine/models.py`
  - `MachineStatus`, `FaultState`, `ErrorCode`
- `src/kolbenspritzgussmaschine/interfaces.py`
  - Hardware-Abstraktionen
- `src/kolbenspritzgussmaschine/pid_control.py`
  - bestehender PID-Kern auf Python-Seite
- `src/kolbenspritzgussmaschine/machine_controller.py`
  - hardwareunabhaengige Regel-/Mode-/Safety-Logik fuer Simulation/Desktop
- `src/kolbenspritzgussmaschine/simulated_hardware.py`
  - Mock-/Simulationshardware
- `src/kolbenspritzgussmaschine/safety_manager.py`
  - zentrale Safety-Pruefungen

### Kommunikation Pi <-> Pico

- `src/kolbenspritzgussmaschine/communication/protocol.py`
  - JSON-Line-Protokoll
- `src/kolbenspritzgussmaschine/communication/client.py`
  - USB-Serial-Client mit `pyserial`
- `src/kolbenspritzgussmaschine/services/controller_service.py`
  - `SimulationGateway`
  - `PicoGateway`
  - `ControllerService`

### Pico-seitige Runtime

- `src/kolbenspritzgussmaschine/pico/max31865_sensor.py`
- `src/kolbenspritzgussmaschine/pico/heater_output.py`
- `src/kolbenspritzgussmaschine/pico/fan_output.py`
- `src/kolbenspritzgussmaschine/pico/valve_output.py`
- `src/kolbenspritzgussmaschine/pico/pid_loop.py`
- `src/kolbenspritzgussmaschine/pico/safety_manager.py`
- `src/kolbenspritzgussmaschine/pico/runtime.py`
- `src/kolbenspritzgussmaschine/pico/main.py`

## Protokoll: aktuell implementierte Kommandos

Die serielle JSON-Line-Schnittstelle unterstuetzt aktuell:

- `ping`
- `get_status`
- `set_mode`
- `ack_fault`
- `all_outputs_off`
- `set_setpoint`
- `set_overtemperature_limit`
- `set_heating`
- `set_fan`
- `set_valve`
- `heater_test`
- `set_pid`

Der Status enthaelt u. a.:

- `mode`
- `temperature_c`
- `setpoint_c`
- `heater_output_percent`
- `heater_on`
- `fan_enabled`
- `valve_enabled`
- `sensor_ok`
- `communication_ok`
- `fault_code`
- `fault_message`
- `fan_auto_active`
- `overtemperature_limit_c`
- `test_seconds_remaining`

## GUI-Status

Die GUI ist absichtlich **nicht** neu erfunden worden.

Wichtig fuer weitere Arbeit:

- `scripts/pid_touch_ui.py` ist die Hauptoberflaeche.
- Der `SERVICE`-Button oeffnet das getrennte Test-/Servicefenster.
- Dort sind vorbereitet:
  - Moduswechsel `OFF / TEST / AUTO`
  - Fault quittieren
  - Luefter EIN/AUS
  - Ventil EIN/AUS
  - kurzer Heiztest
  - `Alles AUS`
  - Overtemperature setzen
  - Live-Anzeige von Temperatur / sensor_ok / mode / outputs / fault

## Was bereits lokal verifiziert wurde

Erfolgreich geprueft:

- Syntax-/Compile-Smoke-Tests fuer `src` und `scripts`
- Simulations-/Service-Logik lokal
- Protokoll-/Client-Test mit Mock-Transport
- GUI-Start nach mehreren Reparaturen
- `pyserial` wurde in der lokalen `.venv` installiert
- `scripts/serial_test_console.py` startet und findet serielle Ports

## Was noch **nicht** real verifiziert wurde

Noch offen auf echter Hardware:

- MicroPython tatsaechlich auf Pico aufgespielt
- Dateien tatsaechlich auf Pico uebertragen
- `main.py` auf Pico getestet
- echter USB-Serial-Handshake mit Pico
- echter Sensorwert vom MAX31865/PT100
- echter Luefter-/Ventiltest
- echter Heiztest
- Kalibrierung / PID-Tuning / Safety-Grenzen gegen reale Hardware

## Wichtige TODOs

- PT100/MAX31865 mit realem Sensor kalibrieren
- Rref des Adafruit-Boards real verifizieren
- PID-Werte fuer die echte Heizzone abstimmen
- Overtemperature-Grenze und plausible Temperaturgrenzen real pruefen
- Fan-Automatikschwelle real testen
- echte Dauerlauf-/Kommunikationsverlusttests ausfuehren

## Bekannte Hinweise

- `pyserial` ist notwendig fuer echte USB-Serial-Kommunikation.
- Der serielle Test auf Windows hat zunaechst `COM1` gefunden; das muss nicht der Pico sein.
- In der Testkonsole duerfen nur deren eigene Befehle eingegeben werden, keine normalen PowerShell-Befehle.
- Die `__pycache__`-/`.pyc`-Dateien sind nicht relevant fuer die eigentliche Logik.

## Empfohlene naechste Schritte auf dem anderen Geraet

1. Repo oeffnen.
2. `.venv` aktivieren.
3. `pip install -r requirements.txt`
4. `scripts/serial_test_console.py` pruefen
5. Pico per USB anschliessen
6. richtigen Port finden
7. `ping` und `status` testen
8. Pico-Dateien per `mpremote` uebertragen
9. Sensor testen
10. Luefter/Ventil testen
11. erst ganz am Schluss kurzer Heiztest

## Kontext fuer die naechste Codex-Session

Wenn du auf dem anderen Geraet mit Codex weiterarbeitest, sollte Codex wissen:

- Keine groessere GUI-Neuerfindung gewuenscht
- Hauptoberflaeche unbedingt erhalten
- Service-/Gateway-/Controller-Architektur beibehalten
- Fokus jetzt auf pragmatischer Inbetriebnahme echter Hardware
- Kleine, robuste Schritte bevorzugen
- Keine unnoetigen Frameworks

## Wenn als naechstes weiterentwickelt werden soll

Sinnvolle naechste Aufgaben:

- echten Pico-Upload testen
- echten USB-Serial-Port anbinden
- Sensor lesen
- Fault-/Safety-Verhalten real pruefen
- Heiztest absichern
- Logging auf dem Raspberry Pi ergaenzen
