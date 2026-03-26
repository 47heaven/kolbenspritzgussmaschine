# Hardware-Architektur

## Zielbild

- Raspberry Pi: Touch-GUI, Logging, Sollwerte, Benutzerinteraktion und USB-Serial zum Pico
- Raspberry Pi Pico: Sensorlesen, Ausgaenge, Safety und einfache Temperaturregelung in MicroPython

## Konkrete Hardwarekonfiguration

### Temperatursensor

- PT100
- 2-Leiter
- MAX31865 Adafruit PT100-Board
- Pico SPI:
  - GPIO18 = CLK
  - GPIO16 = MISO / SDO
  - GPIO19 = MOSI / SDI
  - GPIO17 = CS
- 50-Hz-Filter vorbereitet
- Rref zentral in `config.py`, vorbelegt fuer das Adafruit-Board
- TODO: Rref und Kabel-/Sensorabweichung mit realer Hardware verifizieren

### Ausgaenge

- GPIO2 = Heizung
- GPIO3 = Luefter
- GPIO4 = Pneumatikventil
- alle active high

### Betriebsmodi

- `OFF`
- `TEST`
- `AUTO`
- `FAULT`

## Python-Paketstruktur

- `src/kolbenspritzgussmaschine/config.py`: zentrale Konfiguration fuer PID, Sensor, Safety, Pins und Kommunikation
- `src/kolbenspritzgussmaschine/models.py`: Status- und Fehlerobjekte, Betriebsmodi
- `src/kolbenspritzgussmaschine/services/controller_service.py`: Pi-seitige Service-/Gateway-Schicht
- `src/kolbenspritzgussmaschine/communication/`: JSON-Line-Protokoll fuer USB-Serial
- `src/kolbenspritzgussmaschine/pico/`: MicroPython-Module fuer Sensor, IO, PID und Mainloop
- `scripts/pid_touch_ui.py`: Hauptoberflaeche plus separates Service-/Testfenster

## Pi <-> Pico Protokoll

Transport: USB-Serial, eine JSON-Nachricht pro Zeile.

Kommandos:

- `{"type":"ping"}`
- `{"type":"get_status"}`
- `{"type":"set_mode","mode":"test"}`
- `{"type":"ack_fault"}`
- `{"type":"all_outputs_off"}`
- `{"type":"set_setpoint","value_c":200.0}`
- `{"type":"set_overtemperature_limit","value_c":250.0}`
- `{"type":"set_heating","enabled":true}`
- `{"type":"set_fan","enabled":true}`
- `{"type":"set_valve","enabled":false}`
- `{"type":"heater_test","duration_s":2.0}`
- `{"type":"set_pid","kp":8.0,"ki":0.7,"kd":1.2,"setpoint_c":200.0}`

Statusantwort enthaelt zusaetzlich:

- `mode`
- `sensor_ok`
- `communication_ok`
- `heater_on`
- `fan_auto_active`
- `overtemperature_limit_c`
- `test_seconds_remaining`

## TODO fuer echte Hardware

- PT100-/MAX31865-Kalibrierung mit realen Vergleichsmessungen
- PID-Tuning an der realen Heizzone
- Grenzwert fuer Luefter-Automatik validieren
- Entscheidung, ob Spaeter mehr als eine Heizzone benoetigt wird
