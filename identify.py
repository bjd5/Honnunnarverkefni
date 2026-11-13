#!/usr/bin/env python3
"""Meta yfirfærslufall kerfisins út frá þrepasvörun (liður 1A/1B).

Les data/step1_equilibrium.csv og býr til data/model.json + figures/step1.png.

1) Jafnvægishitastig hvers þreps:
   a) meðaltal síðustu WINDOW sek (ef hallatölu-skilyrði var uppfyllt)
   b) veldisfallsnálgun y(t) = a + b*exp(-t/tau) sem spáir fyrir um lokagildi a
   Ef þrepinu lauk á hámarkstíma (ekki í jafnvægi) er b) notað.

2) Yfirfærslufall út frá þrepasvörun (aðferð úr glærum "Meta yfirfærslufall út
   frá þrepasvörun"):
     K = dT / du          (breyting í hitastigi / hæð þreps)
     t_1/3, t_2/3         tímar þar sem svörunin hefur náð 1/3 og 2/3 af lokagildi
     Q = t_2/3 / t_1/3
   Fyrir G(s) = K e^{-theta s} / (T s + 1)^n gildir t = theta + T*x_n þar sem
   x_n er lausn (1/3, 2/3) á staðlaðri þrepasvörun. Fyrir n = 1:
     T = (t_2/3 - t_1/3)/ln 2,   theta = t_1/3 - T ln(3/2)
   Bæði n = 1 og n = 2 eru reiknuð; n = 1 (FOPDT) er notað við hönnun.
"""
import argparse
import csv
import json
import math
import os

import numpy as np

import config


def load_csv(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}


def smooth(y, n=5):
    if len(y) < n:
        return y
    k = np.ones(n) / n
    ys = np.convolve(y, k, mode="same")
    ys[: n // 2] = y[: n // 2]
    ys[-(n // 2):] = y[-(n // 2):]
    return ys


def exp_fit(t, y):
    """y = a + b*exp(-t/tau): grid-leit á tau, línuleg minnstu kvaðröt á a, b."""
    t = t - t[0]
    best = None
    for tau in np.geomspace(5, 5000, 400):
        A = np.column_stack([np.ones_like(t), np.exp(-t / tau)])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        err = np.sum((A @ coef - y) ** 2)
        if best is None or err < best[0]:
            best = (err, coef[0], coef[1], tau)
    _, a, b, tau = best
    return a, b, tau


def unit_step(n, x):
    """Stöðluð þrepasvörun 1/(s+1)^n."""
    x = np.maximum(x, 0)
    s = sum(x ** k / math.factorial(k) for k in range(n))
    return 1 - np.exp(-x) * s


def x_levels(n):
    xs = np.linspace(0, 20, 200001)
    ys = unit_step(n, xs)
    return xs[np.searchsorted(ys, 1 / 3)], xs[np.searchsorted(ys, 2 / 3)]


def crossing(t, y, level):
    idx = np.nonzero(y >= level)[0]
    if len(idx) == 0:
        return float("nan")
    i = idx[0]
    if i == 0:
        return t[0]
    return t[i - 1] + (level - y[i - 1]) * (t[i] - t[i - 1]) / (y[i] - y[i - 1])


def step_identify(t, y, y0, y_inf):
    """Skilar dict með n=1 og n=2 líkönum. t byrjar í 0 við þrepið."""
    yn = smooth((y - y0) / (y_inf - y0))
    t13, t23 = crossing(t, yn, 1 / 3), crossing(t, yn, 2 / 3)
    out = {"t13": t13, "t23": t23, "Q": t23 / t13 if t13 > 0 else float("nan")}
    for n in (1, 2):
        x1, x2 = x_levels(n)
        T = (t23 - t13) / (x2 - x1)
        theta = max(t13 - T * x1, 0.0)
        model = y0 + (y_inf - y0) * unit_step(n, (t - theta) / T)
        rms = float(np.sqrt(np.mean((model - y) ** 2)))
        out["n%d" % n] = {"T": T, "theta": theta, "rms": rms}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(config.DATA_DIR, "step1_equilibrium.csv"))
    ap.add_argument("--window", type=float, default=120)
    ap.add_argument("--sim", action="store_true", help="nota gögn úr data_sim/")
    ap.add_argument("--out", default=config.MODEL_FILE)
    args = ap.parse_args()

    d = load_csv(args.data)
    meta_path = os.path.splitext(args.data)[0] + "_meta.json"
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {"levels": []}
    stops = {lv["duty"]: lv["stop"] for lv in meta.get("levels", [])}

    duties = []
    for u in d["duty"]:
        if not duties or duties[-1] != u:
            duties.append(float(u))

    levels, segs = [], []
    print("=== Jafnvægishitastig ===")
    for u in duties:
        m = d["duty"] == u
        t, y = d["t"][m], d["temp"][m]
        tail = y[t >= t[-1] - args.window]
        T_tail = float(np.mean(tail))
        a, b, tau_fit = exp_fit(t, y)
        stop = stops.get(u, "?")
        T_eq = T_tail if stop == "slope" else float(a)
        print("duty %3.0f%%: meðaltal síðustu %.0f s = %.2f °C, veldisfallsspá = %.2f °C "
              "(tau=%.0f s), stöðvun: %s  ->  T_eq = %.2f °C"
              % (u, args.window, T_tail, a, tau_fit, stop, T_eq))
        levels.append(dict(duty=u, T_eq=T_eq, T_tail=T_tail, T_expfit=float(a),
                           tau_expfit=float(tau_fit), stop=stop))
        segs.append((u, t, y))

    print("\n=== Þrepasvaranir (t1/3, t2/3 aðferð) ===")
    steps = []
    for i in range(len(segs)):
        u1, t, y = segs[i]
        if i == 0:
            y0, u0 = float(np.mean(y[:5])), None   # frá umhverfishita, ekkert du
        else:
            u0 = segs[i - 1][0]
            y0 = levels[i - 1]["T_eq"]
        y_inf = levels[i]["T_eq"]
        res = step_identify(t - t[0], y, y0, y_inf)
        K = (y_inf - y0) / (u1 - u0) if u0 is not None else None
        name = ("%g->%g" % (u0, u1)) if u0 is not None else ("ræsing->%g" % u1)
        print("%-10s dT=%+.2f °C  K=%s  t1/3=%.1f s  t2/3=%.1f s  Q=%.2f" % (
            name, y_inf - y0, "%.4f °C/%%" % K if K is not None else "  -   ",
            res["t13"], res["t23"], res["Q"]))
        for n in (1, 2):
            r = res["n%d" % n]
            print("           n=%d: T=%.1f s  theta=%.1f s  RMS skekkja=%.3f °C"
                  % (n, r["T"], r["theta"], r["rms"]))
        entry = dict(name=name, u0=u0, u1=u1, y0=y0, y_inf=y_inf, K=K,
                     T_mid=(y0 + y_inf) / 2, tau=res["n1"]["T"], theta=res["n1"]["theta"],
                     fit=res)
        if K is not None:
            steps.append(entry)
        else:
            startup = entry

    by_duty = {lv["duty"]: lv["T_eq"] for lv in levels}
    model = dict(levels=levels, steps=steps, startup=startup,
                 T20=by_duty.get(20.0), T50=by_duty.get(50.0), T80=by_duty.get(80.0))
    if model["T20"] is not None and model["T80"] is not None:
        model["noise_amp"] = 0.03 * abs(model["T20"] - model["T80"])
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(model, f, indent=2)
    print("\nT20 = %.2f °C, T50 = %.2f °C, T80 = %.2f °C" % (model["T20"], model["T50"], model["T80"]))
    if "noise_amp" in model:
        print("Truflun í lið 3: útslag = 0.03*|T20-T80| = %.3f °C" % model["noise_amp"])
    print("Líkan vistað í %s" % args.out)

    # --- graf ---
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(config.FIG_DIR, exist_ok=True)
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    ax.plot(d["t"], d["temp"], ".", ms=2, color="0.5", label="Mælt hitastig")
    allsegs = [startup] + steps
    for (u, t, y), st, lv in zip(segs, allsegs, levels):
        tt = t - t[0]
        f = st["fit"]["n1"]
        fit = st["y0"] + (st["y_inf"] - st["y0"]) * unit_step(1, (tt - f["theta"]) / f["T"])
        ax.plot(t, fit, "-", lw=1.5, label="FOPDT %s: tau=%.0f s, theta=%.1f s" % (st["name"], f["T"], f["theta"]))
        ax.hlines(lv["T_eq"], t[0], t[-1], colors="k", linestyles="--", lw=0.8)
        ax.text(t[-1], lv["T_eq"], " %.2f °C" % lv["T_eq"], va="bottom", ha="right")
    ax.set_ylabel("Hitastig [°C]")
    ax.set_title("Liður 1B: jafnvægishitastig og þrepasvaranir")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax2.step(d["t"], d["duty"], where="post")
    ax2.set_ylabel("Duty cycle [%]")
    ax2.set_xlabel("Tími [s]")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    p = os.path.join(config.FIG_DIR, "step1.png")
    fig.savefig(p, dpi=150)
    print("Graf vistað í %s" % p)


if __name__ == "__main__":
    main()
