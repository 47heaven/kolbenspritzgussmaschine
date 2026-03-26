class SimplePidLoop:
    """Tiny PID implementation suitable for MicroPython.

    TODO: Validate tuning on the real heater, thermal mass and sensor placement.
    """

    def __init__(self, kp: float, ki: float, kd: float, sample_time_s: float, output_min: float = 0.0, output_max: float = 100.0) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.sample_time_s = sample_time_s
        self.output_min = output_min
        self.output_max = output_max
        self.setpoint = 0.0
        self._integral = 0.0
        self._last_measurement = None

    def reset(self) -> None:
        self._integral = 0.0
        self._last_measurement = None

    def update_parameters(self, kp: float, ki: float, kd: float, setpoint: float) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.reset()

    def compute(self, measurement: float) -> float:
        error = self.setpoint - measurement
        proportional = self.kp * error
        self._integral += error * self.sample_time_s * self.ki
        self._integral = max(self.output_min, min(self.output_max, self._integral))
        derivative = 0.0
        if self._last_measurement is not None:
            derivative = -self.kd * ((measurement - self._last_measurement) / self.sample_time_s)
        self._last_measurement = measurement
        output = proportional + self._integral + derivative
        return max(self.output_min, min(self.output_max, output))
