$Port = "COM5"

python -m mpremote connect $Port mkdir :kolbenspritzgussmaschine
python -m mpremote connect $Port mkdir :kolbenspritzgussmaschine/communication
python -m mpremote connect $Port mkdir :kolbenspritzgussmaschine/pico

python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/__init__.py :kolbenspritzgussmaschine/__init__.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/config.py :kolbenspritzgussmaschine/config.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/models.py :kolbenspritzgussmaschine/models.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/safety_manager.py :kolbenspritzgussmaschine/safety_manager.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/communication/__init__.py :kolbenspritzgussmaschine/communication/__init__.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/communication/protocol.py :kolbenspritzgussmaschine/communication/protocol.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/__init__.py :kolbenspritzgussmaschine/pico/__init__.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/max31865_sensor.py :kolbenspritzgussmaschine/pico/max31865_sensor.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/heater_output.py :kolbenspritzgussmaschine/pico/heater_output.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/fan_output.py :kolbenspritzgussmaschine/pico/fan_output.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/valve_output.py :kolbenspritzgussmaschine/pico/valve_output.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/pid_loop.py :kolbenspritzgussmaschine/pico/pid_loop.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/safety_manager.py :kolbenspritzgussmaschine/pico/safety_manager.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/runtime.py :kolbenspritzgussmaschine/pico/runtime.py
python -m mpremote connect $Port cp src/kolbenspritzgussmaschine/pico/main.py :main.py

python -m mpremote connect $Port reset
