"""Tenging við vélbúnað (Raspberry Pi) og hermir með sama viðmóti.

Bæði Hardware og SimHardware bjóða upp á:
    now()                 -> tími [s] frá því að hluturinn var búinn til
    sleep_until(t)        -> bíða þar til now() >= t
    read_temp()           -> hitastig [°C] frá DS18B20
    set_fan(duty)         -> duty cycle viftu [%]
    fan_power(on), heater(on)
    read_rpm(sec)         -> snúningshraði viftu [rpm] (Hall-nemi)
    close()               -> slökkva á hitagjafa, kæla og hreinsa GPIO

Hermirinn gerir mögulegt að prófa allan kóðann (auðkenning, stýringar,
greining) án þess að vera tengdur við búnaðinn: python run_part1.py --sim
"""
import glob
import math
import os
import random
import time
from collections import deque

import config


class OverTemperature(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Raunverulegur búnaður
# ---------------------------------------------------------------------------
class Hardware:
    def __init__(self):
        import RPi.GPIO as GPIO  # aðeins til á Raspberry Pi
        self.GPIO = GPIO
        self._t0 = time.monotonic()
        self._duty = 0.0

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        off = self._relay_level(False)
        GPIO.setup(config.RELAY_FAN_PIN, GPIO.OUT, initial=off)
        GPIO.setup(config.RELAY_HEATER_PIN, GPIO.OUT, initial=off)
        GPIO.setup(config.FAN_PWM_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(config.TACH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self._pwm = GPIO.PWM(config.FAN_PWM_PIN, config.FAN_PWM_FREQ)
        self._pwm.start(0)
        self._sensor_file = self._find_sensor()

    # -- hjálparföll --------------------------------------------------------
    def _relay_level(self, on):
        G = self.GPIO
        if config.RELAY_ACTIVE_LOW:
            return G.LOW if on else G.HIGH
        return G.HIGH if on else G.LOW

    @staticmethod
    def _find_sensor():
        if config.W1_DEVICE_ID:
            path = os.path.join(config.W1_BASE_DIR, config.W1_DEVICE_ID, "w1_slave")
        else:
            found = sorted(glob.glob(os.path.join(config.W1_BASE_DIR, "28-*", "w1_slave")))
            if not found:
                raise RuntimeError(
                    "Fann engan DS18B20 nema í %s. Er 1-Wire virkt (dtoverlay=w1-gpio)?"
                    % config.W1_BASE_DIR)
            path = found[0]
        print("DS18B20 nemi: %s" % path)
        return path

    # -- viðmót ---------------------------------------------------------------
    def now(self):
        return time.monotonic() - self._t0

    def sleep_until(self, t):
        dt = t - self.now()
        if dt > 0:
            time.sleep(dt)

    def read_temp(self, retries=5):
        """Les DS18B20 (tekur ~0.75 s). Hafnar CRC villum og 85.000 ræsigildi."""
        for _ in range(retries):
            with open(self._sensor_file) as f:
                lines = f.read().strip().splitlines()
            if len(lines) == 2 and lines[0].endswith("YES") and "t=" in lines[1]:
                temp = int(lines[1].split("t=")[1]) / 1000.0
                if temp != 85.0:
                    if temp > config.T_MAX_SAFE:
                        self.heater(False)
                        raise OverTemperature("Hitastig %.1f °C > %.1f °C" % (temp, config.T_MAX_SAFE))
                    return temp
            time.sleep(0.1)
        raise RuntimeError("Gat ekki lesið DS18B20")

    def set_fan(self, duty):
        duty = min(max(float(duty), 0.0), 100.0)
        self._duty = duty
        self._pwm.ChangeDutyCycle(duty)

    def fan_power(self, on):
        self.GPIO.output(config.RELAY_FAN_PIN, self._relay_level(on))

    def heater(self, on):
        self.GPIO.output(config.RELAY_HEATER_PIN, self._relay_level(on))

    def read_rpm(self, sec=2.0):
        """Telur breytingar á Hall-merki í sec sekúndur (sama og hall_sensor_demo.py)."""
        G = self.GPIO
        end = time.monotonic() + sec
        last, count = None, 0
        while time.monotonic() < end:
            s = G.input(config.TACH_PIN)
            if s != last:
                if last is not None:
                    count += 1
                last = s
        # 2 breytingar á púls, 2 púlsar á hring
        return count / sec / 2 / 2 * 60

    def close(self, cooldown=config.COOLDOWN_S):
        G = self.GPIO
        try:
            self.heater(False)
            print("Slökkt á hitagjafa.")
            if cooldown > 0:
                self.set_fan(100)
                print("Kæli með viftu á 100%% í allt að %.0f s (Ctrl+C til að sleppa)..." % cooldown)
                try:
                    end = self.now() + cooldown
                    while self.now() < end:
                        if self.read_temp() < 35.0:
                            break
                except KeyboardInterrupt:
                    pass
            self.set_fan(0)
            self.fan_power(False)
            self._pwm.stop()
        finally:
            G.cleanup()
            print("GPIO hreinsað.")


# ---------------------------------------------------------------------------
# Hermir
# ---------------------------------------------------------------------------
class SimHardware:
    """Einfalt líkan af kerfinu: fyrstu gráðu ólínulegt kerfi með dauðtíma.

        dT/dt = (T_eq(u(t - theta)) - T) / tau(u)
        T_eq(u) = T_amb + dT_heat / (1 + u/u0)     (vifta kælir minna og minna)

    Gildin eru ágiskun - aðeins til að prófa kóðann, EKKI til að hanna eftir.
    """

    def __init__(self, seed=1, t_amb=22.0, dT_heat=40.0, u0=25.0,
                 tau0=110.0, theta=4.0, noise=0.03, speed=0.0):
        self._rng = random.Random(seed)
        self.t = 0.0
        self.T = t_amb
        self.t_amb, self.dT_heat, self.u0 = t_amb, dT_heat, u0
        self.tau0, self.theta, self.noise = tau0, theta, noise
        self.speed = speed  # >0: hægja á (til sýnis), 0: eins hratt og hægt er
        self._duty = 0.0
        self._fan_on = False
        self._heater_on = False
        self._hist = deque([(0.0, 0.0)])  # (t, áhrifarík kæling) fyrir dauðtíma

    def _cooling(self):
        return self._duty if self._fan_on else 0.0

    def _teq(self, u):
        if not self._heater_on:
            return self.t_amb
        return self.t_amb + self.dT_heat / (1.0 + u / self.u0)

    def _step(self, dt):
        # finna u sem var í gildi fyrir theta sek
        t_del = self.t - self.theta
        while len(self._hist) > 1 and self._hist[1][0] <= t_del:
            self._hist.popleft()
        u = self._hist[0][1]
        tau = self.tau0 / (1.0 + u / 100.0)
        self.T += dt * (self._teq(u) - self.T) / tau
        self.t += dt

    def now(self):
        return self.t

    def sleep_until(self, t):
        start = self.t
        while self.t < t - 1e-9:
            self._step(min(0.1, t - self.t))
        if self.speed > 0:
            time.sleep((self.t - start) / self.speed)

    def read_temp(self):
        self.sleep_until(self.t + 0.75)  # umbreytingartími DS18B20
        y = self.T + self._rng.gauss(0, self.noise)
        y = round(y / 0.0625) * 0.0625      # 12 bita upplausn
        if y > config.T_MAX_SAFE:
            raise OverTemperature("Hitastig %.1f °C" % y)
        return y

    def _record(self):
        self._hist.append((self.t, self._cooling()))

    def set_fan(self, duty):
        self._duty = min(max(float(duty), 0.0), 100.0)
        self._record()

    def fan_power(self, on):
        self._fan_on = bool(on)
        self._record()

    def heater(self, on):
        self._heater_on = bool(on)

    def read_rpm(self, sec=2.0):
        self.sleep_until(self.t + sec)
        if not self._fan_on:
            return 0.0
        return 200 + 13.5 * self._duty + self._rng.gauss(0, 10)  # ~1550 rpm við 100%

    def close(self, cooldown=0):
        self._heater_on = False
        print("[hermir] Slökkt á hitagjafa.")


def make_hardware(sim=False, speed=0.0):
    if sim:
        print("*** HERMIR - enginn vélbúnaður notaður ***")
        return SimHardware(speed=speed)
    return Hardware()
