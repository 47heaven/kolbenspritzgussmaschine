]# Pico Upload

## MicroPython flashen

1. Pico abziehen.
2. `BOOTSEL` gedrueckt halten und Pico per USB verbinden.
3. Die passende MicroPython-`uf2` fuer den Raspberry Pi Pico auf das USB-Laufwerk kopieren.
4. Pico startet danach neu.

## Verbindung pruefen

1. Pico normal per USB verbinden.
2. Mit `mpremote connect auto repl` pruefen, ob eine REPL erreichbar ist.
3. Alternativ mit Thonny oder einem seriellen Terminal pruefen.

## Dateien auf den Pico kopieren

Empfohlen ist `mpremote`.
Unter Windows ggf. als `python -m mpremote ...` aufrufen, wenn `mpremote` nicht im `PATH` liegt.

Minimal benoetigte Dateien:

- `src/kolbenspritzgussmaschine/__init__.py`
- `src/kolbenspritzgussmaschine/config.py`
- `src/kolbenspritzgussmaschine/models.py`
- `src/kolbenspritzgussmaschine/safety_manager.py`
- `src/kolbenspritzgussmaschine/communication/__init__.py`
- `src/kolbenspritzgussmaschine/communication/protocol.py`
- `src/kolbenspritzgussmaschine/pico/__init__.py`
- `src/kolbenspritzgussmaschine/pico/max31865_sensor.py`
- `src/kolbenspritzgussmaschine/pico/heater_output.py`
- `src/kolbenspritzgussmaschine/pico/fan_output.py`
- `src/kolbenspritzgussmaschine/pico/valve_output.py`
- `src/kolbenspritzgussmaschine/pico/pid_loop.py`
- `src/kolbenspritzgussmaschine/pico/safety_manager.py`
- `src/kolbenspritzgussmaschine/pico/runtime.py`
- `src/kolbenspritzgussmaschine/pico/main.py`

## main.py korrekt platzieren

Der Pico soll am Ende ein `main.py` im Dateisystem haben, das die Runtime startet.
Das Hilfsskript `scripts/pico_upload_commands.ps1` zeigt die benoetigten `mpremote`-Befehle.

## Erster Test

1. Dateien kopieren.
2. Pico neu starten.
3. Auf dem Pi/PC `python scripts/serial_test_console.py` starten.
4. Erst `ping`, dann `status`, dann `mode test`.
5. Danach Sensor, Luefter, Ventil und erst ganz zum Schluss kurzen Heiztest pruefen.

## Hinweise

- Vor dem ersten Heiztest Sensorfunktion sicher pruefen.
- `pyserial` auf Pi/PC installieren: `pip install -r requirements.txt`
- TODO: Nach realem Test Kalibrierung und PID-Werte nachziehen.
