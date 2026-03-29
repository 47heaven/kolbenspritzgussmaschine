
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from kolbenspritzgussmaschine.config import MachineConfig, OperatingMode, RuntimeMode, SensorElement, TemperatureSensorConfig
from kolbenspritzgussmaschine.models import MachineStatus
from kolbenspritzgussmaschine.services.controller_service import ControllerService, PicoGateway, SimulationGateway
from kolbenspritzgussmaschine.communication.client import PicoControllerClient, SerialLineTransport

try:
    import serial.tools.list_ports  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    serial = None  # type: ignore[assignment]


def scaled_size(size: int) -> int:
    return max(1, round(size * 1.3106))


@dataclass(slots=True)
class Profile:
    name: str
    setpoint: float
    kp: float
    ki: float
    kd: float


@dataclass(frozen=True, slots=True)
class UiTheme:
    bg: str = "#07111f"
    panel: str = "#0b1526"
    panel_alt: str = "#0d1a2f"
    border: str = "#18263a"
    grid: str = "#14243a"
    text: str = "#d8e2f0"
    muted: str = "#6d7c90"
    orange: str = "#ff7a1a"
    amber: str = "#ffc247"
    green: str = "#32d98b"
    red: str = "#ff5b57"


@dataclass(slots=True)
class ChartState:
    times: deque[float]
    values: deque[float]
    setpoints: deque[float]
    outputs: deque[float]
    sample_time: float
    max_points: int | None


class TouchToggle(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        theme: UiTheme,
        title: str,
        subtitle: str,
        initial_percent: int,
        *,
        command=None,
    ) -> None:
        super().__init__(master, bg=theme.panel_alt, highlightthickness=1, highlightbackground=theme.border)
        self.enabled = tk.BooleanVar(value=False)
        self._command = command
        self._theme = theme
        self._on_text = "EIN" if "VENTIL" in title.upper() else "AN"
        self._off_text = "AUS"

        top = tk.Frame(self, bg=theme.panel_alt)
        top.pack(fill="x", padx=16, pady=(12, 10))
        text_col = tk.Frame(top, bg=theme.panel_alt)
        text_col.pack(side="left", fill="both", expand=True)
        title_label = tk.Label(text_col, text=title, bg=theme.panel_alt, fg=theme.text, font=("Consolas", scaled_size(13), "bold"))
        title_label.pack(anchor="w")
        self.status_label = tk.Label(text_col, text="AUS", bg=theme.panel_alt, fg=theme.muted, font=("Consolas", scaled_size(10)))
        self.status_label.pack(anchor="w", pady=(2, 0))

        self.switch_canvas = tk.Canvas(
            top,
            width=88,
            height=46,
            bg=theme.panel_alt,
            highlightthickness=0,
            cursor="hand2",
        )
        self.switch_canvas.pack(side="right")
        self.switch_canvas.bind("<Button-1>", self._toggle)
        self.bind("<Button-1>", self._toggle)
        top.bind("<Button-1>", self._toggle)
        text_col.bind("<Button-1>", self._toggle)
        title_label.bind("<Button-1>", self._toggle)
        self.status_label.bind("<Button-1>", self._toggle)
        self._draw_switch()

    def _draw_switch(self) -> None:
        self.switch_canvas.delete("all")
        enabled = self.enabled.get()
        track_fill = self._theme.green if enabled else "#203244"
        track_outline = "#3a5872" if enabled else "#2a3d4f"
        knob_left = 42 if enabled else 8
        self._rounded_rect(6, 8, 82, 38, radius=15, fill=track_fill, outline=track_outline, width=2)
        self.switch_canvas.create_oval(knob_left + 1, 9, knob_left + 29, 37, fill="#d7e0ea", outline="")
        self.switch_canvas.create_oval(knob_left, 8, knob_left + 28, 36, fill="#f9fcff", outline="#dbe5ee", width=1)
        self.status_label.config(
            text=self._on_text if enabled else self._off_text,
            fg=self._theme.green if enabled else self._theme.muted,
        )

    def _rounded_rect(self, x0: int, y0: int, x1: int, y1: int, radius: int, **kwargs) -> None:
        self.switch_canvas.create_arc(x0, y0, x0 + radius * 2, y0 + radius * 2, start=90, extent=90, style="pieslice", **kwargs)
        self.switch_canvas.create_arc(x1 - radius * 2, y0, x1, y0 + radius * 2, start=0, extent=90, style="pieslice", **kwargs)
        self.switch_canvas.create_arc(x0, y1 - radius * 2, x0 + radius * 2, y1, start=180, extent=90, style="pieslice", **kwargs)
        self.switch_canvas.create_arc(x1 - radius * 2, y1 - radius * 2, x1, y1, start=270, extent=90, style="pieslice", **kwargs)
        self.switch_canvas.create_rectangle(x0 + radius, y0, x1 - radius, y1, **kwargs)
        self.switch_canvas.create_rectangle(x0, y0 + radius, x1, y1 - radius, **kwargs)

    def set_state(self, enabled: bool, value: int) -> None:
        self.enabled.set(enabled)
        self._draw_switch()

    def _emit(self) -> None:
        if self._command is not None:
            self._command(self.enabled.get())

    def _toggle(self, _event=None) -> None:
        self.enabled.set(not self.enabled.get())
        self._draw_switch()
        self._emit()


class HeaterPowerGauge(tk.Frame):
    def __init__(self, master: tk.Misc, theme: UiTheme) -> None:
        super().__init__(master, bg=theme.panel_alt, highlightthickness=1, highlightbackground=theme.border)
        self._theme = theme
        self._percent = 0.0

        tk.Label(self, text="HEIZLEISTUNG", bg=theme.panel_alt, fg=theme.muted, font=("Consolas", scaled_size(13))).pack(anchor="w", padx=16, pady=(12, 6))

        self.canvas = tk.Canvas(self, height=184, bg=theme.panel_alt, highlightthickness=0)
        self.canvas.pack(fill="x", padx=12, pady=(0, 12))
        self.canvas.bind("<Configure>", self._redraw)

    def set_percent(self, percent: float) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self._redraw()

    def _redraw(self, _event=None) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 300)
        height = max(self.canvas.winfo_height(), 184)
        center_x = width / 2
        center_y = height - 18
        radius = min(width * 0.31, height - 44)

        start_angle = math.pi
        end_angle = 0.0
        for tick in range(11):
            ratio = tick / 10
            angle = start_angle + (end_angle - start_angle) * ratio
            outer_x = center_x + math.cos(angle) * radius
            outer_y = center_y - math.sin(angle) * radius
            inner_radius = radius - (24 if tick in (0, 5, 10) else 16)
            inner_x = center_x + math.cos(angle) * inner_radius
            inner_y = center_y - math.sin(angle) * inner_radius
            self.canvas.create_line(inner_x, inner_y, outer_x, outer_y, fill=self._theme.text, width=4 if tick in (0, 5, 10) else 3)
            label_radius = radius + 20
            label_x = center_x + math.cos(angle) * label_radius
            label_y = center_y - math.sin(angle) * label_radius
            self.canvas.create_text(label_x, label_y, text=f"{tick * 10}", fill=self._theme.muted, font=("Consolas", scaled_size(10), "bold"))

        self.canvas.create_arc(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            start=180,
            extent=-180,
            style="arc",
            outline=self._theme.grid,
            width=18,
        )
        self.canvas.create_arc(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            start=180,
            extent=-(180 * (self._percent / 100.0)),
            style="arc",
            outline=self._theme.orange,
            width=18,
        )

        angle = start_angle + (end_angle - start_angle) * (self._percent / 100.0)
        marker_outer_radius = radius + 6
        marker_inner_radius = radius - 18
        marker_outer_x = center_x + math.cos(angle) * marker_outer_radius
        marker_outer_y = center_y - math.sin(angle) * marker_outer_radius
        marker_inner_x = center_x + math.cos(angle) * marker_inner_radius
        marker_inner_y = center_y - math.sin(angle) * marker_inner_radius
        self.canvas.create_line(marker_inner_x, marker_inner_y, marker_outer_x, marker_outer_y, fill="#f7fbff", width=7)
        self.canvas.create_text(center_x, center_y - radius * 0.34, text=f"{round(self._percent):.0f} %", fill=self._theme.orange, font=("Consolas", scaled_size(24), "bold"))


class StatusIndicator(tk.Frame):
    def __init__(self, master: tk.Misc, theme: UiTheme, label: str) -> None:
        super().__init__(master, bg=theme.panel_alt, highlightthickness=1, highlightbackground=theme.border)
        self.dot = tk.Canvas(self, width=18, height=18, bg=theme.panel_alt, highlightthickness=0)
        self.dot.grid(row=0, column=0, padx=(12, 8), pady=10)
        self.dot_id = self.dot.create_oval(4, 4, 14, 14, fill=theme.green, outline="")

        tk.Label(self, text=label, bg=theme.panel_alt, fg=theme.text, font=("Consolas", scaled_size(12))).grid(row=0, column=1, sticky="w")
        self.value_widget = tk.Label(self, text="OK", bg=theme.panel_alt, fg=theme.text, font=("Consolas", scaled_size(12), "bold"))
        self.value_widget.grid(row=0, column=2, padx=(8, 12), sticky="e")
        self.grid_columnconfigure(1, weight=1)

    def update_state(self, text: str, color: str) -> None:
        self.value_widget.config(text=text)
        self.dot.itemconfig(self.dot_id, fill=color)


class ServiceWindow:
    def __init__(self, root: tk.Tk, theme: UiTheme, service: ControllerService) -> None:
        self.root = root
        self.theme = theme
        self.service = service
        self.window: tk.Toplevel | None = None
        self.mode_var = tk.StringVar(value='-')
        self.temp_var = tk.StringVar(value='--.- C')
        self.sensor_var = tk.StringVar(value='sensor_ok=nein')
        self.fault_var = tk.StringVar(value='keine')
        self.outputs_var = tk.StringVar(value='heater=aus fan=aus valve=aus')
        self.overtemp_var = tk.StringVar(value='250.0')
        self.test_duration_var = tk.StringVar(value='2.0')

    def open(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            return

        self.window = tk.Toplevel(self.root)
        self.window.title('Service / Test')
        self.window.geometry('620x520')
        self.window.configure(bg=self.theme.bg)

        panel = tk.Frame(self.window, bg=self.theme.panel, highlightthickness=1, highlightbackground=self.theme.border)
        panel.pack(fill='both', expand=True, padx=16, pady=16)

        tk.Label(panel, text='SERVICE / TEST', bg=self.theme.panel, fg=self.theme.orange, font=('Consolas', 18, 'bold')).pack(anchor='w', padx=16, pady=(16, 10))
        tk.Label(panel, text='Reale Hardwarefunktionen laufen nur ?ber ControllerService/USB-Serial.', bg=self.theme.panel, fg=self.theme.muted, font=('Consolas', 11)).pack(anchor='w', padx=16)
        tk.Label(panel, textvariable=self.mode_var, bg=self.theme.panel, fg=self.theme.text, font=('Consolas', 12)).pack(anchor='w', padx=16, pady=(12, 0))
        tk.Label(panel, textvariable=self.temp_var, bg=self.theme.panel, fg=self.theme.text, font=('Consolas', 12)).pack(anchor='w', padx=16, pady=(6, 0))
        tk.Label(panel, textvariable=self.sensor_var, bg=self.theme.panel, fg=self.theme.text, font=('Consolas', 12)).pack(anchor='w', padx=16, pady=(6, 0))
        tk.Label(panel, textvariable=self.outputs_var, bg=self.theme.panel, fg=self.theme.text, font=('Consolas', 12)).pack(anchor='w', padx=16, pady=(6, 0))
        tk.Label(panel, textvariable=self.fault_var, bg=self.theme.panel, fg=self.theme.text, font=('Consolas', 12), wraplength=560, justify='left').pack(anchor='w', padx=16, pady=(6, 12))

        mode_row = tk.Frame(panel, bg=self.theme.panel)
        mode_row.pack(fill='x', padx=16, pady=(0, 8))
        self._btn(mode_row, 'OFF', lambda: self.service.set_mode(OperatingMode.OFF), self.theme.amber, 8).pack(side='left', padx=(0, 8))
        self._btn(mode_row, 'TEST', lambda: self.service.set_mode(OperatingMode.TEST), self.theme.orange, 8).pack(side='left', padx=(0, 8))
        self._btn(mode_row, 'AUTO', lambda: self.service.set_mode(OperatingMode.AUTO), self.theme.green, 8).pack(side='left', padx=(0, 8))
        self._btn(mode_row, 'FAULT QUIT', self.service.acknowledge_fault, self.theme.red, 12).pack(side='left')

        io_row = tk.Frame(panel, bg=self.theme.panel)
        io_row.pack(fill='x', padx=16, pady=(0, 8))
        self._btn(io_row, 'Luefter EIN', lambda: self.service.set_fan_enabled(True), self.theme.green).pack(side='left', padx=(0, 8))
        self._btn(io_row, 'Luefter AUS', lambda: self.service.set_fan_enabled(False), self.theme.amber).pack(side='left', padx=(0, 8))
        self._btn(io_row, 'Ventil EIN', lambda: self.service.set_valve_enabled(True), self.theme.green).pack(side='left', padx=(0, 8))
        self._btn(io_row, 'Ventil AUS', lambda: self.service.set_valve_enabled(False), self.theme.amber).pack(side='left')

        heater_row = tk.Frame(panel, bg=self.theme.panel)
        heater_row.pack(fill='x', padx=16, pady=(0, 8))
        tk.Label(heater_row, text='Heiztest [s]', bg=self.theme.panel, fg=self.theme.text, font=('Consolas', 11)).pack(side='left')
        tk.Entry(heater_row, textvariable=self.test_duration_var, width=8, bg=self.theme.bg, fg=self.theme.text, insertbackground=self.theme.text, relief='flat', font=('Consolas', 11)).pack(side='left', padx=(8, 12))
        self._btn(heater_row, 'Heiztest Start', self._trigger_heater_test, self.theme.red, 14).pack(side='left', padx=(0, 8))
        self._btn(heater_row, 'Alles AUS', self.service.all_outputs_off, self.theme.amber, 12).pack(side='left')

        overtemp_row = tk.Frame(panel, bg=self.theme.panel)
        overtemp_row.pack(fill='x', padx=16, pady=(0, 8))
        tk.Label(overtemp_row, text='Overtemp [C]', bg=self.theme.panel, fg=self.theme.text, font=('Consolas', 11)).pack(side='left')
        tk.Entry(overtemp_row, textvariable=self.overtemp_var, width=8, bg=self.theme.bg, fg=self.theme.text, insertbackground=self.theme.text, relief='flat', font=('Consolas', 11)).pack(side='left', padx=(8, 12))
        self._btn(overtemp_row, 'Grenzwert setzen', self._set_overtemp_limit, self.theme.orange, 16).pack(side='left')

        tk.Label(panel, text='Warnung: Heiztest nur kurz, nur mit Sensor OK und nur im TEST-Modus ausf?hren.', bg=self.theme.panel, fg=self.theme.amber, font=('Consolas', 11), wraplength=560, justify='left').pack(anchor='w', padx=16, pady=(6, 0))
        self._btn(panel, 'Schliessen', self.window.destroy, self.theme.orange, 18).pack(side='bottom', fill='x', padx=16, pady=16)
        self._refresh()

    def _btn(self, master: tk.Misc, text: str, command, color: str, width: int = 12) -> tk.Button:
        return tk.Button(master, text=text, command=command, bg=self.theme.panel_alt, fg=color, activebackground=color, activeforeground=self.theme.bg, relief='flat', bd=0, font=('Consolas', 11, 'bold'), width=width, padx=8, pady=8)

    def _trigger_heater_test(self) -> None:
        self.service.trigger_heater_test(float(self.test_duration_var.get()))

    def _set_overtemp_limit(self) -> None:
        self.service.set_overtemperature_limit(float(self.overtemp_var.get()))

    def _refresh(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            return
        status = self.service.latest_status()
        self.mode_var.set(f'Modus: {status.mode.value} | Runtime: {self.service.mode.value} | test_rest={status.test_seconds_remaining:.1f}s')
        self.temp_var.set(f"Temperatur: {'--.-' if status.temperature_c is None else f'{status.temperature_c:.1f}'} C | Soll: {status.setpoint_c:.1f} C | Overtemp: {status.overtemperature_limit_c:.1f} C")
        self.sensor_var.set(f'sensor_ok={status.sensor_ok} communication_ok={status.communication_ok} fan_auto={status.fan_auto_active}')
        self.outputs_var.set(f'heater_on={status.heater_on} heater_out={status.heater_output_percent:.1f}% fan={status.fan_enabled} valve={status.valve_enabled}')
        self.fault_var.set(f'Fehler: {status.fault_message or status.fault_code.value}')
        self.overtemp_var.set(f'{status.overtemperature_limit_c:.1f}')
        self.window.after(300, self._refresh)

def list_serial_ports() -> list[str]:
    if serial is None:
        return []
    return [port.device for port in serial.tools.list_ports.comports()]


def auto_serial_port() -> str | None:
    ports = list_serial_ports()
    if not ports:
        return None
    preferred = [port for port in ports if "ACM" in port or "USB" in port or "COM" in port]
    return preferred[0] if preferred else ports[0]


def build_service(mode: RuntimeMode = RuntimeMode.SERIAL, serial_port: str | None = None) -> ControllerService:
    sensor = TemperatureSensorConfig.for_element(SensorElement(os.getenv("KOLBEN_SENSOR", "pt100")))
    config = MachineConfig(mode=mode, sensor=sensor)
    config.pid.setpoint = float(os.getenv("KOLBEN_SETPOINT", "230.0"))
    if mode == RuntimeMode.SERIAL:
        port = serial_port or os.getenv("KOLBEN_SERIAL_PORT", auto_serial_port() or "")
        if not port:
            raise RuntimeError("Kein serieller Port gefunden. Bitte Pico anschliessen.")
        baudrate = int(os.getenv("KOLBEN_SERIAL_BAUDRATE", str(config.serial.baudrate)))
        transport = SerialLineTransport(port=port, baudrate=baudrate, timeout_s=config.serial.timeout_s)
        client = PicoControllerClient(transport)
        try:
            client.ping()
        except Exception:
            transport.close()
            raise
        gateway = PicoGateway(client)
    else:
        gateway = SimulationGateway(config)
    return ControllerService(gateway, poll_interval_s=config.status_interval_s)


class App:
    WINDOW_SIZE = "1360x820"
    DISPLAY_MAX_POWER_WATTS = 800.0
    POWER_AVERAGE_WINDOW_SECONDS = 5.0
    LIVE_HISTORY_POINTS = None
    PREVIEW_HISTORY_POINTS = 220
    PROFILE_COLUMNS = 3

    def __init__(self) -> None:
        self.theme = UiTheme()
        self.root = self._build_root()
        self.serial_port = os.getenv("KOLBEN_SERIAL_PORT", auto_serial_port() or "")
        self.connection_notice: str | None = None
        try:
            self.service = build_service(RuntimeMode.SERIAL, self.serial_port)
        except Exception as exc:
            self.connection_notice = f"COM-Port nicht erreichbar. GUI wurde im Simulationsmodus geoeffnet.\n\n{exc}"
            self.service = build_service(RuntimeMode.SIMULATION)
        self.service_window = ServiceWindow(self.root, self.theme, self.service)

        self.sample_time = 0.2
        self.preview_sample_time = 0.2
        self.running = True
        self.elapsed = 0.0
        self.preview_elapsed = 0.0
        self._last_status_timestamp = -1.0
        self.preview_gateway: SimulationGateway | None = None

        self.live_chart = self._create_chart_state(self.sample_time, self.LIVE_HISTORY_POINTS)
        self.preview_chart = self._create_chart_state(self.preview_sample_time, self.PREVIEW_HISTORY_POINTS)
        self.power_history: deque[tuple[float, float]] = deque()

        self.profiles = self._build_default_profiles()
        self.active_profile = self.profiles[0].name

        self._init_variables()
        self._init_widget_refs()
        self._build_ui()
        self._rebuild_profile_buttons()
        self._rebuild_profile_list()
        self._apply_profile(self.profiles[0], update_form=True, push_live=False)
        self._reset_preview()
        self._refresh_connection_ui()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.service.start()
        if self.connection_notice:
            self.status.set("Simulation aktiv - COM-Port nicht erreichbar")
            self.root.after(150, lambda: messagebox.showwarning("Simulationsmodus aktiv", self.connection_notice, parent=self.root))
        self._tick_clock()
        self._schedule()

    def _build_root(self) -> tk.Tk:
        root = tk.Tk()
        root.title("Tiegel-Steuerung")
        root.geometry(self.WINDOW_SIZE)
        root.configure(bg=self.theme.bg)
        return root

    def _create_chart_state(self, sample_time: float, max_points: int | None) -> ChartState:
        return ChartState(
            times=deque(maxlen=max_points),
            values=deque(maxlen=max_points),
            setpoints=deque(maxlen=max_points),
            outputs=deque(maxlen=max_points),
            sample_time=sample_time,
            max_points=max_points,
        )

    def _build_default_profiles(self) -> list[Profile]:
        return [
            Profile("PLA 200", 200.0, 8.0, 0.7, 1.2),
            Profile("PETG 230", 230.0, 8.5, 0.8, 1.1),
            Profile("ABS 240", 240.0, 9.0, 0.9, 1.0),
        ]

    def _init_variables(self) -> None:
        self.clock = tk.StringVar(value="--:--:--")
        self.status = tk.StringVar(value="Heizbetrieb aktiv (Service-Architektur)")
        self.actual = tk.StringVar(value="22")
        self.setpoint = tk.StringVar(value="200")
        self.temperature_pair = tk.StringVar(value="22 C / 200 C")
        self.output = tk.StringVar(value="0 %")
        self.progress = tk.StringVar(value="0 %")
        self.avg_power = tk.StringVar(value="0 W")
        self.profile_label = tk.StringVar(value=self.active_profile)
        self.connection_state = tk.StringVar(value="Live verbunden" if self.service.mode == RuntimeMode.SERIAL else "Simulation aktiv")
        self.connection_port_var = tk.StringVar(value=self.serial_port)

        self.pid_kp = tk.DoubleVar(value=self.profiles[0].kp)
        self.pid_ki = tk.DoubleVar(value=self.profiles[0].ki)
        self.pid_kd = tk.DoubleVar(value=self.profiles[0].kd)
        self.pid_sp = tk.DoubleVar(value=self.profiles[0].setpoint)

        self.form_name = tk.StringVar(value="NEUES MATERIAL")
        self.form_sp = tk.DoubleVar(value=210.0)
        self.form_kp = tk.DoubleVar(value=8.0)
        self.form_ki = tk.DoubleVar(value=0.7)
        self.form_kd = tk.DoubleVar(value=1.2)

    def _init_widget_refs(self) -> None:
        self.nav_buttons: dict[str, tk.Button] = {}
        self.profile_buttons: dict[str, tk.Button] = {}
        self.avg_power_bar: tk.Frame
        self.temp_canvas: tk.Canvas
        self.preview_canvas: tk.Canvas
        self.profile_row: tk.Frame
        self.profile_list: tk.Frame
        self.connection_port_box: ttk.Combobox
        self.sensor_status: StatusIndicator
        self.pid_status: StatusIndicator
        self.heat_status: StatusIndicator
        self.fan_toggle: TouchToggle
        self.valve_toggle: TouchToggle
        self.power_gauge: HeaterPowerGauge
        self.dashboard_layout: tk.Frame
        self.dashboard_left_card: tk.Frame
        self.dashboard_right_card: tk.Frame

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=self.theme.bg)
        outer.pack(fill="both", expand=True, padx=16, pady=16)
        self._build_header(outer)
        self._build_navigation(outer)
        self._build_pages(outer)

    def _build_header(self, master: tk.Misc) -> None:
        header = self.card(master)
        header.pack(fill="x")
        tk.Label(header, text="<> TIEGEL-STEUERUNG V1.0", bg=self.theme.panel, fg=self.theme.orange, font=("Consolas", scaled_size(18), "bold")).pack(side="left", padx=16, pady=12)
        tk.Label(header, textvariable=self.status, bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(11))).pack(side="left", padx=12)
        self.btn(header, "HEIZEN START", self.start_heating, self.theme.green).pack(side="left", padx=(20, 8))
        self.btn(header, "HEIZEN STOPP", self.stop_heating, self.theme.amber).pack(side="left")
        self.btn(header, "SERVICE", self.service_window.open, self.theme.orange, 10).pack(side="right", padx=(0, 16))
        tk.Label(header, textvariable=self.clock, bg=self.theme.panel, fg=self.theme.text, font=("Consolas", scaled_size(16))).pack(side="right", padx=16)

    def _build_navigation(self, master: tk.Misc) -> None:
        nav = tk.Frame(master, bg=self.theme.bg)
        nav.pack(fill="x", pady=(12, 0))
        nav_left = tk.Frame(nav, bg=self.theme.bg)
        nav_left.pack(side="left")
        nav_right = tk.Frame(nav, bg=self.theme.bg)
        nav_right.pack(side="right")

        entries = [("dashboard", "DASHBOARD"), ("pid", "PID-LABOR"), ("profiles", "MATERIALPROFILE")]
        for key, label in entries:
            button = tk.Button(master=nav_left, text=label, command=lambda current=key: self.show_page(current), bg=self.theme.panel_alt, fg=self.theme.text, activebackground=self.theme.orange, activeforeground=self.theme.bg, relief="flat", bd=0, font=("Consolas", scaled_size(13), "bold"), padx=18, pady=12)
            button.pack(side="left", padx=(0, 10))
            self.nav_buttons[key] = button
        self._build_connection_controls(nav_right, compact=True)

    def _build_pages(self, master: tk.Misc) -> None:
        pages = tk.Frame(master, bg=self.theme.bg)
        pages.pack(fill="both", expand=True, pady=(12, 0))
        pages.grid_rowconfigure(0, weight=1)
        pages.grid_columnconfigure(0, weight=1)
        self.page_frames = {
            "dashboard": self._build_dashboard(pages),
            "pid": self._build_pid_page(pages),
            "profiles": self._build_profiles_page(pages),
        }
        for frame in self.page_frames.values():
            frame.grid(row=0, column=0, sticky="nsew")
        self.show_page("dashboard")

    def _build_dashboard(self, master: tk.Misc) -> tk.Frame:
        page = tk.Frame(master, bg=self.theme.bg)
        self.dashboard_layout = tk.Frame(page, bg=self.theme.bg)
        self.dashboard_layout.pack(fill="both", expand=True)

        self.dashboard_left_card = self.card(self.dashboard_layout)
        self.dashboard_right_card = self.card(self.dashboard_layout)
        self.dashboard_layout.bind("<Configure>", self._layout_dashboard_cards)

        self._build_dashboard_left(self.dashboard_left_card)
        self._build_dashboard_center(self.dashboard_right_card)
        return page

    def _layout_dashboard_cards(self, event) -> None:
        width = max(1, event.width)
        height = max(1, event.height)
        gap = 16
        left_width = int((width - gap) * 0.3333)
        right_width = max(1, width - left_width - gap)
        self.dashboard_left_card.place(x=0, y=0, width=left_width, height=height)
        self.dashboard_right_card.place(x=left_width + gap, y=0, width=right_width, height=height)

    def _build_dashboard_left(self, master: tk.Misc) -> None:
        tk.Label(master, text="TEMPERATUR", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(14))).pack(anchor="w", padx=16, pady=(14, 6))
        tk.Label(master, textvariable=self.temperature_pair, bg=self.theme.panel, fg=self.theme.orange, font=("Consolas", scaled_size(30), "bold")).pack(anchor="w", padx=16)
        tk.Label(master, text="IST / SOLL", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(12))).pack(anchor="w", padx=18, pady=(2, 12))

        self.power_gauge = HeaterPowerGauge(master, self.theme)
        self.power_gauge.pack(fill="x", padx=16, pady=(0, 12))

        metrics = tk.Frame(master, bg=self.theme.panel)
        metrics.pack(fill="x", padx=16, pady=(0, 12))
        self.avg_power_bar = self._metric(metrics, "Leistung [5 Sekunden Schnitt]", self.avg_power)
        self.avg_power_bar.pack(fill="x")

        tk.Label(master, text="PERIPHERIE", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(14))).pack(anchor="w", padx=16, pady=(2, 8))
        toggle_row = tk.Frame(master, bg=self.theme.panel)
        toggle_row.pack(fill="x", padx=16, pady=(0, 14))
        toggle_row.grid_columnconfigure(0, weight=1)
        toggle_row.grid_columnconfigure(1, weight=1)
        self.fan_toggle = TouchToggle(toggle_row, self.theme, "LUEFTER", "Status", 0, command=self._set_fan_enabled)
        self.fan_toggle.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.valve_toggle = TouchToggle(toggle_row, self.theme, "VENTIL", "Status", 0, command=self._set_valve_enabled)
        self.valve_toggle.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        tk.Label(master, text="SYSTEM", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(14))).pack(anchor="w", padx=16, pady=(0, 8))
        self.sensor_status = StatusIndicator(master, self.theme, "Sensor")
        self.sensor_status.pack(fill="x", padx=16, pady=(0, 8))
        self.pid_status = StatusIndicator(master, self.theme, "PID")
        self.pid_status.pack(fill="x", padx=16, pady=(0, 8))
        self.heat_status = StatusIndicator(master, self.theme, "Aufheizen")
        self.heat_status.pack(fill="x", padx=16, pady=(0, 12))

        controls = tk.Frame(master, bg=self.theme.bg, highlightthickness=1, highlightbackground=self.theme.border)
        controls.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(controls, text="HEIZBETRIEB", bg=self.theme.bg, fg=self.theme.muted, font=("Consolas", scaled_size(13))).pack(anchor="w", padx=12, pady=(12, 8))
        row = tk.Frame(controls, bg=self.theme.bg)
        row.pack(fill="x", padx=12, pady=(0, 14))
        self.btn(row, "START", self.start_heating, self.theme.green, 12).pack(side="left", padx=(0, 8))
        self.btn(row, "STOPP", self.stop_heating, self.theme.amber, 12).pack(side="left", padx=(0, 8))
        self.btn(row, "NOTSTOPP", self.emergency_stop, self.theme.red, 12).pack(side="left")

        footer = tk.Frame(master, bg=self.theme.panel)
        footer.pack(fill="x", padx=16, pady=(0, 16))
        tk.Label(footer, text="AKTIVES PROFIL", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(12))).pack(side="left")
        tk.Label(footer, textvariable=self.profile_label, bg=self.theme.panel, fg=self.theme.orange, font=("Consolas", scaled_size(14), "bold")).pack(side="right")

    def _build_connection_controls(self, master: tk.Misc, *, compact: bool) -> None:
        bg = self.theme.panel_alt if compact else self.theme.bg
        container = tk.Frame(master, bg=bg, highlightthickness=1, highlightbackground=self.theme.border)
        container.pack(side="right" if compact else "top", fill="x" if not compact else "none", padx=(24, 0) if compact else 0, pady=0)
        tk.Label(container, text="LIVE-VERBINDUNG", bg=bg, fg=self.theme.muted, font=("Consolas", scaled_size(10))).pack(anchor="w", padx=12, pady=(8, 2))
        tk.Label(container, textvariable=self.connection_state, bg=bg, fg=self.theme.text, font=("Consolas", scaled_size(9))).pack(anchor="w", padx=12, pady=(0, 6))
        row = tk.Frame(container, bg=bg)
        row.pack(fill="x", padx=12, pady=(0, 8))
        self.connection_port_box = ttk.Combobox(row, textvariable=self.connection_port_var, values=list_serial_ports(), state="readonly", width=10 if compact else 12)
        self.connection_port_box.pack(side="left")
        tk.Button(row, text="PORTS", command=self._reload_serial_ports, bg=self.theme.panel, fg=self.theme.text, activebackground=self.theme.orange, activeforeground=self.theme.bg, relief="flat", bd=0, font=("Consolas", scaled_size(9), "bold"), padx=8, pady=5).pack(side="left", padx=(8, 6))
        tk.Button(row, text="VERBINDEN", command=self._connect_selected_port, bg=self.theme.panel, fg=self.theme.green, activebackground=self.theme.green, activeforeground=self.theme.bg, relief="flat", bd=0, font=("Consolas", scaled_size(9), "bold"), padx=8, pady=5).pack(side="left")

    def _build_dashboard_center(self, master: tk.Misc) -> None:
        tk.Label(master, text="TEMPERATURVERLAUF", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(14))).pack(anchor="w", padx=12, pady=(12, 8))

        content = tk.Frame(master, bg=self.theme.panel)
        content.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        content.grid_rowconfigure(0, weight=11)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.temp_canvas = tk.Canvas(content, bg=self.theme.panel, highlightthickness=0)
        self.temp_canvas.grid(row=0, column=0, sticky="nsew")

        profile_area = tk.Frame(content, bg=self.theme.panel, highlightthickness=1, highlightbackground=self.theme.border)
        profile_area.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        tk.Label(profile_area, text="MATERIALPROFILE", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(12))).pack(anchor="w", padx=12, pady=(6, 2))
        self.profile_row = tk.Frame(profile_area, bg=self.theme.panel)
        self.profile_row.pack(fill="both", expand=True, padx=6, pady=(0, 4))

    def _build_pid_page(self, master: tk.Misc) -> tk.Frame:
        page = tk.Frame(master, bg=self.theme.bg)
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=5)

        left = self.card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = self.card(page)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(left, text="PID-LABOR", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(14))).pack(anchor="w", padx=12, pady=(12, 8))
        tk.Label(left, text="PID-Werte aendern und parallel die Vorschau-Simulation beobachten.", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(11)), wraplength=420, justify="left").pack(anchor="w", padx=12, pady=(0, 12))
        self._slider(left, "Kp", self.pid_kp, 0.0, 20.0, 0.1, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Ki", self.pid_ki, 0.0, 5.0, 0.05, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Kd", self.pid_kd, 0.0, 5.0, 0.05, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Sollwert", self.pid_sp, 40.0, 300.0, 1.0, self._preview_changed).pack(fill="x", padx=12, pady=8)

        row = tk.Frame(left, bg=self.theme.panel)
        row.pack(fill="x", padx=12, pady=(18, 8))
        self.btn(row, "VORSCHAU RESET", self._reset_preview, self.theme.amber).pack(side="left", padx=(0, 8))
        self.btn(row, "AUF LIVE UEBERNEHMEN", self._apply_preview_to_live, self.theme.orange, 18).pack(side="left")
        tk.Label(left, text="Die Vorschau zeigt den gesamten Temperaturverlauf mit Soll- und Istwert.", bg=self.theme.panel, fg=self.theme.text, font=("Consolas", scaled_size(11)), wraplength=420, justify="left").pack(anchor="w", padx=12, pady=(8, 0))

        tk.Label(right, text="SIMULATIONSVORSCHAU", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(14))).pack(anchor="w", padx=12, pady=(12, 8))
        self.preview_canvas = tk.Canvas(right, bg=self.theme.panel, highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        return page

    def _build_profiles_page(self, master: tk.Misc) -> tk.Frame:
        page = tk.Frame(master, bg=self.theme.bg)
        page.grid_columnconfigure(0, weight=4)
        page.grid_columnconfigure(1, weight=3)

        left = self.card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = self.card(page)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(left, text="GESPEICHERTE PROFILE", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(14))).pack(anchor="w", padx=12, pady=(12, 8))
        self.profile_list = tk.Frame(left, bg=self.theme.panel)
        self.profile_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        tk.Label(right, text="PROFIL BEARBEITEN", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(14))).pack(anchor="w", padx=12, pady=(12, 8))
        self._entry(right, "Name", self.form_name).pack(fill="x", padx=12, pady=8)
        self._slider(right, "Sollwert", self.form_sp, 40.0, 300.0, 1.0).pack(fill="x", padx=12, pady=8)
        self._slider(right, "Kp", self.form_kp, 0.0, 20.0, 0.1).pack(fill="x", padx=12, pady=8)
        self._slider(right, "Ki", self.form_ki, 0.0, 5.0, 0.05).pack(fill="x", padx=12, pady=8)
        self._slider(right, "Kd", self.form_kd, 0.0, 5.0, 0.05).pack(fill="x", padx=12, pady=8)

        row = tk.Frame(right, bg=self.theme.panel)
        row.pack(fill="x", padx=12, pady=(18, 8))
        self.btn(row, "NEU SPEICHERN", self._save_profile, self.theme.green).pack(side="left", padx=(0, 8))
        self.btn(row, "AUF LIVE ANWENDEN", self._apply_form_profile, self.theme.orange, 18).pack(side="left")
        return page

    def card(self, master: tk.Misc) -> tk.Frame:
        return tk.Frame(master, bg=self.theme.panel, highlightthickness=1, highlightbackground=self.theme.border)

    def btn(self, master: tk.Misc, text: str, command, fg: str, width: int = 14) -> tk.Button:
        return tk.Button(master, text=text, command=command, bg=self.theme.panel_alt, fg=fg, activebackground=fg, activeforeground=self.theme.bg, relief="flat", bd=0, font=("Consolas", scaled_size(12), "bold"), width=width, padx=8, pady=10)

    def _metric(self, master: tk.Misc, label: str, variable: tk.StringVar) -> tk.Frame:
        frame = tk.Frame(master, bg=self.theme.panel)
        top = tk.Frame(frame, bg=self.theme.panel)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", scaled_size(13))).pack(side="left")
        tk.Label(top, textvariable=variable, bg=self.theme.panel, fg=self.theme.text, font=("Consolas", scaled_size(13))).pack(side="right")
        canvas = tk.Canvas(frame, height=18, bg=self.theme.panel, highlightthickness=0)
        canvas.pack(fill="x", pady=(6, 0))
        canvas.create_rectangle(0, 6, 260, 14, fill=self.theme.grid, outline="")
        frame.bar = canvas.create_rectangle(0, 6, 20, 14, fill=self.theme.orange, outline="")
        frame.canvas = canvas
        return frame

    def _slider(self, master: tk.Misc, label: str, variable: tk.DoubleVar, start: float, stop: float, resolution: float, command=None) -> tk.Frame:
        card = tk.Frame(master, bg=self.theme.panel_alt, highlightthickness=1, highlightbackground=self.theme.border)
        top = tk.Frame(card, bg=self.theme.panel_alt)
        top.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(top, text=label, bg=self.theme.panel_alt, fg=self.theme.text, font=("Consolas", scaled_size(12))).pack(side="left")
        value_label = tk.Label(top, bg=self.theme.panel_alt, fg=self.theme.orange, font=("Consolas", scaled_size(12), "bold"))
        value_label.pack(side="right")

        def refresh(*_args) -> None:
            value_label.config(text=f"{variable.get():.2f}")
            if command is not None:
                command()

        variable.trace_add("write", refresh)
        refresh()
        tk.Scale(card, from_=start, to=stop, resolution=resolution, orient="horizontal", variable=variable, showvalue=False, bg=self.theme.panel_alt, fg=self.theme.text, troughcolor=self.theme.bg, activebackground=self.theme.orange, highlightthickness=0, sliderlength=24, bd=0).pack(fill="x", padx=10, pady=(6, 10))
        return card

    def _entry(self, master: tk.Misc, label: str, variable: tk.StringVar) -> tk.Frame:
        card = tk.Frame(master, bg=self.theme.panel_alt, highlightthickness=1, highlightbackground=self.theme.border)
        tk.Label(card, text=label, bg=self.theme.panel_alt, fg=self.theme.text, font=("Consolas", scaled_size(12))).pack(anchor="w", padx=12, pady=(10, 6))
        tk.Entry(card, textvariable=variable, bg=self.theme.bg, fg=self.theme.text, insertbackground=self.theme.text, relief="flat", font=("Consolas", scaled_size(13))).pack(fill="x", padx=12, pady=(0, 12))
        return card

    def show_page(self, key: str) -> None:
        self.page_frames[key].tkraise()
        for name, button in self.nav_buttons.items():
            is_active = name == key
            button.config(bg=self.theme.panel if is_active else self.theme.panel_alt, fg=self.theme.orange if is_active else self.theme.text)

    def start_heating(self) -> None:
        self.running = True
        self.service.set_mode(OperatingMode.AUTO)
        self.service.set_heating_enabled(True)
        self.status.set("Heizbetrieb aktiv")

    def _set_fan_enabled(self, enabled: bool) -> None:
        self.service.set_fan_enabled(enabled)

    def _set_valve_enabled(self, enabled: bool) -> None:
        self.service.set_valve_enabled(enabled)

    def _reload_serial_ports(self) -> None:
        ports = list_serial_ports()
        self.connection_port_box["values"] = ports
        if ports:
            if self.connection_port_var.get() not in ports:
                self.connection_port_var.set(ports[0])
        else:
            self.connection_port_var.set("")
            messagebox.showwarning("Keine Ports", "Es wurden aktuell keine seriellen Ports gefunden.", parent=self.root)

    def _replace_service(self, new_service: ControllerService, *, status_text: str, connection_text: str) -> None:
        old_service = self.service
        old_service.stop()
        self.service = new_service
        self.service_window.service = self.service
        self._last_status_timestamp = -1.0
        self.service.start()
        self.connection_state.set(connection_text)
        self.status.set(status_text)
        self._refresh_connection_ui()

    def _connect_selected_port(self) -> None:
        port = self.connection_port_var.get().strip()
        if not port:
            port = auto_serial_port() or ""
            self.connection_port_var.set(port)
        if not port:
            messagebox.showerror("Kein COM-Port", "Bitte waehle einen gueltigen COM-Port aus.", parent=self.root)
            return

        try:
            new_service = build_service(RuntimeMode.SERIAL, port)
        except Exception as exc:
            fallback_service = build_service(RuntimeMode.SIMULATION)
            self.serial_port = port
            self._replace_service(
                fallback_service,
                status_text="Simulation aktiv - Live-Verbindung fehlgeschlagen",
                connection_text=f"COM-Port {port} nicht erreichbar - Simulation aktiv",
            )
            messagebox.showwarning(
                "Verbindung fehlgeschlagen",
                f"COM-Port nicht erreichbar.\n\n{exc}\n\nGUI wurde im Simulationsmodus geoeffnet.",
                parent=self.root,
            )
            return

        self.serial_port = port
        self._replace_service(
            new_service,
            status_text=f"Live-Verbindung aktiv auf {port}",
            connection_text=f"Live verbunden: {port}",
        )

    def _refresh_connection_ui(self) -> None:
        ports = list_serial_ports()
        if hasattr(self, "connection_port_box"):
            self.connection_port_box["values"] = ports
        current_port = self.connection_port_var.get().strip()
        if self.serial_port and not current_port:
            self.connection_port_var.set(self.serial_port)
        elif ports and not current_port:
            self.connection_port_var.set(ports[0])
        if self.service.mode == RuntimeMode.SERIAL:
            port = self.connection_port_var.get() or self.serial_port or auto_serial_port() or "-"
            self.connection_state.set(f"Live verbunden: {port}")
        else:
            port = self.connection_port_var.get() or self.serial_port
            if port:
                self.connection_state.set(f"Simulation aktiv - letzter Port: {port}")
            else:
                self.connection_state.set("Simulation aktiv")

    def stop_heating(self) -> None:
        self.service.set_heating_enabled(False)
        self.service.set_mode(OperatingMode.OFF)
        self.status.set("Heizbetrieb gestoppt")

    def emergency_stop(self) -> None:
        self.running = False
        self.service.set_heating_enabled(False)
        self.service.set_mode(OperatingMode.OFF)
        self.service.set_valve_enabled(False)
        self.service.set_fan_enabled(True)
        self.status.set("Notstopp aktiv")

    def _schedule(self) -> None:
        self.root.after(int(self.sample_time * 1000), self.tick)

    def _tick_clock(self) -> None:
        self.clock.set(datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def tick(self) -> None:
        status = self.service.latest_status()
        if status.timestamp != self._last_status_timestamp:
            self._last_status_timestamp = status.timestamp
            self._append_live_status(status)
            self._refresh_live_metrics(status)

        self._tick_preview()
        self._draw_live()
        self._draw_preview()
        self._schedule()

    def _append_live_status(self, status: MachineStatus) -> None:
        self.elapsed += self.sample_time
        self.live_chart.times.append(self.elapsed)
        self.live_chart.values.append(status.temperature_c if status.temperature_c is not None else 0.0)
        self.live_chart.setpoints.append(status.setpoint_c)
        self.live_chart.outputs.append(status.heater_output_percent)
        self._record_power(self.elapsed, status.heater_output_percent)

    def _refresh_live_metrics(self, status: MachineStatus) -> None:
        actual_temp = status.temperature_c if status.temperature_c is not None else 0.0
        progress = 0.0
        if status.setpoint_c > 0:
            progress = min(100.0, max(0.0, actual_temp / status.setpoint_c * 100.0))

        avg_power = self._average_power_watts()
        self.actual.set(f"{actual_temp:.0f}")
        self.setpoint.set(f"{status.setpoint_c:.0f}")
        self.temperature_pair.set(f"{actual_temp:.0f} C / {status.setpoint_c:.0f} C")
        self.output.set(f"{status.heater_output_percent:.0f} %")
        self.progress.set(f"{progress:.0f} %")
        self.avg_power.set(f"{avg_power:.0f} W")

        if status.fault_message:
            self.status.set(f"Fehler: {status.fault_message}")
            self.sensor_status.update_state("FEHLER", self.theme.red)
            self.pid_status.update_state("STOP", self.theme.red)
            self.heat_status.update_state(status.fault_code.value.upper(), self.theme.red)
        else:
            self.sensor_status.update_state("OK", self.theme.green)
            self.pid_status.update_state("AKTIV" if status.heating_enabled else "PAUSE", self.theme.green if status.heating_enabled else self.theme.amber)
            self.heat_status.update_state(f"{progress:.0f} %", self.theme.green if progress >= 99 else self.theme.amber)

        self.fan_toggle.set_state(status.fan_enabled, 100 if status.fan_enabled else 0)
        self.valve_toggle.set_state(status.valve_enabled, 100 if status.valve_enabled else 0)
        self.power_gauge.set_percent(status.heater_output_percent)
        self._fill_bar(self.avg_power_bar, (avg_power / self.DISPLAY_MAX_POWER_WATTS) * 100.0, self.theme.green)

    def _fill_bar(self, frame: tk.Frame, percent: float, color: str) -> None:
        width = max(frame.canvas.winfo_width(), 260)
        clamped = max(0.0, min(100.0, percent))
        frame.canvas.itemconfig(frame.bar, fill=color)
        frame.canvas.coords(frame.bar, 0, 6, max(12, width * clamped / 100.0), 14)

    def _draw_live(self) -> None:
        current_time = self.live_chart.times[-1] if self.live_chart.times else 0.0
        self._draw_chart(self.temp_canvas, self.live_chart, self.theme.orange, "#3d1d0a", current_time)

    def _draw_preview(self) -> None:
        self._draw_chart(self.preview_canvas, self.preview_chart, self.theme.green, "#102419", self.preview_elapsed)

    def _draw_chart(self, canvas: tk.Canvas, chart: ChartState, process_color: str, fill_color: str, current_time: float) -> None:
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 220)
        left, top, right, bottom = 72, 94, width - 18, height - 46

        window_start, window_end = self._visible_time_window(chart, current_time)
        self._draw_legend(canvas, left, 24, process_color)
        canvas.create_text(24, (top + bottom) / 2, text="Temp. [C]", fill=self.theme.muted, font=("Consolas", scaled_size(11)), angle=90)
        canvas.create_text((left + right) / 2, bottom + 26, text="Zeit [s]", fill=self.theme.muted, font=("Consolas", scaled_size(11)))

        for temp in range(0, 301, 50):
            y = bottom - ((temp / 300.0) * (bottom - top))
            canvas.create_line(left, y, right, y, fill=self.theme.grid)

        if len(chart.values) < 2:
            self._draw_axis_ticks(canvas, left, right, top, bottom, window_start, max(chart.sample_time, window_end - window_start))
            canvas.create_rectangle(left, top, right, bottom, outline=self.theme.border)
            return

        vmin = 0.0
        vmax = 300.0
        vspan = vmax - vmin
        tspan = max(chart.sample_time, window_end - window_start)

        self._draw_axis_ticks(canvas, left, right, top, bottom, window_start, tspan)

        value_points: list[float] = []
        setpoint_points: list[float] = []
        output_points: list[float] = []
        output_fill_points: list[float] = []
        y_zero = bottom

        for timestamp, value, setpoint, output in zip(chart.times, chart.values, chart.setpoints, chart.outputs):
            x = left + ((timestamp - window_start) / tspan) * (right - left)
            y_value = bottom - ((value - vmin) / vspan) * (bottom - top)
            clamped_setpoint = max(vmin, min(vmax, setpoint))
            y_setpoint = bottom - ((clamped_setpoint - vmin) / vspan) * (bottom - top)
            y_output = y_zero - (max(0.0, min(100.0, output)) / 100.0) * (y_zero - y_setpoint)
            value_points.extend([x, y_value])
            setpoint_points.extend([x, y_setpoint])
            output_points.extend([x, y_output])
            output_fill_points.extend([x, y_output])

        if output_fill_points:
            output_fill_points = [output_points[0], y_zero] + output_fill_points + [output_points[-2], y_zero]
            canvas.create_polygon(*output_fill_points, fill=self.theme.green, outline="", stipple="gray25")
        canvas.create_line(left, y_zero, right, y_zero, fill=self.theme.grid, dash=(2, 6))
        canvas.create_line(*setpoint_points, fill=self.theme.amber, width=2, dash=(6, 5), smooth=True)
        canvas.create_line(*output_points, fill=self.theme.green, width=3)
        canvas.create_line(*value_points, fill=process_color, width=4, smooth=True)
        canvas.create_oval(value_points[-2] - 5, value_points[-1] - 5, value_points[-2] + 5, value_points[-1] + 5, fill=process_color, outline="")
        canvas.create_oval(output_points[-2] - 4, output_points[-1] - 4, output_points[-2] + 4, output_points[-1] + 4, fill=self.theme.green, outline="")
        canvas.create_rectangle(left, top, right, bottom, outline=self.theme.border)

    def _visible_time_window(self, chart: ChartState, current_time: float) -> tuple[float, float]:
        if not chart.times:
            return 0.0, max(chart.sample_time, current_time)
        window_start = chart.times[0]
        window_end = chart.times[-1]
        if window_end <= window_start:
            window_end = window_start + chart.sample_time
        return window_start, window_end

    def _draw_axis_ticks(self, canvas: tk.Canvas, left: int, right: int, top: int, bottom: int, t0: float, tspan: float) -> None:
        for temp in range(0, 301, 50):
            ratio = temp / 300.0
            y = bottom - ratio * (bottom - top)
            canvas.create_line(left - 6, y, left, y, fill=self.theme.muted)
            canvas.create_text(left - 10, y, text=f"{temp}", fill=self.theme.muted, font=("Consolas", scaled_size(10)), anchor="e")

        for index in range(5):
            ratio = index / 4
            x = left + ratio * (right - left)
            canvas.create_text(x, bottom + 10, text=f"{t0 + ratio * tspan:.0f}", fill=self.theme.muted, font=("Consolas", scaled_size(10)), anchor="n")

    def _draw_legend(self, canvas: tk.Canvas, x: int, y: int, process_color: str) -> None:
        width = max(canvas.winfo_width(), 300)
        left = x
        right = width - 24
        segment_width = (right - left) / 3
        entries = [
            ("Isttemperatur", process_color, None),
            ("Sollwert", self.theme.amber, (6, 5)),
            ("Heizleistung", self.theme.green, None),
        ]
        for index, (label, color, dash) in enumerate(entries):
            item_x = left + segment_width * index + 8
            canvas.create_line(item_x, y, item_x + 28, y, fill=color, width=4, dash=dash)
            canvas.create_text(item_x + 40, y, text=label, fill=self.theme.text, font=("Consolas", scaled_size(11)), anchor="w")

    def _output_to_watts(self, output_percent: float) -> float:
        return max(0.0, min(100.0, output_percent)) / 100.0 * self.DISPLAY_MAX_POWER_WATTS

    def _record_power(self, timestamp: float, output_percent: float) -> None:
        self.power_history.append((timestamp, self._output_to_watts(output_percent)))
        cutoff = timestamp - self.POWER_AVERAGE_WINDOW_SECONDS
        while self.power_history and self.power_history[0][0] < cutoff:
            self.power_history.popleft()

    def _average_power_watts(self) -> float:
        if not self.power_history:
            return 0.0
        return sum(power for _, power in self.power_history) / len(self.power_history)

    def _preview_changed(self) -> None:
        self._reset_preview()

    def _reset_preview(self) -> None:
        config = MachineConfig()
        config.pid.kp = self.pid_kp.get()
        config.pid.ki = self.pid_ki.get()
        config.pid.kd = self.pid_kd.get()
        config.pid.setpoint = self.pid_sp.get()
        config.pid.sample_time = self.preview_sample_time
        config.control_interval_s = self.preview_sample_time

        self.preview_elapsed = 0.0
        self.preview_chart = self._create_chart_state(self.preview_sample_time, self.PREVIEW_HISTORY_POINTS)
        self.preview_gateway = SimulationGateway(config)
        self.preview_gateway.set_target_temperature(config.pid.setpoint)
        self.preview_gateway.set_heating_enabled(True)

    def _tick_preview(self) -> None:
        if self.preview_gateway is None:
            return
        status = self.preview_gateway.poll_status()
        self.preview_elapsed += self.preview_sample_time
        self.preview_chart.times.append(self.preview_elapsed)
        self.preview_chart.values.append(status.temperature_c if status.temperature_c is not None else 0.0)
        self.preview_chart.setpoints.append(status.setpoint_c)
        self.preview_chart.outputs.append(status.heater_output_percent)

    def _apply_preview_to_live(self) -> None:
        try:
            self.service.set_pid_parameters(self.pid_kp.get(), self.pid_ki.get(), self.pid_kd.get(), self.pid_sp.get())
            self.status.set("PID-Werte aus PID-Labor uebernommen")
        except Exception as exc:
            self.status.set(f"PID-Update fehlgeschlagen: {exc}")

    def _rebuild_profile_buttons(self) -> None:
        for child in self.profile_row.winfo_children():
            child.destroy()

        self.profile_buttons.clear()
        for index, profile in enumerate(self.profiles):
            button = tk.Button(
                self.profile_row,
                text=profile.name,
                command=lambda current=profile: self._confirm_profile_switch(current),
                bg=self.theme.panel_alt,
                fg=self.theme.text,
                activebackground=self.theme.orange,
                activeforeground=self.theme.bg,
                relief="flat",
                bd=0,
                font=("Consolas", scaled_size(13), "bold"),
                padx=10,
                pady=10,
                wraplength=180,
                justify="center",
            )
            button.grid(row=index // self.PROFILE_COLUMNS, column=index % self.PROFILE_COLUMNS, sticky="nsew", padx=6, pady=6)
            self.profile_buttons[profile.name] = button

        for column in range(self.PROFILE_COLUMNS):
            self.profile_row.grid_columnconfigure(column, weight=1)

        self._mark_profile(self.active_profile)

    def _rebuild_profile_list(self) -> None:
        for child in self.profile_list.winfo_children():
            child.destroy()

        for profile in self.profiles:
            row = tk.Frame(self.profile_list, bg=self.theme.panel_alt, highlightthickness=1, highlightbackground=self.theme.border)
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=profile.name, bg=self.theme.panel_alt, fg=self.theme.orange, font=("Consolas", scaled_size(13), "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
            tk.Label(row, text=f"Soll {profile.setpoint:.0f}C   Kp {profile.kp:.2f}   Ki {profile.ki:.2f}   Kd {profile.kd:.2f}", bg=self.theme.panel_alt, fg=self.theme.text, font=("Consolas", scaled_size(11))).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))
            tk.Button(row, text="LADEN", command=lambda current=profile: self._load_profile(current), bg=self.theme.panel, fg=self.theme.text, activebackground=self.theme.orange, activeforeground=self.theme.bg, relief="flat", bd=0, font=("Consolas", scaled_size(11), "bold"), padx=12, pady=8).grid(row=0, column=1, rowspan=2, padx=12)
            row.grid_columnconfigure(0, weight=1)

    def _mark_profile(self, name: str) -> None:
        self.active_profile = name
        for key, button in self.profile_buttons.items():
            button.config(bg=self.theme.panel if key == name else self.theme.panel_alt, fg=self.theme.orange if key == name else self.theme.text)

    def _load_profile(self, profile: Profile) -> None:
        self.form_name.set(profile.name)
        self.form_sp.set(profile.setpoint)
        self.form_kp.set(profile.kp)
        self.form_ki.set(profile.ki)
        self.form_kd.set(profile.kd)
        self.status.set(f"Profil {profile.name} geladen")

    def _confirm_profile_switch(self, profile: Profile) -> None:
        if profile.name == self.active_profile:
            return

        confirmed = messagebox.askyesno(title="Materialprofil wechseln", message=f"Moechtest du das Materialprofil wirklich aendern?\n\n{profile.name}", parent=self.root)
        if confirmed:
            self._apply_profile(profile, update_form=True, push_live=True)

    def _save_profile(self) -> None:
        name = self.form_name.get().strip() or "NEUES MATERIAL"
        current = next((profile for profile in self.profiles if profile.name == name), None)
        if current is None:
            self.profiles.append(Profile(name, self.form_sp.get(), self.form_kp.get(), self.form_ki.get(), self.form_kd.get()))
        else:
            current.setpoint = self.form_sp.get()
            current.kp = self.form_kp.get()
            current.ki = self.form_ki.get()
            current.kd = self.form_kd.get()

        self._rebuild_profile_buttons()
        self._rebuild_profile_list()
        self.status.set(f"Profil {name} gespeichert")

    def _apply_form_profile(self) -> None:
        profile = Profile(self.form_name.get().strip() or "NEUES MATERIAL", self.form_sp.get(), self.form_kp.get(), self.form_ki.get(), self.form_kd.get())
        self._apply_profile(profile, update_form=False, push_live=True)

    def _apply_profile(self, profile: Profile, update_form: bool, push_live: bool) -> None:
        self.pid_kp.set(profile.kp)
        self.pid_ki.set(profile.ki)
        self.pid_kd.set(profile.kd)
        self.pid_sp.set(profile.setpoint)
        self.profile_label.set(profile.name)
        self._mark_profile(profile.name)
        if update_form:
            self._load_profile(profile)
        self._reset_preview()

        if push_live:
            try:
                self.service.set_pid_parameters(profile.kp, profile.ki, profile.kd, profile.setpoint)
            except Exception as exc:
                self.status.set(f"Profil {profile.name} lokal aktiv, Live-Update fehlgeschlagen: {exc}")
                return
        self.status.set(f"Profil {profile.name} aktiv")

    def _on_close(self) -> None:
        self.service.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
