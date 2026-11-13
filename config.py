"""Stillingar fyrir hitastýringuna (IÐN303G hönnunarverkefni).

Pinnanúmer koma úr sýnidæmum kennara (BCM númerun):
  PWM_demo.py         -> FAN_PWM_PIN = 20, 25 kHz
  hall_sensor_demo.py -> TACH_PIN = 21
  RELAY_demo.py       -> RELAY_FAN_PIN = 26, RELAY_HEATER_PIN = 16 (LOW = kveikt)
"""

# --- Vélbúnaður -------------------------------------------------------------
FAN_PWM_PIN = 20          # PWM merki til viftu
FAN_PWM_FREQ = 25000      # [Hz] 25 kHz eins og Intel 4-pin PWM staðallinn
TACH_PIN = 21             # Hall-nemi í viftu (2 púlsar á hring)
RELAY_FAN_PIN = 26        # Segulrofi fyrir viftu
RELAY_HEATER_PIN = 16     # Segulrofi fyrir hitaelement
RELAY_ACTIVE_LOW = True   # Segulrofinn kveikir þegar pinni er LOW

# DS18B20 hitanemi (1-Wire). None = finna sjálfkrafa fyrsta 28-* tækið.
W1_DEVICE_ID = None
W1_BASE_DIR = "/sys/bus/w1/devices"

# --- Reglun -----------------------------------------------------------------
TS = 1.0                  # [s] söfnunartími T (DS18B20 þarf ~0.75 s fyrir 12 bita mælingu)
DUTY_MIN = 0.0            # [%]
DUTY_MAX = 100.0          # [%]

# --- Öryggi -----------------------------------------------------------------
T_MAX_SAFE = 90.0         # [°C] slökkt á hitagjafa ef mæling fer yfir þetta
COOLDOWN_S = 60.0         # [s] vifta keyrir á 100% í lok keyrslu til að kæla

# --- Skrár ------------------------------------------------------------------
# Með --sim fara öll gögn í sér möppur svo hermigögn skrifi aldrei yfir
# raunverulegar mælingar.
import sys as _sys
SIM = "--sim" in _sys.argv
DATA_DIR = "data_sim" if SIM else "data"
FIG_DIR = "figures_sim" if SIM else "figures"
MODEL_FILE = DATA_DIR + "/model.json"
