#!/usr/bin/env python3
"""Liður 1B: Mæla jafnvægishitastig við 20%, 50% og 80% duty cycle.

Hitagjafinn er í gangi allan tímann. Viftan er stillt á hvert duty cycle í
röð og hitastigið skráð á T = 1 s fresti.

Hvenær er jafnvægi náð? (rökstuðningur fyrir skýrslu)
  Hallatala bestu línu (minnstu kvaðröt) gegnum mælingar síðustu WINDOW sek
  er reiknuð á hverri sekúndu. Jafnvægi telst náð þegar |hallatala| er minni
  en SLOPE_THR [°C/mín] samfellt í HOLD sek (og a.m.k. MIN_TIME sek liðnar).
  Jafnvægishitastigið er þá meðaltal síðustu WINDOW sek. identify.py ber
  þetta einnig saman við veldisfallsnálgun (fyrstu gráðu líkan) sem spáir
  fyrir um lokagildið.

Þrepin 20% -> 50% -> 80% eru jafnframt þrepasvaranir sem identify.py notar til
að meta yfirfærslufall kerfisins (K, tau, theta).

Keyrsla:   python3 step1_equilibrium.py          (á Raspberry Pi)
           python3 step1_equilibrium.py --sim    (hermir)
"""
import argparse
import csv
import json
import os

import config
from hardware import make_hardware


def slope_per_min(ts, ys):
    n = len(ts)
    mt, my = sum(ts) / n, sum(ys) / n
    sxx = sum((t - mt) ** 2 for t in ts)
    sxy = sum((t - mt) * (y - my) for t, y in zip(ts, ys))
    return 60.0 * sxy / sxx if sxx > 0 else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true", help="nota hermi í stað vélbúnaðar")
    ap.add_argument("--levels", type=float, nargs="+", default=[20, 50, 80])
    ap.add_argument("--min-time", type=float, default=300, help="lágmarkstími á hverju þrepi [s]")
    ap.add_argument("--max-time", type=float, default=1500, help="hámarkstími á hverju þrepi [s]")
    ap.add_argument("--window", type=float, default=120, help="gluggi fyrir hallatölu [s]")
    ap.add_argument("--slope", type=float, default=0.1, help="þröskuldur á hallatölu [°C/mín]")
    ap.add_argument("--hold", type=float, default=60, help="hve lengi skilyrði þarf að halda [s]")
    ap.add_argument("--out", default=os.path.join(config.DATA_DIR, "step1_equilibrium.csv"))
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    hw = make_hardware(args.sim)
    meta = {"levels": [], "args": vars(args)}
    try:
        hw.fan_power(True)
        hw.set_fan(args.levels[0])
        hw.heater(True)
        print("Hitagjafi KVEIKTUR, vifta KVEIKT. Ýtið á Ctrl+C til að stöðva.")
        with open(args.out, "w", newline="") as fp:
            w = csv.writer(fp)
            w.writerow(["t", "duty", "temp"])
            t_next = hw.now()
            for duty in args.levels:
                hw.set_fan(duty)
                t_start = hw.now()
                print("\n=== Duty cycle %.0f%% (byrjar t=%.0f s) ===" % (duty, t_start))
                ts, ys = [], []
                ok_since = None
                reason = "max_time"
                while True:
                    t_next += config.TS
                    hw.sleep_until(t_next)
                    y = hw.read_temp()
                    t = hw.now()
                    w.writerow(["%.2f" % t, "%.1f" % duty, "%.4f" % y])
                    fp.flush()
                    ts.append(t)
                    ys.append(y)
                    el = t - t_start
                    while ts and ts[0] < t - args.window:
                        ts.pop(0)
                        ys.pop(0)
                    sl = slope_per_min(ts, ys) if el > args.window else float("nan")
                    if int(el) % 10 == 0:
                        print("t=%7.1f s  duty=%5.1f%%  T=%7.3f °C  halli=%+.3f °C/mín"
                              % (el, duty, y, sl))
                    if el >= args.min_time and abs(sl) < args.slope:
                        ok_since = ok_since if ok_since is not None else t
                        if t - ok_since >= args.hold:
                            reason = "slope"
                            break
                    else:
                        ok_since = None
                    if el >= args.max_time:
                        break
                t_eq = sum(ys) / len(ys)
                rpm = hw.read_rpm(2.0)
                t_next = hw.now()
                print(">>> Jafnvægi (%s): T_eq = %.2f °C við %.0f%%, vifta %.0f rpm"
                      % ("hallatala < %.2f °C/mín" % args.slope if reason == "slope" else "hámarkstími",
                         t_eq, duty, rpm))
                meta["levels"].append(dict(duty=duty, t_start=t_start, t_end=t,
                                           T_eq_tail=t_eq, rpm=rpm, stop=reason))
    except KeyboardInterrupt:
        print("\nStöðvað af notanda.")
    finally:
        hw.close()
        with open(os.path.splitext(args.out)[0] + "_meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        print("Gögn vistuð í %s" % args.out)


if __name__ == "__main__":
    main()
