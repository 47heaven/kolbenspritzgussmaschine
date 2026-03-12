from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

from _bootstrap import ensure_project_paths

ensure_project_paths(include_project_root=True)

from pid_simulation import FirstOrderPlant, build_demo_controller
from kolbenspritzgussmaschine.pid_control import InjectionMachinePidController, PidConfig, PidTelemetry


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
    max_points: int


class TouchToggle(tk.Frame):
    def __init__(self, master: tk.Misc, theme: UiTheme, title: str, subtitle: str, initial_percent: int) -> None:
        super().__init__(master, bg=theme.panel_alt, highlightthickness=1, highlightbackground=theme.border)
        self.enabled = tk.BooleanVar(value=True)
        self.value = tk.IntVar(value=initial_percent)

        tk.Label(self, text=title, bg=theme.panel_alt, fg=theme.muted, font=("Consolas", 11)).pack(anchor="w", padx=14, pady=(12, 10))

        row = tk.Frame(self, bg=theme.panel_alt)
        row.pack(fill="x", padx=14)
        tk.Label(row, text="Ein/Aus", bg=theme.panel_alt, fg=theme.text, font=("Consolas", 13)).pack(side="left")
        tk.Checkbutton(
            row,
            variable=self.enabled,
            bg=theme.panel_alt,
            activebackground=theme.panel_alt,
            selectcolor=theme.panel_alt,
            indicatoron=False,
            offrelief="flat",
            relief="flat",
            fg=theme.text,
            activeforeground=theme.text,
            text="AN",
            font=("Consolas", 11, "bold"),
        ).pack(side="right")

        slider_row = tk.Frame(self, bg=theme.panel_alt)
        slider_row.pack(fill="x", padx=14, pady=(10, 12))
        tk.Label(slider_row, text=subtitle, bg=theme.panel_alt, fg=theme.muted, font=("Consolas", 11)).pack(side="left")
        tk.Label(slider_row, textvariable=self.value, bg=theme.panel_alt, fg=theme.orange, font=("Consolas", 13, "bold")).pack(side="right")

        tk.Scale(
            self,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.value,
            showvalue=False,
            bg=theme.panel_alt,
            fg=theme.text,
            troughcolor=theme.bg,
            activebackground=theme.orange,
            highlightthickness=0,
            sliderlength=24,
            bd=0,
        ).pack(fill="x", padx=10, pady=(0, 10))


class StatusIndicator(tk.Frame):
    def __init__(self, master: tk.Misc, theme: UiTheme, label: str) -> None:
        super().__init__(master, bg=theme.panel_alt, highlightthickness=1, highlightbackground=theme.border)
        self.dot = tk.Canvas(self, width=18, height=18, bg=theme.panel_alt, highlightthickness=0)
        self.dot.grid(row=0, column=0, padx=(12, 8), pady=10)
        self.dot_id = self.dot.create_oval(4, 4, 14, 14, fill=theme.green, outline="")

        tk.Label(self, text=label, bg=theme.panel_alt, fg=theme.text, font=("Consolas", 12)).grid(row=0, column=1, sticky="w")
        self.value_widget = tk.Label(self, text="OK", bg=theme.panel_alt, fg=theme.text, font=("Consolas", 12, "bold"))
        self.value_widget.grid(row=0, column=2, padx=(8, 12), sticky="e")
        self.grid_columnconfigure(1, weight=1)

    def update_state(self, text: str, color: str) -> None:
        self.value_widget.config(text=text)
        self.dot.itemconfig(self.dot_id, fill=color)


class App:
    WINDOW_SIZE = "1360x820"
    DISPLAY_MAX_POWER_WATTS = 800.0
    POWER_AVERAGE_WINDOW_SECONDS = 5.0
    LIVE_HISTORY_POINTS = 300
    PREVIEW_HISTORY_POINTS = 220
    PROFILE_COLUMNS = 2

    def __init__(self) -> None:
        self.theme = UiTheme()
        self.root = self._build_root()

        self.sample_time, self.plant, self.controller = build_demo_controller()
        self.preview_plant: FirstOrderPlant | None = None
        self.preview_controller: InjectionMachinePidController | None = None
        self.preview_sample_time = 0.2

        self.running = True
        self.heating_enabled = True
        self.elapsed = 0.0
        self.preview_elapsed = 0.0

        self.live_chart = self._create_chart_state(self.sample_time, self.LIVE_HISTORY_POINTS)
        self.preview_chart = self._create_chart_state(self.preview_sample_time, self.PREVIEW_HISTORY_POINTS)
        self.power_history: deque[tuple[float, float]] = deque()

        self.profiles = self._build_default_profiles()
        self.active_profile = self.profiles[0].name

        self._init_variables()
        self._init_widget_refs()
        self._build_ui()
        self._rebuild_profile_buttons()
        self._apply_profile(self.profiles[0], update_form=True)
        self._reset_preview()
        self._tick_clock()
        self._schedule()

    def _build_root(self) -> tk.Tk:
        root = tk.Tk()
        root.title("Tiegel-Steuerung")
        root.geometry(self.WINDOW_SIZE)
        root.configure(bg=self.theme.bg)
        return root

    def _create_chart_state(self, sample_time: float, max_points: int) -> ChartState:
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
        self.status = tk.StringVar(value="Heizbetrieb aktiv (Zeitraffer-Demo)")
        self.actual = tk.StringVar(value="22")
        self.setpoint = tk.StringVar(value="200")
        self.output = tk.StringVar(value="0 %")
        self.progress = tk.StringVar(value="0 %")
        self.avg_power = tk.StringVar(value="0 W")
        self.profile_label = tk.StringVar(value=self.active_profile)

        self.pid_kp = tk.DoubleVar(value=self.controller.config.kp)
        self.pid_ki = tk.DoubleVar(value=self.controller.config.ki)
        self.pid_kd = tk.DoubleVar(value=self.controller.config.kd)
        self.pid_sp = tk.DoubleVar(value=200.0)

        self.form_name = tk.StringVar(value="NEUES MATERIAL")
        self.form_sp = tk.DoubleVar(value=210.0)
        self.form_kp = tk.DoubleVar(value=8.0)
        self.form_ki = tk.DoubleVar(value=0.7)
        self.form_kd = tk.DoubleVar(value=1.2)

    def _init_widget_refs(self) -> None:
        self.nav_buttons: dict[str, tk.Button] = {}
        self.profile_buttons: dict[str, tk.Button] = {}

        self.output_bar: tk.Frame
        self.progress_bar: tk.Frame
        self.avg_power_bar: tk.Frame
        self.temp_canvas: tk.Canvas
        self.preview_canvas: tk.Canvas
        self.profile_row: tk.Frame
        self.profile_list: tk.Frame
        self.sensor_status: StatusIndicator
        self.pid_status: StatusIndicator
        self.heat_status: StatusIndicator

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=self.theme.bg)
        outer.pack(fill="both", expand=True, padx=16, pady=16)

        self._build_header(outer)
        self._build_navigation(outer)
        self._build_pages(outer)

    def _build_header(self, master: tk.Misc) -> None:
        header = self.card(master)
        header.pack(fill="x")
        tk.Label(header, text="<> TIEGEL-STEUERUNG V1.0", bg=self.theme.panel, fg=self.theme.orange, font=("Consolas", 18, "bold")).pack(side="left", padx=16, pady=12)
        tk.Label(header, textvariable=self.status, bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 11)).pack(side="left", padx=12)
        self.btn(header, "HEIZEN START", self.start_heating, self.theme.green).pack(side="left", padx=(20, 8))
        self.btn(header, "HEIZEN STOPP", self.stop_heating, self.theme.amber).pack(side="left")
        tk.Label(header, textvariable=self.clock, bg=self.theme.panel, fg=self.theme.text, font=("Consolas", 16)).pack(side="right", padx=16)

    def _build_navigation(self, master: tk.Misc) -> None:
        nav = tk.Frame(master, bg=self.theme.bg)
        nav.pack(fill="x", pady=(12, 0))
        entries = [("dashboard", "DASHBOARD"), ("pid", "PID-LABOR"), ("profiles", "MATERIALPROFILE")]
        for key, label in entries:
            button = tk.Button(
                nav,
                text=label,
                command=lambda current=key: self.show_page(current),
                bg=self.theme.panel_alt,
                fg=self.theme.text,
                activebackground=self.theme.orange,
                activeforeground=self.theme.bg,
                relief="flat",
                bd=0,
                font=("Consolas", 13, "bold"),
                padx=18,
                pady=12,
            )
            button.pack(side="left", padx=(0, 10))
            self.nav_buttons[key] = button

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
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=6)
        page.grid_columnconfigure(2, weight=3)

        left = self.card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        center = self.card(page)
        center.grid(row=0, column=1, sticky="nsew", padx=5)
        right = self.card(page)
        right.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        self._build_dashboard_left(left)
        self._build_dashboard_center(center)
        self._build_dashboard_right(right)
        return page

    def _build_dashboard_left(self, master: tk.Misc) -> None:
        tk.Label(master, text="TEMPERATUR", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        tk.Label(master, textvariable=self.actual, bg=self.theme.panel, fg=self.theme.orange, font=("Consolas", 48)).pack(pady=(16, 0))
        tk.Label(master, text="ISTTEMPERATUR", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack()

        info = tk.Frame(master, bg=self.theme.bg, highlightthickness=1, highlightbackground=self.theme.border)
        info.pack(fill="x", padx=16, pady=12)
        tk.Label(info, text="SOLL", bg=self.theme.bg, fg=self.theme.muted, font=("Consolas", 13)).pack(anchor="w", padx=12, pady=(12, 4))
        tk.Label(info, textvariable=self.setpoint, bg=self.theme.bg, fg=self.theme.orange, font=("Consolas", 28, "bold")).pack(anchor="e", padx=12, pady=(0, 12))

        self.output_bar = self._metric(master, "Heizleistung", self.output)
        self.output_bar.pack(fill="x", padx=16, pady=8)
        self.progress_bar = self._metric(master, "Aufheizen", self.progress)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 8))
        self.avg_power_bar = self._metric(master, "Avg Leistung 5 s", self.avg_power)
        self.avg_power_bar.pack(fill="x", padx=16, pady=(0, 16))

        controls = tk.Frame(master, bg=self.theme.bg, highlightthickness=1, highlightbackground=self.theme.border)
        controls.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(controls, text="HEIZBETRIEB", bg=self.theme.bg, fg=self.theme.muted, font=("Consolas", 13)).pack(anchor="w", padx=12, pady=(12, 8))
        row = tk.Frame(controls, bg=self.theme.bg)
        row.pack(fill="x", padx=12, pady=(0, 14))
        self.btn(row, "START", self.start_heating, self.theme.green, 10).pack(side="left", padx=(0, 8))
        self.btn(row, "STOPP", self.stop_heating, self.theme.amber, 10).pack(side="left")

        footer = tk.Frame(master, bg=self.theme.panel)
        footer.pack(side="bottom", fill="x", padx=16, pady=16)
        tk.Label(footer, text="AKTIVES PROFIL", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 12)).pack(side="left")
        tk.Label(footer, textvariable=self.profile_label, bg=self.theme.panel, fg=self.theme.orange, font=("Consolas", 14, "bold")).pack(side="right")

    def _build_dashboard_center(self, master: tk.Misc) -> None:
        tk.Label(master, text="TEMPERATURVERLAUF", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))

        content = tk.Frame(master, bg=self.theme.panel)
        content.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        content.grid_rowconfigure(0, weight=2)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.temp_canvas = tk.Canvas(content, bg=self.theme.panel, highlightthickness=0)
        self.temp_canvas.grid(row=0, column=0, sticky="nsew")

        profile_area = tk.Frame(content, bg=self.theme.panel, highlightthickness=1, highlightbackground=self.theme.border)
        profile_area.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        tk.Label(profile_area, text="MATERIALPROFILE", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 13)).pack(anchor="w", padx=12, pady=(12, 8))
        tk.Label(profile_area, text="Per Touch auswaehlen. Profilwechsel wird vor dem Anwenden bestaetigt.", bg=self.theme.panel, fg=self.theme.text, font=("Consolas", 11)).pack(anchor="w", padx=12, pady=(0, 10))
        self.profile_row = tk.Frame(profile_area, bg=self.theme.panel)
        self.profile_row.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def _build_dashboard_right(self, master: tk.Misc) -> None:
        tk.Label(master, text="PERIPHERIE", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        TouchToggle(master, self.theme, "LUEFTER / ABSAUGUNG", "Leistung", 60).pack(fill="x", padx=16, pady=(0, 12))
        TouchToggle(master, self.theme, "BELEUCHTUNG", "Helligkeit", 80).pack(fill="x", padx=16, pady=(0, 18))

        tk.Label(master, text="SYSTEM", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(8, 8))
        self.sensor_status = StatusIndicator(master, self.theme, "Sensor")
        self.sensor_status.pack(fill="x", padx=16, pady=(0, 8))
        self.pid_status = StatusIndicator(master, self.theme, "PID")
        self.pid_status.pack(fill="x", padx=16, pady=(0, 8))
        self.heat_status = StatusIndicator(master, self.theme, "Aufheizen")
        self.heat_status.pack(fill="x", padx=16, pady=(0, 20))
        self.btn(master, "NOTSTOPP", self.emergency_stop, self.theme.red, 18).pack(side="bottom", fill="x", padx=16, pady=16)

    def _build_pid_page(self, master: tk.Misc) -> tk.Frame:
        page = tk.Frame(master, bg=self.theme.bg)
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=5)

        left = self.card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = self.card(page)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(left, text="PID-LABOR", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        tk.Label(left, text="PID-Werte aendern und parallel die Vorschau-Simulation beobachten.", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 11), wraplength=320, justify="left").pack(anchor="w", padx=12, pady=(0, 12))
        self._slider(left, "Kp", self.pid_kp, 0.0, 20.0, 0.1, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Ki", self.pid_ki, 0.0, 5.0, 0.05, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Kd", self.pid_kd, 0.0, 5.0, 0.05, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Sollwert", self.pid_sp, 40.0, 300.0, 1.0, self._preview_changed).pack(fill="x", padx=12, pady=8)

        row = tk.Frame(left, bg=self.theme.panel)
        row.pack(fill="x", padx=12, pady=(18, 8))
        self.btn(row, "VORSCHAU RESET", self._reset_preview, self.theme.amber).pack(side="left", padx=(0, 8))
        self.btn(row, "AUF LIVE UEBERNEHMEN", self._apply_preview_to_live, self.theme.orange, 18).pack(side="left")
        tk.Label(left, text="Im Plot sind Sollwert, Istwert und Stellwert gleichzeitig sichtbar.", bg=self.theme.panel, fg=self.theme.text, font=("Consolas", 11)).pack(anchor="w", padx=12, pady=(8, 0))

        tk.Label(right, text="SIMULATIONSVORSCHAU", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
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

        tk.Label(left, text="GESPEICHERTE PROFILE", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        self.profile_list = tk.Frame(left, bg=self.theme.panel)
        self.profile_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        tk.Label(right, text="PROFIL BEARBEITEN", bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
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
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=self.theme.panel_alt,
            fg=fg,
            activebackground=fg,
            activeforeground=self.theme.bg,
            relief="flat",
            bd=0,
            font=("Consolas", 12, "bold"),
            width=width,
            padx=8,
            pady=10,
        )

    def _metric(self, master: tk.Misc, label: str, variable: tk.StringVar) -> tk.Frame:
        frame = tk.Frame(master, bg=self.theme.panel)
        top = tk.Frame(frame, bg=self.theme.panel)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=self.theme.panel, fg=self.theme.muted, font=("Consolas", 13)).pack(side="left")
        tk.Label(top, textvariable=variable, bg=self.theme.panel, fg=self.theme.text, font=("Consolas", 13)).pack(side="right")

        canvas = tk.Canvas(frame, height=18, bg=self.theme.panel, highlightthickness=0)
        canvas.pack(fill="x", pady=(6, 0))
        canvas.create_rectangle(0, 6, 260, 14, fill=self.theme.grid, outline="")
        frame.bar = canvas.create_rectangle(0, 6, 20, 14, fill=self.theme.orange, outline="")  # type: ignore[attr-defined]
        frame.canvas = canvas  # type: ignore[attr-defined]
        return frame

    def _slider(self, master: tk.Misc, label: str, variable: tk.DoubleVar, start: float, stop: float, resolution: float, command=None) -> tk.Frame:
        card = tk.Frame(master, bg=self.theme.panel_alt, highlightthickness=1, highlightbackground=self.theme.border)
        top = tk.Frame(card, bg=self.theme.panel_alt)
        top.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(top, text=label, bg=self.theme.panel_alt, fg=self.theme.text, font=("Consolas", 12)).pack(side="left")
        value_label = tk.Label(top, bg=self.theme.panel_alt, fg=self.theme.orange, font=("Consolas", 12, "bold"))
        value_label.pack(side="right")

        def refresh(*_args) -> None:
            value_label.config(text=f"{variable.get():.2f}")
            if command is not None:
                command()

        variable.trace_add("write", refresh)
        refresh()
        tk.Scale(
            card,
            from_=start,
            to=stop,
            resolution=resolution,
            orient="horizontal",
            variable=variable,
            showvalue=False,
            bg=self.theme.panel_alt,
            fg=self.theme.text,
            troughcolor=self.theme.bg,
            activebackground=self.theme.orange,
            highlightthickness=0,
            sliderlength=24,
            bd=0,
        ).pack(fill="x", padx=10, pady=(6, 10))
        return card

    def _entry(self, master: tk.Misc, label: str, variable: tk.StringVar) -> tk.Frame:
        card = tk.Frame(master, bg=self.theme.panel_alt, highlightthickness=1, highlightbackground=self.theme.border)
        tk.Label(card, text=label, bg=self.theme.panel_alt, fg=self.theme.text, font=("Consolas", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        tk.Entry(card, textvariable=variable, bg=self.theme.bg, fg=self.theme.text, insertbackground=self.theme.text, relief="flat", font=("Consolas", 13)).pack(fill="x", padx=12, pady=(0, 12))
        return card

    def show_page(self, key: str) -> None:
        self.page_frames[key].tkraise()
        for name, button in self.nav_buttons.items():
            is_active = name == key
            button.config(
                bg=self.theme.panel if is_active else self.theme.panel_alt,
                fg=self.theme.orange if is_active else self.theme.text,
            )

    def start_heating(self) -> None:
        self.running = True
        self.heating_enabled = True
        self.controller.enable()
        self.status.set("Heizbetrieb aktiv")

    def stop_heating(self) -> None:
        self.heating_enabled = False
        self.controller.disable()
        self.status.set("Heizbetrieb gestoppt")

    def emergency_stop(self) -> None:
        self.running = False
        self.heating_enabled = False
        self.controller.disable()
        self.status.set("Notstopp aktiv")

    def _schedule(self) -> None:
        self.root.after(int(self.sample_time * 1000), self.tick)

    def _tick_clock(self) -> None:
        self.clock.set(datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def tick(self) -> None:
        if self.running:
            telemetry = self._next_live_telemetry()
            self.plant.step(self.sample_time)
            self.elapsed += self.sample_time
            self._append_chart_sample(self.live_chart, self.elapsed, telemetry)
            self._record_power(self.elapsed, telemetry.control_output)
            self._refresh_live_metrics(telemetry)

        self._tick_preview()
        self._draw_live()
        self._draw_preview()
        self._schedule()

    def _next_live_telemetry(self) -> PidTelemetry:
        if self.heating_enabled:
            return self.controller.update_once()

        current = self.plant.read()
        self.plant.stop()
        return PidTelemetry(
            self.elapsed,
            current,
            float(self.controller.pid.setpoint),
            0.0,
            float(self.controller.pid.setpoint - current),
            0.0,
            0.0,
            0.0,
        )

    def _append_chart_sample(self, chart: ChartState, timestamp: float, telemetry: PidTelemetry) -> None:
        chart.times.append(timestamp)
        chart.values.append(telemetry.process_value)
        chart.setpoints.append(telemetry.setpoint)
        chart.outputs.append(telemetry.control_output)

    def _refresh_live_metrics(self, telemetry: PidTelemetry) -> None:
        progress = 0.0
        if telemetry.setpoint > 0:
            progress = min(100.0, max(0.0, telemetry.process_value / telemetry.setpoint * 100.0))

        avg_power = self._average_power_watts()
        self.actual.set(f"{telemetry.process_value:.0f}")
        self.setpoint.set(f"{telemetry.setpoint:.0f}")
        self.output.set(f"{telemetry.control_output:.0f} %")
        self.progress.set(f"{progress:.0f} %")
        self.avg_power.set(f"{avg_power:.0f} W")

        self.sensor_status.update_state("OK", self.theme.green)
        self.pid_status.update_state("AKTIV" if self.heating_enabled else "PAUSE", self.theme.green if self.heating_enabled else self.theme.amber)
        self.heat_status.update_state(f"{progress:.0f} %", self.theme.green if progress >= 99 else self.theme.amber)

        self._fill_bar(self.output_bar, telemetry.control_output, self.theme.orange)
        self._fill_bar(self.progress_bar, progress, self.theme.amber)
        self._fill_bar(self.avg_power_bar, (avg_power / self.DISPLAY_MAX_POWER_WATTS) * 100.0, self.theme.green)

    def _fill_bar(self, frame: tk.Frame, percent: float, color: str) -> None:
        width = max(frame.canvas.winfo_width(), 260)  # type: ignore[attr-defined]
        clamped = max(0.0, min(100.0, percent))
        frame.canvas.itemconfig(frame.bar, fill=color)  # type: ignore[attr-defined]
        frame.canvas.coords(frame.bar, 0, 6, max(12, width * clamped / 100.0), 14)  # type: ignore[attr-defined]

    def _draw_live(self) -> None:
        self._draw_chart(self.temp_canvas, self.live_chart, self.theme.orange, "#3d1d0a", self.elapsed)

    def _draw_preview(self) -> None:
        self._draw_chart(self.preview_canvas, self.preview_chart, self.theme.green, "#102419", self.preview_elapsed)

    def _draw_chart(self, canvas: tk.Canvas, chart: ChartState, process_color: str, fill_color: str, current_time: float) -> None:
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 220)
        left, top, right, bottom = 54, 58, width - 18, height - 34

        window_start, window_end = self._visible_time_window(chart, current_time)
        self._draw_legend(canvas, left, 20, process_color)
        canvas.create_text(18, (top + bottom) / 2, text="Temp. [C]", fill=self.theme.muted, font=("Consolas", 11), angle=90)
        canvas.create_text((left + right) / 2, height - 12, text=f"Zeit [s]  Fenster {window_start:.0f} - {window_end:.0f}", fill=self.theme.muted, font=("Consolas", 11))

        for index in range(5):
            y = top + ((bottom - top) / 4) * index
            canvas.create_line(left, y, right, y, fill=self.theme.grid)

        if len(chart.values) < 2:
            self._draw_axis_ticks(canvas, left, right, top, bottom, window_start, max(chart.sample_time, window_end - window_start), 0.0, 100.0)
            canvas.create_rectangle(left, top, right, bottom, outline=self.theme.border)
            return

        vmin = min(min(chart.values), min(chart.setpoints)) - 10
        vmax = max(max(chart.values), max(chart.setpoints)) + 10
        vspan = max(20.0, vmax - vmin)
        tspan = max(chart.sample_time, window_end - window_start)

        self._draw_axis_ticks(canvas, left, right, top, bottom, window_start, tspan, vmin, vspan)

        fill_points = [left, bottom]
        value_points: list[float] = []
        setpoint_points: list[float] = []
        output_points: list[float] = []

        for timestamp, value, setpoint, output in zip(chart.times, chart.values, chart.setpoints, chart.outputs):
            x = left + ((timestamp - window_start) / tspan) * (right - left)
            y_value = bottom - ((value - vmin) / vspan) * (bottom - top)
            y_setpoint = bottom - ((setpoint - vmin) / vspan) * (bottom - top)
            y_output = bottom - (max(0.0, min(100.0, output)) / 100.0) * ((bottom - top) * 0.32)

            fill_points.extend([x, y_value])
            value_points.extend([x, y_value])
            setpoint_points.extend([x, y_setpoint])
            output_points.extend([x, y_output])

        fill_points.extend([right, bottom])
        canvas.create_polygon(*fill_points, fill=fill_color, outline="", smooth=True)
        canvas.create_line(*setpoint_points, fill=self.theme.amber, width=2, dash=(6, 5), smooth=True)
        canvas.create_line(*value_points, fill=process_color, width=4, smooth=True)
        canvas.create_line(*output_points, fill=self.theme.green, width=3, smooth=True)
        canvas.create_oval(value_points[-2] - 5, value_points[-1] - 5, value_points[-2] + 5, value_points[-1] + 5, fill=process_color, outline="")
        canvas.create_oval(output_points[-2] - 4, output_points[-1] - 4, output_points[-2] + 4, output_points[-1] + 4, fill=self.theme.green, outline="")
        canvas.create_rectangle(left, top, right, bottom, outline=self.theme.border)

    def _visible_time_window(self, chart: ChartState, current_time: float) -> tuple[float, float]:
        visible_span = chart.sample_time * max(2, chart.max_points)
        window_end = chart.times[-1] if chart.times else current_time
        window_start = max(0.0, window_end - visible_span)
        return window_start, window_end

    def _draw_axis_ticks(self, canvas: tk.Canvas, left: int, right: int, top: int, bottom: int, t0: float, tspan: float, vmin: float, vspan: float) -> None:
        for index in range(5):
            ratio = index / 4
            y = bottom - ratio * (bottom - top)
            x = left + ratio * (right - left)
            canvas.create_text(left - 8, y, text=f"{vmin + ratio * vspan:.0f}", fill=self.theme.muted, font=("Consolas", 10), anchor="e")
            canvas.create_text(x, bottom + 14, text=f"{t0 + ratio * tspan:.0f}", fill=self.theme.muted, font=("Consolas", 10), anchor="n")

    def _draw_legend(self, canvas: tk.Canvas, x: int, y: int, process_color: str) -> None:
        entries = [
            ("Isttemperatur", process_color, None),
            ("Sollwert", self.theme.amber, (6, 5)),
            ("Stellwert", self.theme.green, None),
        ]
        cursor = x
        for label, color, dash in entries:
            canvas.create_line(cursor, y, cursor + 22, y, fill=color, width=3, dash=dash)
            canvas.create_text(cursor + 30, y, text=label, fill=self.theme.text, font=("Consolas", 11), anchor="w")
            cursor += 118 if label == "Sollwert" else 136

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
        self.preview_elapsed = 0.0
        self.preview_chart = self._create_chart_state(self.preview_sample_time, self.PREVIEW_HISTORY_POINTS)
        self.preview_plant = FirstOrderPlant.timelapse_demo()
        self.preview_controller = InjectionMachinePidController(
            sensor=self.preview_plant,
            actuator=self.preview_plant,
            config=PidConfig(
                kp=self.pid_kp.get(),
                ki=self.pid_ki.get(),
                kd=self.pid_kd.get(),
                setpoint=self.pid_sp.get(),
                sample_time=self.preview_sample_time,
                output_limits=(0.0, 100.0),
                starting_output=0.0,
            ),
        )

    def _tick_preview(self) -> None:
        if self.preview_controller is None or self.preview_plant is None:
            return

        telemetry = self.preview_controller.update_once()
        self.preview_plant.step(self.preview_sample_time)
        self.preview_elapsed += self.preview_sample_time
        self._append_chart_sample(self.preview_chart, self.preview_elapsed, telemetry)

    def _apply_preview_to_live(self) -> None:
        self._set_controller_config(
            Profile(
                name=self.active_profile,
                setpoint=self.pid_sp.get(),
                kp=self.pid_kp.get(),
                ki=self.pid_ki.get(),
                kd=self.pid_kd.get(),
            )
        )
        self.status.set("PID-Werte aus PID-Labor uebernommen")

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
                font=("Consolas", 13, "bold"),
                padx=18,
                pady=18,
                wraplength=160,
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
            tk.Label(row, text=profile.name, bg=self.theme.panel_alt, fg=self.theme.orange, font=("Consolas", 13, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
            tk.Label(row, text=f"Soll {profile.setpoint:.0f}C   Kp {profile.kp:.2f}   Ki {profile.ki:.2f}   Kd {profile.kd:.2f}", bg=self.theme.panel_alt, fg=self.theme.text, font=("Consolas", 11)).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))
            tk.Button(row, text="LADEN", command=lambda current=profile: self._load_profile(current), bg=self.theme.panel, fg=self.theme.text, activebackground=self.theme.orange, activeforeground=self.theme.bg, relief="flat", bd=0, font=("Consolas", 11, "bold"), padx=12, pady=8).grid(row=0, column=1, rowspan=2, padx=12)
            row.grid_columnconfigure(0, weight=1)

    def _mark_profile(self, name: str) -> None:
        self.active_profile = name
        for key, button in self.profile_buttons.items():
            button.config(
                bg=self.theme.panel if key == name else self.theme.panel_alt,
                fg=self.theme.orange if key == name else self.theme.text,
            )

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

        confirmed = messagebox.askyesno(
            title="Materialprofil wechseln",
            message=f"Moechtest du das Materialprofil wirklich aendern?\n\n{profile.name}",
            parent=self.root,
        )
        if confirmed:
            self._apply_profile(profile, update_form=True)

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
        profile = Profile(
            self.form_name.get().strip() or "NEUES MATERIAL",
            self.form_sp.get(),
            self.form_kp.get(),
            self.form_ki.get(),
            self.form_kd.get(),
        )
        self._apply_profile(profile, update_form=False)

    def _apply_profile(self, profile: Profile, update_form: bool) -> None:
        self._set_controller_config(profile)
        self.profile_label.set(profile.name)
        self._mark_profile(profile.name)
        if update_form:
            self._load_profile(profile)
        self._reset_preview()
        self.status.set(f"Profil {profile.name} aktiv")

    def _set_controller_config(self, profile: Profile) -> None:
        config = self.controller.config
        config.kp = profile.kp
        config.ki = profile.ki
        config.kd = profile.kd
        config.setpoint = profile.setpoint

        self.controller = InjectionMachinePidController(sensor=self.plant, actuator=self.plant, config=config)
        self.controller.set_setpoint(profile.setpoint)

        self.pid_kp.set(profile.kp)
        self.pid_ki.set(profile.ki)
        self.pid_kd.set(profile.kd)
        self.pid_sp.set(profile.setpoint)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
