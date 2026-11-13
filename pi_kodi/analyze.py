#!/usr/bin/env python3
"""Mat á frammistöðu og gröf fyrir liði 1-3 (upprunaleg v1 vs. endurbætt v2).

Mælikvarðar (rökstuðningur: hönnunarkröfurnar eru hraði, skekkja í jafnvægi,
næmni fyrir truflunum/breytileika og stýrimerki):

  Skekkja (heild):      IAE = sum |e| dt,  RMS(e),  max |e|
  Skekkja í jafnvægi:   meðaltal e síðustu 60 s hvers fasta bútar
  Hraði:                aðlögunartími eftir ramp (tími þar til |e| < BAND til enda bútar)
                        og meðalskekkja (eftirdragi) í rampi
  Yfirskot:             mesta frávik handan óskgildis eftir ramp
  Stýrimerki:           heildarbreytileiki TV = sum |du| og staðalfrávik du
                        (mikið TV = slit á viftu og næmni fyrir suði)

e = r - y er reiknað með RAUNVERULEGU mælda hitastiginu y (án viðbættrar
truflunar í lið 3), því markmiðið er að raunhitinn fylgi óskgildinu.

Keyrsla:  python3 analyze.py          (öll gögn sem eru til í data/)
          python3 analyze.py --sim    (gögn úr hermi, data_sim/)
"""
import csv
import os

import numpy as np

import config

BAND = 0.5  # [°C] vikmörk fyrir aðlögunartíma


def load(path):
    with open(path) as f:
        rows = [r for r in csv.DictReader(f) if r["phase"] == "run"]
    keys = ["t", "r", "y", "y_meas", "y_filt", "u", "u_ff"]
    return {k: np.array([float(r[k]) for r in rows]) for k in keys}


def segments(part, d):
    """Skilar lista (tegund, t0, t1) samkvæmt óskgildisferlinum."""
    if part == 1:
        return [("hold", 0, 240)]
    return [("hold", 0, 180), ("ramp", 180, 300), ("hold", 300, 480),
            ("ramp", 480, 600), ("hold", 600, 780)]


def metrics(part, d):
    t, r, y, u = d["t"], d["r"], d["y"], d["u"]
    e = r - y
    dt = np.diff(t, prepend=t[0])
    m = {
        "IAE [°C·s]": float(np.sum(np.abs(e) * dt)),
        "RMS e [°C]": float(np.sqrt(np.mean(e ** 2))),
        "max |e| [°C]": float(np.max(np.abs(e))),
        "TV(u) [%]": float(np.sum(np.abs(np.diff(u)))),
        "std(du) [%]": float(np.std(np.diff(u))),
        "mean u [%]": float(np.mean(u)),
    }
    segs = segments(part, d)
    for i, (kind, t0, t1) in enumerate(segs):
        sel = (t >= t0) & (t < t1)
        if not sel.any():
            continue
        label = "%s%d" % ("H" if kind == "hold" else "R", i + 1)
        if kind == "hold":
            tail = sel & (t >= t1 - 60)
            m["e_ss %s [°C]" % label] = float(np.mean(e[tail]))
            if part > 1 and i > 0:
                ts = settling_time(t[sel] - t0, e[sel])
                m["t_s %s [s]" % label] = ts
                # yfirskot í stefnu síðasta ramps
                direction = np.sign(r[sel][0] - segs_r_start(d, segs[i - 1]))
                os_ = np.max(direction * (y[sel] - r[sel]))
                m["yfirskot %s [°C]" % label] = float(max(os_, 0.0))
        else:
            m["meðal e %s [°C]" % label] = float(np.mean(e[sel]))
    if part == 1:
        m["t_s [s]"] = settling_time(t, e)
    return m


def segs_r_start(d, seg):
    _, t0, _ = seg
    i = np.searchsorted(d["t"], t0)
    return d["r"][min(i, len(d["r"]) - 1)]


def settling_time(t, e):
    out = np.nonzero(np.abs(e) >= BAND)[0]
    if len(out) == 0:
        return 0.0
    if out[-1] == len(e) - 1:
        return float("nan")  # náði aldrei innan vikmarka
    return float(t[out[-1] + 1])


def plot(part, runs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    titles = {1: "Liður 1: fast óskgildi",
              2: "Liður 2: breytingar í óskgildi",
              3: "Liður 3: breytingar í óskgildi með truflun á mælingu"}
    colors = {"v1": "tab:red", "v2": "tab:blue"}
    names = {"v1": "Upprunaleg (v1)", "v2": "Endurbætt (v2)"}
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1.3]})
    ref = next(iter(runs.values()))
    ax.plot(ref["t"], ref["r"], "k--", lw=1.5, label="Óskgildi r(t)")
    for v, d in runs.items():
        if part == 3:
            ax.plot(d["t"], d["y_meas"], color=colors[v], lw=0.6, alpha=0.3,
                    label="%s: mæling + truflun" % names[v])
        ax.plot(d["t"], d["y"], color=colors[v], lw=1.6, label="%s: mælt hitastig" % names[v])
        ax2.plot(d["t"], d["u"], color=colors[v], lw=1.0, label=names[v])
    ax.set_ylabel("Hitastig [°C]")
    ax.set_title(titles[part])
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)
    ax2.set_ylabel("Duty cycle [%]")
    ax2.set_xlabel("Tími [s]")
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8)
    fig.tight_layout()
    os.makedirs(config.FIG_DIR, exist_ok=True)
    p = os.path.join(config.FIG_DIR, "part%d.png" % part)
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true", help="nota gögn úr data_sim/")
    ap.parse_args()
    all_rows = []
    for part in (1, 2, 3):
        runs = {}
        for v in ("v1", "v2"):
            p = os.path.join(config.DATA_DIR, "part%d_%s.csv" % (part, v))
            if os.path.exists(p):
                runs[v] = load(p)
        if not runs:
            continue
        ms = {v: metrics(part, d) for v, d in runs.items()}
        keys = list(next(iter(ms.values())).keys())
        print("\n### Liður %d\n" % part)
        hdr = "| Mælikvarði | " + " | ".join(runs) + (" | Breyting |" if len(runs) == 2 else " |")
        print(hdr)
        print("|" + "---|" * (hdr.count("|") - 1))
        for k in keys:
            vals = [ms[v].get(k, float("nan")) for v in runs]
            line = "| %s | " % k + " | ".join("%.3f" % x for x in vals)
            # breyting reiknuð á tölugildum (minna = betra fyrir alla skekkjumælikvarða)
            a0, a1 = (abs(x) for x in vals) if len(vals) == 2 else (0, 0)
            if k.startswith("mean u"):
                line += " | -"
            elif len(vals) == 2 and np.isfinite(a0) and np.isfinite(a1) and a0 > 1e-3:
                line += " | %+.0f%%" % (100 * (a1 - a0) / a0)
            elif len(vals) == 2:
                line += " | -"
            print(line + " |")
            all_rows.append([part, k] + vals)
        print("\nGraf: %s" % plot(part, runs))
    if all_rows:
        p = os.path.join(config.DATA_DIR, "metrics.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["lidur", "maelikvardi", "v1", "v2"])
            w.writerows(all_rows)
        print("\nMælikvarðar vistaðir í %s" % p)
    else:
        print("Engin gögn fundust í %s/" % config.DATA_DIR)


if __name__ == "__main__":
    main()
