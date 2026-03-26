# Hardwaretest Schritt fuer Schritt

## 1. Pico vorbereiten

1. Pico noch nicht mit Heizung unter Last verbinden.
2. PT100/MAX31865, Luefter und Ventil zuerst ohne Heizung pruefen.
3. GPIO-Zuordnung gegen Schaltplan gegenpruefen:
   - Heizung = GPIO2
   - Luefter = GPIO3
   - Ventil = GPIO4
   - MAX31865: CLK=18, MISO=16, MOSI=19, CS=17

## 2. MicroPython aufspielen

1. Pico per USB anschliessen.
2. MicroPython-Firmware aufspielen.
3. Mit Thonny oder `mpremote` pruefen, dass eine REPL erreichbar ist.

## 3. Dateien uebertragen

Mindestens auf den Pico kopieren:

- `src/kolbenspritzgussmaschine/config.py`
- `src/kolbenspritzgussmaschine/models.py`
- `src/kolbenspritzgussmaschine/communication/protocol.py`
- `src/kolbenspritzgussmaschine/pico/max31865_sensor.py`
- `src/kolbenspritzgussmaschine/pico/heater_output.py`
- `src/kolbenspritzgussmaschine/pico/fan_output.py`
- `src/kolbenspritzgussmaschine/pico/valve_output.py`
- `src/kolbenspritzgussmaschine/pico/pid_loop.py`
- `src/kolbenspritzgussmaschine/pico/safety_manager.py`
- `src/kolbenspritzgussmaschine/pico/runtime.py`
- `src/kolbenspritzgussmaschine/pico/main.py`

Pragmatisch fuer den Test: `main.py` auf dem Pico als Startdatei ablegen.

## 4. USB-Serial testen

1. Pico an den Raspberry Pi oder PC anschliessen.
2. Passenden Port pruefen, z. B. `/dev/ttyACM0` auf Linux/Raspberry Pi.
3. Testweise JSON senden:

```json
{"type":"ping"}
```

Erwartung: `pong`-Antwort.

4. Dann Status abfragen:

```json
{"type":"get_status"}
```

## 5. Sensor testen

1. Nur Sensor anschliessen, Heizung noch deaktiviert lassen.
2. Im GUI-Servicefenster oder per Statuskommando Temperatur beobachten.
3. Temperatur vorsichtig mit Hand-/Umgebungseinfluss veraendern und Plausibilitaet pruefen.
4. Bei sofortigem `sensor_fault`: Verdrahtung, PT100-Typ, 2-Leiter-Konfiguration und SPI pruefen.
5. TODO: Temperatur mit Referenzthermometer gegenpruefen.

## 6. Luefter/Ventil testen

1. Modus auf `TEST` setzen.
2. Luefter EIN/AUS pruefen.
3. Ventil EIN/AUS pruefen.
4. Danach `Alles AUS` senden.
5. Fehlerfall kurz simulieren oder Kommunikation trennen und pruefen:
   - Heizung AUS
   - Ventil AUS
   - Luefter EIN

## 7. Heizung vorsichtig testen

1. Heizung erst anschliessen, wenn Sensor stabil gelesen wird.
2. Modus auf `TEST` setzen.
3. Nur sehr kurzen Heiztest ausloesen, z. B. `2.0 s`.
4. Temperaturanstieg beobachten.
5. Danach auf `AUTO` wechseln und mit niedrigem Sollwert starten, z. B. `180 C`.
6. Overtemperature-Grenze zunaechst nicht erhoehen.
7. Bei ungewoehnlichem Verhalten sofort `Alles AUS` oder Fault-Stop nutzen.

## Hinweise fuer den ersten echten Versuch

- Luefter-Bootstart ist absichtlich nicht automatisch aktiv.
- Heiztest ist nur im `TEST`-Modus erlaubt und zeitlich begrenzt.
- Ruecksetzen aus `FAULT` nur per expliziter Quittierung.
- TODO: Vor Produktbetrieb reale PID-Werte und Safety-Grenzen durch Messung validieren.
