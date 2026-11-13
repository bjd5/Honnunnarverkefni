#!/usr/bin/env python3
"""Kortleggja svörun viftunnar: snúningshraði [rpm] sem fall af duty cycle.

Hitagjafinn er SLÖKKTUR allan tímann. Fyrir hvert duty cycle er beðið í
--wait sek svo hraðinn nái jafnvægi, svo talið í 2 s með Hall-nemanum.
Tekur u.þ.b. 11 x (wait + 2) sek, sjálfgefið ~1,5 mín.

Keyrsla:  python3 fan_test.py
          python3 fan_test.py --freq 100        (prófa aðra PWM tíðni)
          python3 fan_test.py --sim
"""
import argparse
import csv
import os

import config
from hardware import make_hardware


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--wait", type=float, default=6.0, help="biðtími á hverju þrepi [s]")
    ap.add_argument("--freq", type=float, default=None,
                    help="PWM tíðni [Hz] (sjálfgefið úr config.py)")
    ap.add_argument("--levels", type=float, nargs="+",
                    default=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    args = ap.parse_args()

    if args.freq:
        config.FAN_PWM_FREQ = args.freq
    os.makedirs(config.DATA_DIR, exist_ok=True)
    out = os.path.join(config.DATA_DIR, "fan_test_%gHz.csv" % config.FAN_PWM_FREQ)
    hw = make_hardware(args.sim)
    try:
        hw.heater(False)
        hw.fan_power(True)
        print("Hitagjafi SLÖKKTUR. Mæli snúningshraða viftu, PWM tíðni %g Hz." % config.FAN_PWM_FREQ)
        print(" duty [%]   rpm")
        with open(out, "w", newline="") as fp:
            w = csv.writer(fp)
            w.writerow(["duty", "rpm"])
            for d in args.levels:
                hw.set_fan(d)
                hw.sleep_until(hw.now() + args.wait)
                rpm = hw.read_rpm(2.0)
                print("  %5.0f   %6.0f" % (d, rpm))
                w.writerow([d, "%.1f" % rpm])
                fp.flush()
        print("Vistað í %s" % out)
    except KeyboardInterrupt:
        print("\nStöðvað.")
    finally:
        hw.close(cooldown=0)


if __name__ == "__main__":
    main()
