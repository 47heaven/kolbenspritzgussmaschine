# Architektur-Ueberblick

Diese Datei ist fuer Personen gedacht, die das Projekt uebernehmen, warten oder weiterentwickeln sollen. Ziel ist nicht nur zu sagen, welche Dateien es gibt, sondern zu erklaeren, warum sie existieren, wie sie zusammenspielen und wo man bei Problemen oder Erweiterungen ansetzen sollte.

## 1. Ziel dieses Projekts

Die Software bildet den aktuellen Steuerungs- und Bedienstand einer Kolbenspritzgussmaschine ab. Im Mittelpunkt steht zurzeit die Temperaturregelung einer beheizten Zone. Das Projekt ist so aufgebaut, dass Entwicklung und Tests zuerst in einer sicheren Simulation moeglich sind und spaeter dieselbe Logik mit echter Hardware genutzt werden kann.

Die Grundidee ist:

- moeglichst viel Logik hardwareunabhaengig halten
- Simulation und echte Hardware ueber dieselben Bedienpfade nutzbar machen
- Sicherheitszustand klar definieren
- GUI, Kommunikationsschicht und Hardwarelogik voneinander trennen

## 2. Gesamtsystem in einfachen Worten

Das System besteht aus zwei Seiten:

### Host-Seite

Das ist der PC oder spaeter ein Raspberry Pi mit Bildschirm.

Auf dieser Seite laufen:

- die Touch-GUI
- Testscripte
- Service- und Gateway-Logik
- im Simulationsfall auch die lokale Maschinenlogik
- im echten Betrieb die serielle Kommunikation zum Pico

### Pico-Seite

Das ist der Raspberry Pi Pico mit MicroPython.

Auf dieser Seite laufen:

- Sensoranbindung
- Ausgangsansteuerung
- lokale Temperaturregelung
- Safety-Funktionen
- Kommandoverarbeitung ueber USB-Serial

## 3. Warum die Architektur so aufgeteilt wurde

Die Trennung hat mehrere Vorteile:

- Die GUI muss nicht wissen, ob sie mit Simulation oder echter Hardware spricht.
- Die Fachlogik kann lokal getestet werden, ohne Heizung oder Sensor anzuschliessen.
- Die Pico-Seite bleibt klein und nahe an der Hardware.
- Kommunikationsfehler lassen sich sauber von eigentlichen Regelungsfehlern trennen.

Kurz gesagt: dieselbe Bedienung soll mit zwei verschiedenen "Maschinenquellen" funktionieren.

## 4. Wichtige Ebenen der Software

Die Software kann man in sechs Ebenen aufteilen:

1. Bedienung
2. Service/Gateway
3. Maschinenlogik
4. Hardware-Abstraktion
5. Kommunikation
6. Pico-Runtime

### 4.1 Bedienung

Datei:

- `scripts/pid_touch_ui.py`

Diese Datei ist die Hauptoberflaeche des Projekts. Sie ist aktuell der wichtigste Einstiegspunkt fuer Bedienung und Demonstration.

Die GUI uebernimmt vor allem:

- Anzeigen von Temperatur, Sollwert und Heizleistung
- Wechsel zwischen Profilen
- Starten und Stoppen des Heizbetriebs
- Oeffnen eines Service-/Testfensters
- Auswahl bzw. Neuverbindung eines seriellen Ports
- Fallback in den Simulationsmodus, wenn kein Pico erreichbar ist

Wichtig fuer Nachfolger:

- Die GUI ist vergleichsweise gross und vereint viel Oberflaechenlogik in einer Datei.
- Sie enthaelt nicht die eigentliche Maschinenregelung, sondern spricht ueber `ControllerService` mit der dahinterliegenden Logik.
- Bei Refactorings sollte man Bedienlogik und Maschinenlogik weiterhin getrennt halten.

### 4.2 Service/Gateway-Schicht

Datei:

- `src/kolbenspritzgussmaschine/services/controller_service.py`

Diese Schicht ist das Bindeglied zwischen GUI und Maschine.

Die zentrale Idee:

- Die GUI spricht nur mit einem `ControllerService`.
- Der `ControllerService` benutzt intern ein Gateway.
- Es gibt aktuell zwei Gateway-Typen:
  - `SimulationGateway`
  - `PicoGateway`

#### Aufgabe von `ControllerService`

Der Service:

- pollt zyklisch den aktuellen Status
- speichert den letzten bekannten `MachineStatus`
- kapselt Fehler bei der Kommunikation
- stellt einfache Methoden fuer die GUI bereit

Beispiele:

- `set_mode(...)`
- `set_target_temperature(...)`
- `set_pid_parameters(...)`
- `set_fan_enabled(...)`
- `latest_status()`

Der grosse Vorteil fuer die GUI ist: sie muss nicht selbst Threads, Serial-Fehler oder Simulationsobjekte verwalten.

#### Aufgabe von `SimulationGateway`

Das `SimulationGateway` verbindet den Service mit:

- einer simulierten Anlage
- einem lokalen `MachineController`

Das ist ideal fuer:

- Entwicklung ohne Hardware
- Debugging der GUI
- erstes PID-Verstaendnis

#### Aufgabe von `PicoGateway`

Das `PicoGateway` reicht Befehle an den Pico weiter und holt den aktuellen Status ueber die serielle JSON-Schnittstelle ab.

Wichtig:

- Der Host regelt in diesem Fall nicht selbst die Temperatur.
- Der Pico ist dann die operative Laufzeit fuer Sensor, Safety und Heizausgabe.

### 4.3 Maschinenlogik auf Host-/Simulationsseite

Datei:

- `src/kolbenspritzgussmaschine/machine_controller.py`

Der `MachineController` ist die zentrale fachliche Logik fuer die lokale Maschine im Simulationsbetrieb.

Hier passiert:

- Moduswechsel zwischen `OFF`, `TEST`, `AUTO`, `FAULT`
- Aktivieren und Deaktivieren des PID-Reglers
- Start eines begrenzten Heiztests
- Fan-Automatik
- Fault-Behandlung
- Aufbau eines einheitlichen `MachineStatus`

Das ist eine wichtige Datei, weil sie sehr gut zeigt, wie die Maschine fachlich gedacht ist.

#### Typischer Ablauf in `tick()`

Bei jedem Zyklus passiert im Wesentlichen:

1. Temperatur lesen
2. Plausibilitaet und Sicherheitsgrenzen pruefen
3. ggf. Fan-Automatik anwenden
4. je nach Modus:
   - PID-Regelung
   - Heiztest
   - alles aus
5. Statusobjekt zurueckgeben

#### Fault-Logik

Wenn ein Fehler erkannt wird:

- wechselt die Maschine in `FAULT`
- Heizung wird deaktiviert
- Ventil wird geschlossen
- Luefter wird in den sicheren Zustand gebracht

Das macht die Maschine berechenbarer und erleichtert spaetere Hardwaretests.

### 4.4 Hardware-Abstraktion

Dateien:

- `src/kolbenspritzgussmaschine/interfaces.py`
- `src/kolbenspritzgussmaschine/simulated_hardware.py`

Diese Ebene sorgt dafuer, dass die Regelung nicht direkt an konkrete Sensor- oder GPIO-Klassen gekoppelt ist.

Es gibt abstrakte Rollen fuer:

- Temperatursensor
- Heizung
- Luefter
- Ventil

Diese Rollen werden in `MachineHardware` gebuendelt.

#### Warum das wichtig ist

Wenn spaeter echte Hardware ersetzt oder erweitert wird, muss nicht der gesamte Regler umgebaut werden. Stattdessen implementiert man passende Klassen, die dieselbe Schnittstelle erfuellen.

#### Simulation

`simulated_hardware.py` stellt eine einfache thermische Modellanlage bereit:

- Heizung erhoeht die Temperatur
- passive Kuehlung senkt sie
- Luefter und Ventil beeinflussen den Waermeverlust
- Sensorrauschen wird leicht simuliert

Das Modell ist absichtlich einfach. Es dient nicht als exaktes physikalisches Abbild, sondern als sichere Entwicklungsumgebung.

### 4.5 PID-Kern

Datei:

- `src/kolbenspritzgussmaschine/pid_control.py`

Hier liegt der wiederverwendbare Temperaturregler.

Wesentliche Aufgaben:

- Einbindung von `simple-pid` oder einer Fallback-Implementierung
- Setzen des Sollwerts
- Aktivieren/Deaktivieren des Reglers
- Berechnung des Stellwerts
- Rueckgabe von Telemetriedaten

Der PID-Kern kennt nur:

- einen Sensor
- einen Aktor
- eine Konfiguration

Er kennt dagegen nicht:

- GUI
- Serial-Kommunikation
- Touch-Bedienung
- konkrete Hardwarepins

Das ist eine saubere Trennung.

### 4.6 Safety

Datei:

- `src/kolbenspritzgussmaschine/safety_manager.py`

Der `SafetyManager` uebernimmt Sicherheitspruefungen wie:

- Temperatur unter plausibler Untergrenze
- Temperatur ueber plausibler Obergrenze
- Uebertemperatur
- Kommunikationszeitueberschreitung

Wichtig zu verstehen:

- Im aktuellen Stand sind die Safety-Regeln schon angelegt, aber reale Grenzwerte muessen weiter validiert werden.
- Die Softwarestruktur ist vorbereitet, die reale Inbetriebnahme ist trotzdem ein eigener, vorsichtiger Arbeitsschritt.

## 5. Kommunikation zwischen Host und Pico

Dateien:

- `src/kolbenspritzgussmaschine/communication/protocol.py`
- `src/kolbenspritzgussmaschine/communication/client.py`

Die Kommunikation ist bewusst einfach gehalten:

- Transport: USB-Serial
- Format: JSON
- genau eine Nachricht pro Zeile

### Beispielprinzip

Der Host sendet zum Beispiel:

```json
{"type":"set_mode","mode":"auto"}
```

Der Pico antwortet mit einem Ack oder mit einem Status-/Fehlerobjekt.

### Wichtige Kommandos

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

### Warum dieses Protokoll praktisch ist

- leicht lesbar
- gut mit Testtools pruefbar
- einfach fuer GUI und Testkonsole nutzbar
- auf dem Pico ohne schwere Zusatzbibliotheken umsetzbar

## 6. Pico-Seite im Detail

Wichtige Dateien:

- `src/kolbenspritzgussmaschine/pico/main.py`
- `src/kolbenspritzgussmaschine/pico/runtime.py`
- `src/kolbenspritzgussmaschine/pico/max31865_sensor.py`
- `src/kolbenspritzgussmaschine/pico/heater_output.py`
- `src/kolbenspritzgussmaschine/pico/fan_output.py`
- `src/kolbenspritzgussmaschine/pico/valve_output.py`
- `src/kolbenspritzgussmaschine/pico/pid_loop.py`
- `src/kolbenspritzgussmaschine/pico/safety_manager.py`

### Rolle von `main.py`

`main.py` baut die Pico-Konfiguration auf:

- Sensorparameter
- Pinbelegung
- Taktung der Regelung
- Sicherheitsgrenzen

Danach startet `main.py` die Endlosschleife der Runtime.

### Rolle von `runtime.py`

`PicoRuntime` ist das Herz der Pico-Seite. Hier laufen zusammen:

- Sensor lesen
- Heizleistung berechnen
- Fan- und Ventilausgaenge schalten
- Fault-Handling
- Verarbeitung eingehender JSON-Kommandos
- Aufbau des Status fuer den Host

Man kann `PicoRuntime` als "kleinen lokalen Maschinencontroller auf dem Mikrocontroller" verstehen.

### Wichtiger Unterschied zum Simulationsbetrieb

Im Simulationsbetrieb liegt die fachliche Regelung auf dem Host in `MachineController`.

Im echten Serial-Betrieb liegt die operative Regelung auf dem Pico in `PicoRuntime`.

Das ist gewollt, weil der Pico naeher an der Hardware sitzt und auch dann noch kontrolliert handeln kann, wenn die Host-Seite gerade langsam ist oder die GUI haengt.

## 7. Konfiguration

Datei:

- `src/kolbenspritzgussmaschine/config.py`

Hier werden fast alle wichtigen Einstellobjekte definiert.

### Wichtige Konfigurationsklassen

- `MachineConfig`: Sammelobjekt fuer das Gesamtsystem
- `PidConfig`: PID-Parameter und Regeltakt
- `TemperatureSensorConfig`: PT100/PT1000 und MAX31865-bezogene Parameter
- `SafetyConfig`: Grenzwerte und Timeouts
- `HeaterOutputConfig`: Ausgang, Zeittakt, Einschwingrampe
- `FanControlConfig`: automatische Luefterlogik
- `SerialConfig`: serielle Schnittstelle

### Warum das wichtig ist

Wenn spaeter ein Nachfolger Parameter anpassen muss, sollte der erste Blick fast immer nach `config.py` gehen und nicht direkt in die GUI oder in irgendwelche Einzelmodule.

## 8. Gemeinsame Datenmodelle

Datei:

- `src/kolbenspritzgussmaschine/models.py`

Diese Datei definiert die fachlichen Datenobjekte, die mehrere Teile des Systems gemeinsam verwenden.

Besonders wichtig:

- `MachineStatus`
- `FaultState`
- `ErrorCode`

### Warum `MachineStatus` zentral ist

`MachineStatus` ist das gemeinsame Format fuer:

- GUI-Anzeige
- Service-Rueckgabe
- Simulation
- Pico-Statusantworten

Wenn man verstehen will, welche Zustandsinformationen das System kennt, ist diese Datei einer der besten Einstiege.

## 9. Datenfluss von der GUI bis zur Heizung

Der wichtigste Gesamtfluss sieht so aus:

### Fall A: Simulation

1. Benutzer aendert etwas in der GUI
2. GUI ruft Methode am `ControllerService` auf
3. `ControllerService` spricht mit `SimulationGateway`
4. `SimulationGateway` benutzt `MachineController`
5. `MachineController` arbeitet mit Simulationssensor und Simulationsaktor
6. Ergebnis kommt als `MachineStatus` zurueck zur GUI

### Fall B: Echter Pico-Betrieb

1. Benutzer aendert etwas in der GUI
2. GUI ruft Methode am `ControllerService` auf
3. `ControllerService` spricht mit `PicoGateway`
4. `PicoGateway` sendet JSON ueber `PicoControllerClient`
5. `PicoRuntime` verarbeitet das Kommando
6. Pico liefert Status zurueck
7. GUI aktualisiert ihre Anzeige

## 10. Welche Dateien man wofuer oeffnen sollte

### Wenn die GUI komisch aussieht oder falsch reagiert

- `scripts/pid_touch_ui.py`

### Wenn Befehle in Simulation und Live-Betrieb gleich aussehen sollen

- `src/kolbenspritzgussmaschine/services/controller_service.py`

### Wenn Moduswechsel, Faults oder Heiztests unklar sind

- `src/kolbenspritzgussmaschine/machine_controller.py`

### Wenn Grenzwerte oder Reglerparameter angepasst werden sollen

- `src/kolbenspritzgussmaschine/config.py`

### Wenn Serial-Kommunikation nicht funktioniert

- `src/kolbenspritzgussmaschine/communication/client.py`
- `src/kolbenspritzgussmaschine/communication/protocol.py`
- `scripts/serial_test_console.py`

### Wenn echte Hardware auf dem Pico Probleme macht

- `src/kolbenspritzgussmaschine/pico/runtime.py`
- `src/kolbenspritzgussmaschine/pico/main.py`
- zugehoerige Sensor-/Output-Dateien im `pico/`-Ordner

## 11. Typische Missverstaendnisse beim Einsteigen

### "Die GUI regelt doch die Temperatur direkt, oder?"

Nicht unbedingt.

- In der Simulation: indirekt ja, ueber `MachineController`
- Im Serial-Betrieb: nein, dort regelt der Pico

### "Ist `SIMULATION` das gleiche wie `OFF`, `AUTO` oder `TEST`?"

Nein.

- `SIMULATION` und `SERIAL` beschreiben die technische Laufumgebung
- `OFF`, `TEST`, `AUTO`, `FAULT` beschreiben den fachlichen Maschinenzustand

### "Warum gibt es PID-Code auf Host und Pico?"

Weil das Projekt beide Welten unterstuetzt:

- lokal testbare Simulationswelt
- echte hardware-nahe Welt auf dem Pico

## 12. Bekannte Grenzen des aktuellen Stands

Ein Nachfolger sollte wissen, dass das Projekt funktional weit ist, aber noch nicht in allen Punkten real validiert wurde.

Vor allem offen oder kritisch:

- echte Kalibrierung des PT100/MAX31865
- Validierung von `Rref`
- reale Ueberpruefung der Overtemperature-Grenze
- PID-Tuning an der echten Heizzone
- Langzeittest der Kommunikation
- reale Erprobung von Fan-Automatik und Heiztest

## 13. Empfohlene Arbeitsweise fuer Nachfolger

Wenn du neu weitermachst, ist dieses Vorgehen robust:

1. Erst Architektur und Datenfluss verstehen
2. GUI nur oberflaechlich anpassen, solange Hardwarethemen offen sind
3. Simulation sauber nutzbar halten
4. echte Hardware nur in kleinen Schritten testen
5. Safety-Grenzen vor aggressivem Heizen pruefen
6. Aenderungen immer daraufhin beurteilen, ob Simulation und Serial-Betrieb weiter zusammenpassen

## 14. Empfohlene erste Lesereihenfolge im Code

1. `README.md`
2. `docs/uebergabe-stand-2026-03-26.md`
3. `scripts/pid_touch_ui.py`
4. `src/kolbenspritzgussmaschine/services/controller_service.py`
5. `src/kolbenspritzgussmaschine/machine_controller.py`
6. `src/kolbenspritzgussmaschine/config.py`
7. `src/kolbenspritzgussmaschine/models.py`
8. `src/kolbenspritzgussmaschine/communication/client.py`
9. `src/kolbenspritzgussmaschine/pico/runtime.py`

## 15. Kurzfazit

Das Projekt ist bereits so aufgebaut, dass ein Nachfolger nicht bei null anfangen muss. Die wichtigste Leitidee lautet:

- Bedienung von Technik trennen
- Simulation und reale Hardware ueber gemeinsame Schnittstellen verbinden
- sichere Zustaende klar definieren
- kleine, nachvollziehbare Bausteine statt ungetrennter Gesamtlogik verwenden

Wenn man diese Grundidee im Kopf behaelt, wird der Rest des Repositories deutlich leichter verstaendlich.
