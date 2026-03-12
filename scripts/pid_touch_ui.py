from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import tkinter as tk

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


class TouchToggle(tk.Frame):
    def __init__(self, master: tk.Misc, theme, title: str, subtitle: str, initial_percent: int) -> None:
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
        tk.Label(slider_row, textvariable=self.value, bg=theme.panel_alt, fg=theme.accent_soft, font=("Consolas", 13, "bold")).pack(side="right")

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
            activebackground=theme.accent,
            highlightthickness=0,
            sliderlength=24,
            bd=0,
        ).pack(fill="x", padx=10, pady=(0, 10))


class StatusIndicator(tk.Frame):
    def __init__(self, master: tk.Misc, theme, label: str) -> None:
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
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Tiegel-Steuerung")
        self.root.geometry("1360x820")
        self.root.configure(bg="#07111f")
        self.colors = {"bg": "#07111f", "panel": "#0b1526", "alt": "#0d1a2f", "border": "#18263a", "grid": "#14243a", "text": "#d8e2f0", "muted": "#6d7c90", "orange": "#ff7a1a", "amber": "#ffc247", "green": "#32d98b", "red": "#ff5b57"}

        self.sample_time, self.plant, self.controller = build_demo_controller()
        self.running = True
        self.heating_enabled = True
        self.elapsed = 0.0
        self.time_history: deque[float] = deque(maxlen=300)
        self.temp_history: deque[float] = deque(maxlen=300)
        self.sp_history: deque[float] = deque(maxlen=300)
        self.out_history: deque[float] = deque(maxlen=300)

        self.preview_plant: FirstOrderPlant | None = None
        self.preview_controller: InjectionMachinePidController | None = None
        self.preview_sample_time = 0.2
        self.preview_elapsed = 0.0
        self.preview_t: deque[float] = deque(maxlen=220)
        self.preview_temp: deque[float] = deque(maxlen=220)
        self.preview_sp: deque[float] = deque(maxlen=220)
        self.preview_out: deque[float] = deque(maxlen=220)

        self.profiles = [
            Profile("PLA 200", 200.0, 8.0, 0.7, 1.2),
            Profile("PETG 230", 230.0, 8.5, 0.8, 1.1),
            Profile("ABS 240", 240.0, 9.0, 0.9, 1.0),
        ]
        self.active_profile = self.profiles[0].name

        self.clock = tk.StringVar(value="--:--:--")
        self.status = tk.StringVar(value="Heizbetrieb aktiv")
        self.actual = tk.StringVar(value="22")
        self.setpoint = tk.StringVar(value="200")
        self.output = tk.StringVar(value="0 %")
        self.progress = tk.StringVar(value="0 %")
        self.pid_live = tk.StringVar(value="Kp 8.0   Ki 0.7   Kd 1.2")
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

        self.nav_buttons: dict[str, tk.Button] = {}
        self.profile_buttons: dict[str, tk.Button] = {}
        self._build()
        self._apply_profile(self.profiles[0], update_form=True)
        self._reset_preview()
        self._tick_clock()
        self._schedule()

    def card(self, master: tk.Misc) -> tk.Frame:
        return tk.Frame(master, bg=self.colors["panel"], highlightthickness=1, highlightbackground=self.colors["border"])

    def btn(self, master: tk.Misc, text: str, cmd, fg: str, width: int = 14) -> tk.Button:
        return tk.Button(master, text=text, command=cmd, bg=self.colors["alt"], fg=fg, activebackground=fg, activeforeground=self.colors["bg"], relief="flat", bd=0, font=("Consolas", 12, "bold"), width=width, padx=8, pady=10)

    def _build(self) -> None:
        outer = tk.Frame(self.root, bg=self.colors["bg"])
        outer.pack(fill="both", expand=True, padx=16, pady=16)

        header = self.card(outer)
        header.pack(fill="x")
        tk.Label(header, text="<> TIEGEL-STEUERUNG V1.0", bg=self.colors["panel"], fg=self.colors["orange"], font=("Consolas", 18, "bold")).pack(side="left", padx=16, pady=12)
        tk.Label(header, textvariable=self.status, bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 11)).pack(side="left", padx=12)
        self.btn(header, "HEIZEN START", self.start_heating, self.colors["green"]).pack(side="left", padx=(20, 8))
        self.btn(header, "HEIZEN STOPP", self.stop_heating, self.colors["amber"]).pack(side="left")
        tk.Label(header, textvariable=self.clock, bg=self.colors["panel"], fg=self.colors["text"], font=("Consolas", 16)).pack(side="right", padx=16)

        nav = tk.Frame(outer, bg=self.colors["bg"])
        nav.pack(fill="x", pady=(12, 0))
        for key, label in [("dashboard", "DASHBOARD"), ("pid", "PID-LABOR"), ("profiles", "MATERIALPROFILE")]:
            b = tk.Button(nav, text=label, command=lambda k=key: self.show_page(k), bg=self.colors["alt"], fg=self.colors["text"], activebackground=self.colors["orange"], activeforeground=self.colors["bg"], relief="flat", bd=0, font=("Consolas", 13, "bold"), padx=18, pady=12)
            b.pack(side="left", padx=(0, 10))
            self.nav_buttons[key] = b

        self.pages = tk.Frame(outer, bg=self.colors["bg"])
        self.pages.pack(fill="both", expand=True, pady=(12, 0))
        self.pages.grid_rowconfigure(0, weight=1)
        self.pages.grid_columnconfigure(0, weight=1)
        self.page_frames = {
            "dashboard": self._build_dashboard(self.pages),
            "pid": self._build_pid_page(self.pages),
            "profiles": self._build_profiles_page(self.pages),
        }
        for frame in self.page_frames.values():
            frame.grid(row=0, column=0, sticky="nsew")
        self.show_page("dashboard")

    def _build_dashboard(self, master: tk.Misc) -> tk.Frame:
        page = tk.Frame(master, bg=self.colors["bg"])
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=6)
        page.grid_columnconfigure(2, weight=3)

        left = self.card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        center = self.card(page)
        center.grid(row=0, column=1, sticky="nsew", padx=5)
        right = self.card(page)
        right.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        tk.Label(left, text="TEMPERATUR", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        tk.Label(left, textvariable=self.actual, bg=self.colors["panel"], fg=self.colors["orange"], font=("Consolas", 48)).pack(pady=(16, 0))
        tk.Label(left, text="ISTTEMPERATUR", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack()
        info = tk.Frame(left, bg=self.colors["bg"], highlightthickness=1, highlightbackground=self.colors["border"])
        info.pack(fill="x", padx=16, pady=12)
        tk.Label(info, text="SOLL", bg=self.colors["bg"], fg=self.colors["muted"], font=("Consolas", 13)).pack(anchor="w", padx=12, pady=(12, 4))
        tk.Label(info, textvariable=self.setpoint, bg=self.colors["bg"], fg=self.colors["orange"], font=("Consolas", 28, "bold")).pack(anchor="e", padx=12, pady=(0, 12))
        self.output_bar = self._metric(left, "Heizleistung", self.output)
        self.output_bar.pack(fill="x", padx=16, pady=8)
        self.progress_bar = self._metric(left, "Aufheizen", self.progress)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 16))
        controls = tk.Frame(left, bg=self.colors["bg"], highlightthickness=1, highlightbackground=self.colors["border"])
        controls.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(controls, text="HEIZBETRIEB", bg=self.colors["bg"], fg=self.colors["muted"], font=("Consolas", 13)).pack(anchor="w", padx=12, pady=(12, 8))
        row = tk.Frame(controls, bg=self.colors["bg"])
        row.pack(fill="x", padx=12, pady=(0, 14))
        self.btn(row, "START", self.start_heating, self.colors["green"], 10).pack(side="left", padx=(0, 8))
        self.btn(row, "STOPP", self.stop_heating, self.colors["amber"], 10).pack(side="left")
        footer = tk.Frame(left, bg=self.colors["panel"])
        footer.pack(side="bottom", fill="x", padx=16, pady=16)
        tk.Label(footer, text="AKTIVES PROFIL", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 12)).pack(side="left")
        tk.Label(footer, textvariable=self.profile_label, bg=self.colors["panel"], fg=self.colors["orange"], font=("Consolas", 14, "bold")).pack(side="right")

        tk.Label(center, text="TEMPERATURVERLAUF", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        holder = tk.Frame(center, bg=self.colors["panel"])
        holder.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        holder.grid_rowconfigure(0, weight=4)
        holder.grid_rowconfigure(1, weight=2)
        holder.grid_columnconfigure(0, weight=1)
        self.temp_canvas = tk.Canvas(holder, bg=self.colors["panel"], highlightthickness=0)
        self.temp_canvas.grid(row=0, column=0, sticky="nsew")
        self.out_canvas = tk.Canvas(holder, bg=self.colors["panel"], highlightthickness=0)
        self.out_canvas.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        profile_area = tk.Frame(center, bg=self.colors["panel"])
        profile_area.pack(fill="x", padx=16, pady=(0, 14))
        tk.Label(profile_area, text="MATERIALPROFILE", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 13)).pack(anchor="w", pady=(0, 8))
        self.profile_row = tk.Frame(profile_area, bg=self.colors["panel"])
        self.profile_row.pack(fill="x")

        tk.Label(right, text="PERIPHERIE", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        TouchToggle(right, self._theme(), "LUEFTER / ABSAUGUNG", "Leistung", 60).pack(fill="x", padx=16, pady=(0, 12))
        TouchToggle(right, self._theme(), "BELEUCHTUNG", "Helligkeit", 80).pack(fill="x", padx=16, pady=(0, 18))
        tk.Label(right, text="SYSTEM", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(8, 8))
        self.sensor_status = StatusIndicator(right, self._theme(), "Sensor")
        self.sensor_status.pack(fill="x", padx=16, pady=(0, 8))
        self.pid_status = StatusIndicator(right, self._theme(), "PID")
        self.pid_status.pack(fill="x", padx=16, pady=(0, 8))
        self.heat_status = StatusIndicator(right, self._theme(), "Aufheizen")
        self.heat_status.pack(fill="x", padx=16, pady=(0, 20))
        self.btn(right, "NOTSTOPP", self.emergency_stop, self.colors["red"], 18).pack(side="bottom", fill="x", padx=16, pady=16)
        return page

    def _build_pid_page(self, master: tk.Misc) -> tk.Frame:
        page = tk.Frame(master, bg=self.colors["bg"])
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=5)
        left = self.card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = self.card(page)
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(left, text="PID-LABOR", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        tk.Label(left, text="PID-Werte aendern und parallel die Vorschau-Simulation beobachten.", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 11), wraplength=320, justify="left").pack(anchor="w", padx=12, pady=(0, 12))
        self._slider(left, "Kp", self.pid_kp, 0.0, 20.0, 0.1, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Ki", self.pid_ki, 0.0, 5.0, 0.05, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Kd", self.pid_kd, 0.0, 5.0, 0.05, self._preview_changed).pack(fill="x", padx=12, pady=8)
        self._slider(left, "Sollwert", self.pid_sp, 40.0, 300.0, 1.0, self._preview_changed).pack(fill="x", padx=12, pady=8)
        row = tk.Frame(left, bg=self.colors["panel"])
        row.pack(fill="x", padx=12, pady=(18, 8))
        self.btn(row, "VORSCHAU RESET", self._reset_preview, self.colors["amber"]).pack(side="left", padx=(0, 8))
        self.btn(row, "AUF LIVE UEBERNEHMEN", self._apply_preview_to_live, self.colors["orange"], 18).pack(side="left")
        tk.Label(left, text="Im Plot sind Sollwert, Istwert und Stellwert gleichzeitig sichtbar.", bg=self.colors["panel"], fg=self.colors["text"], font=("Consolas", 11)).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(right, text="SIMULATIONSVORSCHAU", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        self.preview_canvas = tk.Canvas(right, bg=self.colors["panel"], highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        return page

    def _build_profiles_page(self, master: tk.Misc) -> tk.Frame:
        page = tk.Frame(master, bg=self.colors["bg"])
        page.grid_columnconfigure(0, weight=4)
        page.grid_columnconfigure(1, weight=3)
        left = self.card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = self.card(page)
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(left, text="GESPEICHERTE PROFILE", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        self.profile_list = tk.Frame(left, bg=self.colors["panel"])
        self.profile_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        tk.Label(right, text="PROFIL BEARBEITEN", bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 14)).pack(anchor="w", padx=12, pady=(12, 8))
        self._entry(right, "Name", self.form_name).pack(fill="x", padx=12, pady=8)
        self._slider(right, "Sollwert", self.form_sp, 40.0, 300.0, 1.0).pack(fill="x", padx=12, pady=8)
        self._slider(right, "Kp", self.form_kp, 0.0, 20.0, 0.1).pack(fill="x", padx=12, pady=8)
        self._slider(right, "Ki", self.form_ki, 0.0, 5.0, 0.05).pack(fill="x", padx=12, pady=8)
        self._slider(right, "Kd", self.form_kd, 0.0, 5.0, 0.05).pack(fill="x", padx=12, pady=8)
        row = tk.Frame(right, bg=self.colors["panel"])
        row.pack(fill="x", padx=12, pady=(18, 8))
        self.btn(row, "NEU SPEICHERN", self._save_profile, self.colors["green"]).pack(side="left", padx=(0, 8))
        self.btn(row, "AUF LIVE ANWENDEN", self._apply_form_profile, self.colors["orange"], 18).pack(side="left")
        return page

    def _metric(self, master: tk.Misc, label: str, variable: tk.StringVar) -> tk.Frame:
        frame = tk.Frame(master, bg=self.colors["panel"])
        top = tk.Frame(frame, bg=self.colors["panel"])
        top.pack(fill="x")
        tk.Label(top, text=label, bg=self.colors["panel"], fg=self.colors["muted"], font=("Consolas", 13)).pack(side="left")
        tk.Label(top, textvariable=variable, bg=self.colors["panel"], fg=self.colors["text"], font=("Consolas", 13)).pack(side="right")
        canvas = tk.Canvas(frame, height=18, bg=self.colors["panel"], highlightthickness=0)
        canvas.pack(fill="x", pady=(6, 0))
        canvas.create_rectangle(0, 6, 260, 14, fill=self.colors["grid"], outline="")
        frame.bar = canvas.create_rectangle(0, 6, 20, 14, fill=self.colors["orange"], outline="")  # type: ignore[attr-defined]
        frame.canvas = canvas  # type: ignore[attr-defined]
        return frame

    def _slider(self, master: tk.Misc, label: str, var: tk.DoubleVar, start: float, stop: float, resolution: float, command=None) -> tk.Frame:
        card = tk.Frame(master, bg=self.colors["alt"], highlightthickness=1, highlightbackground=self.colors["border"])
        top = tk.Frame(card, bg=self.colors["alt"])
        top.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(top, text=label, bg=self.colors["alt"], fg=self.colors["text"], font=("Consolas", 12)).pack(side="left")
        value = tk.Label(top, bg=self.colors["alt"], fg=self.colors["orange"], font=("Consolas", 12, "bold"))
        value.pack(side="right")
        def refresh(*_args):
            value.config(text=f"{var.get():.2f}")
            if command:
                command()
        var.trace_add("write", refresh)
        refresh()
        tk.Scale(card, from_=start, to=stop, resolution=resolution, orient="horizontal", variable=var, showvalue=False, bg=self.colors["alt"], fg=self.colors["text"], troughcolor=self.colors["bg"], activebackground=self.colors["orange"], highlightthickness=0, sliderlength=24, bd=0).pack(fill="x", padx=10, pady=(6, 10))
        return card

    def _entry(self, master: tk.Misc, label: str, variable: tk.StringVar) -> tk.Frame:
        card = tk.Frame(master, bg=self.colors["alt"], highlightthickness=1, highlightbackground=self.colors["border"])
        tk.Label(card, text=label, bg=self.colors["alt"], fg=self.colors["text"], font=("Consolas", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        tk.Entry(card, textvariable=variable, bg=self.colors["bg"], fg=self.colors["text"], insertbackground=self.colors["text"], relief="flat", font=("Consolas", 13)).pack(fill="x", padx=12, pady=(0, 12))
        return card

    def _theme(self):
        return type("T", (), {"panel_alt": self.colors["alt"], "border": self.colors["border"], "text": self.colors["text"], "muted": self.colors["muted"], "accent": self.colors["orange"], "accent_soft": self.colors["orange"], "bg": self.colors["bg"], "green": self.colors["green"]})()

    def show_page(self, key: str) -> None:
        self.page_frames[key].tkraise()
        for name, btn in self.nav_buttons.items():
            active = name == key
            btn.config(bg=self.colors["panel"] if active else self.colors["alt"], fg=self.colors["orange"] if active else self.colors["text"])

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
            if self.heating_enabled:
                telemetry = self.controller.update_once()
            else:
                current = self.plant.read()
                self.plant.stop()
                telemetry = PidTelemetry(self.elapsed, current, float(self.controller.pid.setpoint), 0.0, float(self.controller.pid.setpoint - current), 0.0, 0.0, 0.0)
            self.plant.step(self.sample_time)
            self.elapsed += self.sample_time
            self.time_history.append(self.elapsed)
            self.temp_history.append(telemetry.process_value)
            self.sp_history.append(telemetry.setpoint)
            self.out_history.append(telemetry.control_output)
            self._refresh_live(telemetry)
        self._tick_preview()
        self._draw_live()
        self._draw_preview()
        self._schedule()

    def _refresh_live(self, telemetry: PidTelemetry) -> None:
        progress = 0.0 if telemetry.setpoint <= 0 else min(100.0, max(0.0, telemetry.process_value / telemetry.setpoint * 100.0))
        self.actual.set(f"{telemetry.process_value:.0f}")
        self.setpoint.set(f"{telemetry.setpoint:.0f}")
        self.output.set(f"{telemetry.control_output:.0f} %")
        self.progress.set(f"{progress:.0f} %")
        self.pid_live.set(f"Kp {self.controller.config.kp:.2f}   Ki {self.controller.config.ki:.2f}   Kd {self.controller.config.kd:.2f}")
        self.sensor_status.update_state("OK", self.colors["green"])
        self.pid_status.update_state("AKTIV" if self.heating_enabled else "PAUSE", self.colors["green"] if self.heating_enabled else self.colors["amber"])
        self.heat_status.update_state(f"{progress:.0f} %", self.colors["amber"] if progress < 99 else self.colors["green"])
        self._fill_bar(self.output_bar, telemetry.control_output, self.colors["orange"])
        self._fill_bar(self.progress_bar, progress, self.colors["amber"])

    def _fill_bar(self, frame: tk.Frame, percent: float, color: str) -> None:
        width = max(frame.canvas.winfo_width(), 260)  # type: ignore[attr-defined]
        frame.canvas.itemconfig(frame.bar, fill=color)  # type: ignore[attr-defined]
        frame.canvas.coords(frame.bar, 0, 6, max(12, width * max(0.0, min(100.0, percent)) / 100.0), 14)  # type: ignore[attr-defined]

    def _draw_live(self) -> None:
        self._draw_chart(self.temp_canvas, self.time_history, self.temp_history, self.sp_history, self.out_history, self.colors["orange"], "#3d1d0a", True)
        self._draw_output(self.out_canvas, self.time_history, self.out_history)

    def _draw_preview(self) -> None:
        self._draw_chart(self.preview_canvas, self.preview_t, self.preview_temp, self.preview_sp, self.preview_out, self.colors["green"], "#102419", True)

    def _draw_chart(self, canvas: tk.Canvas, times, values, setpoints, outputs, line_color: str, fill_color: str, overlay_output: bool) -> None:
        canvas.delete("all")
        w = max(canvas.winfo_width(), 300)
        h = max(canvas.winfo_height(), 220)
        left, top, right, bottom = 54, 26, w - 18, h - 34
        for i in range(5):
            y = top + ((bottom - top) / 4) * i
            canvas.create_line(left, y, right, y, fill=self.colors["grid"])
        if len(values) < 2:
            canvas.create_rectangle(left, top, right, bottom, outline=self.colors["border"])
            return
        vmin = min(min(values), min(setpoints)) - 10
        vmax = max(max(values), max(setpoints)) + 10
        span = max(20.0, vmax - vmin)
        t0 = times[0]
        tspan = max(self.sample_time, times[-1] - t0)
        p_fill, p_val, p_sp, p_out = [left, bottom], [], [], []
        for i, (t, v, sp) in enumerate(zip(times, values, setpoints)):
            x = left + ((t - t0) / tspan) * (right - left)
            yv = bottom - ((v - vmin) / span) * (bottom - top)
            ys = bottom - ((sp - vmin) / span) * (bottom - top)
            p_fill.extend([x, yv]); p_val.extend([x, yv]); p_sp.extend([x, ys])
            if overlay_output:
                yo = bottom - (max(0.0, min(100.0, outputs[i])) / 100.0) * ((bottom - top) * 0.35)
                p_out.extend([x, yo])
        p_fill.extend([right, bottom])
        canvas.create_polygon(*p_fill, fill=fill_color, outline="", smooth=True)
        canvas.create_line(*p_sp, fill=self.colors["amber"], width=2, dash=(6, 5), smooth=True)
        canvas.create_line(*p_val, fill=line_color, width=4, smooth=True)
        if p_out:
            canvas.create_line(*p_out, fill=self.colors["amber"], width=2, smooth=True)
        canvas.create_oval(p_val[-2] - 5, p_val[-1] - 5, p_val[-2] + 5, p_val[-1] + 5, fill=line_color, outline="")
        canvas.create_rectangle(left, top, right, bottom, outline=self.colors["border"])

    def _draw_output(self, canvas: tk.Canvas, times, outputs) -> None:
        canvas.delete("all")
        w = max(canvas.winfo_width(), 300)
        h = max(canvas.winfo_height(), 120)
        left, top, right, bottom = 54, 26, w - 18, h - 28
        canvas.create_text(left, 10, text="STELLWERTVERLAUF", fill=self.colors["muted"], font=("Consolas", 12), anchor="w")
        for i in range(5):
            y = top + ((bottom - top) / 4) * i
            canvas.create_line(left, y, right, y, fill=self.colors["grid"])
        if len(outputs) < 2:
            canvas.create_rectangle(left, top, right, bottom, outline=self.colors["border"])
            return
        t0 = times[0]
        tspan = max(self.sample_time, times[-1] - t0)
        pts, fill = [], [left, bottom]
        for t, out in zip(times, outputs):
            x = left + ((t - t0) / tspan) * (right - left)
            y = bottom - (max(0.0, min(100.0, out)) / 100.0) * (bottom - top)
            pts.extend([x, y]); fill.extend([x, y])
        fill.extend([right, bottom])
        canvas.create_polygon(*fill, fill="#10263b", outline="", smooth=True)
        canvas.create_line(*pts, fill=self.colors["amber"], width=3, smooth=True)
        canvas.create_oval(pts[-2] - 5, pts[-1] - 5, pts[-2] + 5, pts[-1] + 5, fill=self.colors["amber"], outline="")
        canvas.create_rectangle(left, top, right, bottom, outline=self.colors["border"])

    def _preview_changed(self) -> None:
        self._reset_preview()

    def _reset_preview(self) -> None:
        self.preview_elapsed = 0.0
        self.preview_t.clear(); self.preview_temp.clear(); self.preview_sp.clear(); self.preview_out.clear()
        self.preview_plant = FirstOrderPlant()
        self.preview_controller = InjectionMachinePidController(sensor=self.preview_plant, actuator=self.preview_plant, config=PidConfig(kp=self.pid_kp.get(), ki=self.pid_ki.get(), kd=self.pid_kd.get(), setpoint=self.pid_sp.get(), sample_time=self.preview_sample_time, output_limits=(0.0, 100.0), starting_output=0.0))

    def _tick_preview(self) -> None:
        if self.preview_controller is None or self.preview_plant is None:
            return
        telemetry = self.preview_controller.update_once()
        self.preview_plant.step(self.preview_sample_time)
        self.preview_elapsed += self.preview_sample_time
        self.preview_t.append(self.preview_elapsed)
        self.preview_temp.append(telemetry.process_value)
        self.preview_sp.append(telemetry.setpoint)
        self.preview_out.append(telemetry.control_output)

    def _apply_preview_to_live(self) -> None:
        cfg = self.controller.config
        cfg.kp = self.pid_kp.get(); cfg.ki = self.pid_ki.get(); cfg.kd = self.pid_kd.get(); cfg.setpoint = self.pid_sp.get()
        self.controller = InjectionMachinePidController(sensor=self.plant, actuator=self.plant, config=cfg)
        self.controller.set_setpoint(cfg.setpoint)
        self.status.set("PID-Werte aus PID-Labor uebernommen")

    def _rebuild_profile_buttons(self) -> None:
        for child in self.profile_row.winfo_children():
            child.destroy()
        self.profile_buttons.clear()
        for profile in self.profiles:
            b = tk.Button(self.profile_row, text=profile.name, command=lambda p=profile: self._apply_profile(p, update_form=True), bg=self.colors["alt"], fg=self.colors["text"], activebackground=self.colors["orange"], activeforeground=self.colors["bg"], relief="flat", bd=0, font=("Consolas", 13), padx=16, pady=12)
            b.pack(side="left", padx=(0, 8))
            self.profile_buttons[profile.name] = b
        self._mark_profile(self.active_profile)

    def _rebuild_profile_list(self) -> None:
        for child in self.profile_list.winfo_children():
            child.destroy()
        for profile in self.profiles:
            row = tk.Frame(self.profile_list, bg=self.colors["alt"], highlightthickness=1, highlightbackground=self.colors["border"])
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=profile.name, bg=self.colors["alt"], fg=self.colors["orange"], font=("Consolas", 13, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
            tk.Label(row, text=f"Soll {profile.setpoint:.0f}C   Kp {profile.kp:.2f}   Ki {profile.ki:.2f}   Kd {profile.kd:.2f}", bg=self.colors["alt"], fg=self.colors["text"], font=("Consolas", 11)).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))
            tk.Button(row, text="LADEN", command=lambda p=profile: self._load_profile(p), bg=self.colors["panel"], fg=self.colors["text"], activebackground=self.colors["orange"], activeforeground=self.colors["bg"], relief="flat", bd=0, font=("Consolas", 11, "bold"), padx=12, pady=8).grid(row=0, column=1, rowspan=2, padx=12)
            row.grid_columnconfigure(0, weight=1)

    def _mark_profile(self, name: str) -> None:
        self.active_profile = name
        for key, button in self.profile_buttons.items():
            button.config(bg=self.colors["panel"] if key == name else self.colors["alt"], fg=self.colors["orange"] if key == name else self.colors["text"])

    def _load_profile(self, profile: Profile) -> None:
        self.form_name.set(profile.name)
        self.form_sp.set(profile.setpoint)
        self.form_kp.set(profile.kp)
        self.form_ki.set(profile.ki)
        self.form_kd.set(profile.kd)
        self.status.set(f"Profil {profile.name} geladen")

    def _save_profile(self) -> None:
        name = self.form_name.get().strip() or "NEUES MATERIAL"
        current = next((p for p in self.profiles if p.name == name), None)
        if current is None:
            self.profiles.append(Profile(name, self.form_sp.get(), self.form_kp.get(), self.form_ki.get(), self.form_kd.get()))
        else:
            current.setpoint = self.form_sp.get(); current.kp = self.form_kp.get(); current.ki = self.form_ki.get(); current.kd = self.form_kd.get()
        self._rebuild_profile_buttons()
        self._rebuild_profile_list()
        self.status.set(f"Profil {name} gespeichert")

    def _apply_form_profile(self) -> None:
        self._apply_profile(Profile(self.form_name.get().strip() or "NEUES MATERIAL", self.form_sp.get(), self.form_kp.get(), self.form_ki.get(), self.form_kd.get()), update_form=False)

    def _apply_profile(self, profile: Profile, update_form: bool) -> None:
        cfg = self.controller.config
        cfg.kp = profile.kp; cfg.ki = profile.ki; cfg.kd = profile.kd; cfg.setpoint = profile.setpoint
        self.controller = InjectionMachinePidController(sensor=self.plant, actuator=self.plant, config=cfg)
        self.controller.set_setpoint(profile.setpoint)
        self.pid_kp.set(profile.kp); self.pid_ki.set(profile.ki); self.pid_kd.set(profile.kd); self.pid_sp.set(profile.setpoint)
        self.profile_label.set(profile.name)
        self.active_profile = profile.name
        self._mark_profile(profile.name)
        if update_form:
            self._load_profile(profile)
        self._reset_preview()
        self.status.set(f"Profil {profile.name} aktiv")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
