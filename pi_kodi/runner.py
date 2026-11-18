"""Sameiginleg reglunarlykkja fyrir liði 1-3.

Lykkjan (á T = 1 s fresti):
  1. lesa hitastig y (DS18B20)
  2. (liður 3) bæta sínustruflun við: y_m = y + A sin(2 pi t / P)
  3. reikna óskgildi r(t) út frá óskgildisferli
  4. reikna stýrimerki u = stýring(r, y_m)
  5. stilla duty cycle viftu = u
  6. skrá gildin í CSV skrá og prenta í skipanaglugga

Á undan sjálfri keyrslunni er aðlögunartími ("settle") þar sem stýringin er
virk við upphafsóskgildið þar til hitastigið hefur verið innan --tol í
--settle-hold sek (eða --settle-max er liðinn). Tíminn t = 0 er byrjun
keyrslunnar sjálfrar.
"""
import argparse
import csv
import json
import math
import os

import config
from design import build_controller, load_model, u_static
from hardware import make_hardware


class Profile:
    """Óskgildisferill úr bútum: ("hold", T, sek) eða ("ramp", T_end, sek)."""

    def __init__(self, r0, segments):
        self.r0 = r0
        self.segs = []
        t, r = 0.0, r0
        for kind, target, dur in segments:
            r_end = r if kind == "hold" else target
            self.segs.append((t, t + dur, r, r_end))
            t, r = t + dur, r_end
        self.duration = t

    def r(self, t):
        if t <= 0:
            return self.r0
        for t0, t1, a, b in self.segs:
            if t0 <= t < t1:
                return a + (b - a) * (t - t0) / (t1 - t0)
        return self.segs[-1][3]

    def rdot(self, t):
        for t0, t1, a, b in self.segs:
            if t0 <= t < t1:
                return (b - a) / (t1 - t0)
        return 0.0


def profile_for(part, model):
    T20, T50, T80 = model["T20"], model["T50"], model["T80"]
    if part == 1:
        return Profile(T50, [("hold", None, 240)])
    return Profile(T50, [("hold", None, 180),
                         ("ramp", T20, 120),
                         ("hold", None, 180),
                         ("ramp", T80, 120),
                         ("hold", None, 180)])


def main(part):
    ap = argparse.ArgumentParser(description="Liður %d" % part)
    ap.add_argument("version", choices=["v1", "v2"], help="v1 = upprunaleg, v2 = endurbætt stýring")
    ap.add_argument("--sim", action="store_true", help="nota hermi")
    ap.add_argument("--speed", type=float, default=0.0, help="hermir: hraði miðað við rauntíma (0 = ótakmarkað)")
    ap.add_argument("--settle-max", type=float, default=300, help="hámarks aðlögunartími [s]")
    ap.add_argument("--settle-hold", type=float, default=30, help="tími innan tol áður en keyrsla hefst [s]")
    ap.add_argument("--tol", type=float, default=0.3, help="vikmörk aðlögunar [°C]")
    ap.add_argument("--model", default=config.MODEL_FILE)
    ap.add_argument("--quiet", action="store_true", help="prenta aðeins á 10 s fresti")
    args = ap.parse_args()

    model = load_model(args.model)
    profile = profile_for(part, model)
    noise_amp = model["noise_amp"] if part == 3 else 0.0
    noise_period = 8.0
    ctrl = build_controller(part, args.version, model, noise_period=noise_period)
    out = os.path.join(config.DATA_DIR, "part%d_%s.csv" % (part, args.version))
    os.makedirs(config.DATA_DIR, exist_ok=True)

    print("=" * 72)
    print("Liður %d, útgáfa %s: %s" % (part, args.version, ctrl.description))
    dz = ctrl.design
    print("Líkan: K=%.4f °C/%%, tau=%.1f s, theta=%.1f s (virkt %.1f s)"
          % (dz["K"], dz["tau"], dz["theta"], dz["theta_eff"]))
    print("Stillistuðlar: Kc=%.3f %%/°C, Ti=%.1f s, tc=%.1f s, preview=%.1f s"
          % (dz["kc"], dz["ti"], dz["tc"], ctrl.preview))
    print("Óskgildi: T50=%.2f  T20=%.2f  T80=%.2f °C, lengd %.0f s"
          % (model["T50"], model["T20"], model["T80"], profile.duration))
    if noise_amp:
        print("Truflun á mælingu: %.3f °C * sin(2 pi t / %.0f s)" % (noise_amp, noise_period))
    print("Skrifa í %s" % out)
    print("=" * 72)

    hw = make_hardware(args.sim, args.speed)
    try:
        with open(out, "w", newline="") as fp:
            w = csv.writer(fp)
            w.writerow(["t_abs", "t", "phase", "r", "y", "y_meas", "y_filt", "u", "u_ff", "p", "i", "kc", "ti"])
            hw.fan_power(True)
            r0 = profile.r(0)
            u0 = u_static(model, r0)
            hw.set_fan(u0)
            hw.heater(True)
            print("Hitagjafi og vifta KVEIKT. Upphafs duty cycle %.1f%%" % u0)

            y = hw.read_temp()
            ctrl.reset(y, r0, u0)
            t_prog0 = hw.now()
            t_run0 = None           # sett þegar aðlögun lýkur
            in_tol_since = None
            t_prev = hw.now()
            t_next = t_prev
            k = 0
            while True:
                t_next += config.TS
                hw.sleep_until(t_next)
                y = hw.read_temp()
                now = hw.now()
                dt = now - t_prev
                t_prev = now
                t_abs = now - t_prog0

                if t_run0 is None:
                    phase, t = "settle", 0.0
                else:
                    phase, t = "run", now - t_run0
                    if t > profile.duration:
                        break

                noise = noise_amp * math.sin(2 * math.pi * t_abs / noise_period)
                y_m = y + noise
                r = profile.r(t)
                tp = t + ctrl.preview if phase == "run" else 0.0
                u, info = ctrl.update(r, y_m, dt, r_ff=profile.r(tp), rdot_ff=profile.rdot(tp) if phase == "run" else 0.0)
                hw.set_fan(u)

                w.writerow(["%.2f" % t_abs, "%.2f" % t if phase == "run" else "", phase,
                            "%.4f" % r, "%.4f" % y, "%.4f" % y_m, "%.4f" % info["y_f"],
                            "%.3f" % u, "%.3f" % info["u_ff"], "%.3f" % info["p"],
                            "%.3f" % info["i"], "%.4f" % info["kc"], "%.2f" % info["ti"]])
                fp.flush()

                if not args.quiet or k % 10 == 0:
                    tag = "AÐLÖGUN" if phase == "settle" else "KEYRSLA"
                    tt = t_abs if phase == "settle" else t
                    print("[%s] t=%6.1f s  r=%6.2f  y=%6.2f  y_m=%6.2f  e=%+5.2f °C  u=%5.1f%%  (ff=%5.1f)"
                          % (tag, tt, r, y, y_m, r - y, u, info["u_ff"]))
                k += 1

                if phase == "settle":
                    if abs(r - y) < args.tol:
                        in_tol_since = in_tol_since if in_tol_since is not None else now
                    else:
                        in_tol_since = None
                    held = in_tol_since is not None and now - in_tol_since >= args.settle_hold
                    if held or t_abs >= args.settle_max:
                        t_run0 = now
                        print(">>> Aðlögun lokið eftir %.0f s (%s). Keyrsla hefst, t = 0."
                              % (t_abs, "innan vikmarka" if held else "hámarkstími"))
        print("Keyrslu lokið. Gögn í %s" % out)
    except KeyboardInterrupt:
        print("\nStöðvað af notanda.")
    finally:
        hw.close()
    with open(os.path.splitext(out)[0] + "_design.json", "w") as f:
        json.dump(dict(part=part, version=args.version, description=ctrl.description,
                       preview=ctrl.preview, **ctrl.design), f, indent=2)

