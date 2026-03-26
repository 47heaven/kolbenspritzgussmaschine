import json


def encode_message(message):
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line):
    text = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
    return json.loads(text.strip())


def ping_command():
    return {"type": "ping"}


def status_command():
    return {"type": "get_status"}


def set_mode_command(mode):
    return {"type": "set_mode", "mode": mode}


def acknowledge_fault_command():
    return {"type": "ack_fault"}


def all_outputs_off_command():
    return {"type": "all_outputs_off"}


def set_setpoint_command(value_c):
    return {"type": "set_setpoint", "value_c": value_c}


def set_overtemperature_limit_command(value_c):
    return {"type": "set_overtemperature_limit", "value_c": value_c}


def set_heating_command(enabled):
    return {"type": "set_heating", "enabled": enabled}


def set_fan_command(enabled):
    return {"type": "set_fan", "enabled": enabled}


def set_valve_command(enabled):
    return {"type": "set_valve", "enabled": enabled}


def heater_test_command(duration_s):
    return {"type": "heater_test", "duration_s": duration_s}


def set_pid_command(kp, ki, kd, setpoint_c):
    return {"type": "set_pid", "kp": kp, "ki": ki, "kd": kd, "setpoint_c": setpoint_c}
