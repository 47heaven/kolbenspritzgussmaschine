from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from kolbenspritzgussmaschine.communication.client import PicoControllerClient, SerialLineTransport
from kolbenspritzgussmaschine.communication.protocol import decode_message
from kolbenspritzgussmaschine.config import OperatingMode

try:
    import serial.tools.list_ports  # type: ignore[import-not-found]
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pyserial is required. Install with: pip install pyserial") from exc


def list_ports() -> list[str]:
    return [port.device for port in serial.tools.list_ports.comports()]


def auto_port() -> str | None:
    ports = list_ports()
    if not ports:
        return None
    preferred = [p for p in ports if 'ACM' in p or 'USB' in p or 'COM' in p]
    return preferred[0] if preferred else ports[0]


def print_help() -> None:
    print('Commands:')
    print('  help')
    print('  ports')
    print('  reconnect [PORT]')
    print('  ping')
    print('  status')
    print('  mode off|test|auto')
    print('  all_off')
    print('  fault_ack')
    print('  fan on|off')
    print('  valve on|off')
    print('  heater_test [seconds]')
    print('  setpoint VALUE_C')
    print('  overtemp VALUE_C')
    print('  raw JSON')
    print('  quit')


def format_status(response: dict) -> str:
    return (
        f"mode={response.get('mode')} temp={response.get('temperature_c')}C "
        f"sp={response.get('setpoint_c')}C heater={response.get('heater_output_percent')}% "
        f"heater_on={response.get('heater_on')} fan={response.get('fan_enabled')} "
        f"valve={response.get('valve_enabled')} sensor_ok={response.get('sensor_ok')} "
        f"fault={response.get('fault_code')} msg={response.get('fault_message')}"
    )


def connect(port: str) -> tuple[PicoControllerClient, SerialLineTransport]:
    transport = SerialLineTransport(port=port, baudrate=115200, timeout_s=1.0)
    client = PicoControllerClient(transport)
    return client, transport


def main() -> None:
    port = auto_port()
    if port is None:
        print('No serial ports found. Connect the Pico first or use reconnect PORT later.')
        client = None
        transport = None
    else:
        try:
            client, transport = connect(port)
            print(f'Connected to {port}')
        except Exception as exc:
            print(f'Connection failed on {port}: {exc}')
            client = None
            transport = None

    print_help()

    while True:
        try:
            line = input('serial-console> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            line = 'quit'

        if not line:
            continue
        if line == 'quit':
            break
        if line == 'help':
            print_help()
            continue
        if line == 'ports':
            ports = list_ports()
            print('\n'.join(ports) if ports else 'No ports found.')
            continue
        if line.startswith('reconnect'):
            parts = line.split(maxsplit=1)
            selected = parts[1] if len(parts) > 1 else auto_port()
            if not selected:
                print('No port specified and no port auto-detected.')
                continue
            try:
                if transport is not None:
                    transport.close()
                client, transport = connect(selected)
                port = selected
                print(f'Connected to {port}')
            except Exception as exc:
                client = None
                transport = None
                print(f'Connection failed on {selected}: {exc}')
            continue

        if client is None:
            print('Not connected. Use reconnect PORT.')
            continue

        try:
            if line == 'ping':
                response = client.ping()
            elif line == 'status':
                status = client.fetch_status()
                print(status)
                continue
            elif line.startswith('mode '):
                mode = line.split()[1].lower()
                response = client.set_mode(OperatingMode(mode))
            elif line == 'all_off':
                response = client.all_outputs_off()
            elif line == 'fault_ack':
                response = client.acknowledge_fault()
            elif line.startswith('fan '):
                response = client.set_fan_enabled(line.split()[1].lower() == 'on')
            elif line.startswith('valve '):
                response = client.set_valve_enabled(line.split()[1].lower() == 'on')
            elif line.startswith('heater_test'):
                parts = line.split()
                duration = float(parts[1]) if len(parts) > 1 else 2.0
                response = client.trigger_heater_test(duration)
            elif line.startswith('setpoint '):
                response = client.set_setpoint(float(line.split()[1]))
            elif line.startswith('overtemp '):
                response = client.set_overtemperature_limit(float(line.split()[1]))
            elif line.startswith('raw '):
                payload = decode_message((line[4:].strip() + '\n').encode('utf-8'))
                response = client._roundtrip(payload)
            else:
                print('Unknown command. Type help.')
                continue
            print(response)
            if isinstance(response, dict) and 'mode' in response:
                print(format_status(response))
        except Exception as exc:
            print(f'Command failed: {exc}')

    if transport is not None:
        transport.close()


if __name__ == '__main__':
    main()
