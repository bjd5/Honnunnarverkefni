"""Hönnun stýringa út frá líkani (model.json sem identify.py býr til).

Líkan kerfisins (fyrstu gráðu með dauðtíma, FOPDT) um vinnupunkt:

            dT(s)        K e^{-theta s}
    G(s) = ------- = ------------------      K < 0 [°C/%]  (vifta kælir)
            du(s)       tau s + 1

Stillingaraðferð: SIMC (Skogestad 2003), sem er IMC/lambda stilling fyrir FOPDT:

    Kc = tau / (|K| (tc + theta))
    Ti = min(tau, 4 (tc + theta))

tc er óskaður tímastuðull lokuðu lykkjunnar: lítið tc -> hröð en næm stýring,
stórt tc -> hæg en sterk (robust) stýring.

Framvirk stýring (feedforward) notar kyrrstöðuferil kerfisins u_ss(T) sem fæst
úr jafnvægismælingunum við 20/50/80% (annarrar gráðu brúun), auk afleiðuliðar
tau * du_ss/dT * dr/dt sem vegur upp hæga svörun kerfisins í rampi.

PRESETS skilgreinir upprunalega (v1) og endurbætta (v2) útgáfu fyrir hvern lið.
Breytið gildunum hér ef mælingarnar kalla á það og rökstyðjið í skýrslunni.
"""
import json

import config
from controller import PID, Controller, LowPass, Notch


# ---------------------------------------------------------------------------
# Líkan
# ---------------------------------------------------------------------------
def load_model(path=config.MODEL_FILE):
    with open(path) as f:
        return json.load(f)


def _eq_points(model):
    pts = sorted((lv["T_eq"], lv["duty"]) for lv in model["levels"])
    return pts  # [(T, u), ...] í hækkandi T


def u_static(model, T):
    """Kyrrstöðuferill: duty cycle [%] sem gefur jafnvægishitastig T.

    Lagrange brúun gegnum (T_eq, duty) punktana (3 punktar -> 2. gráðu).
    Utan mælda bilsins er notuð línuleg framlenging til að forðast ofsveiflur.
    """
    pts = _eq_points(model)
    lo, hi = pts[0][0], pts[-1][0]
    if T < lo or T > hi:
        Tb = lo if T < lo else hi
        u = _lagrange(pts, Tb) + du_dT(model, Tb) * (T - Tb)
    else:
        u = _lagrange(pts, T)
    return min(max(u, config.DUTY_MIN), config.DUTY_MAX)


def du_dT(model, T):
    """Afleiða kyrrstöðuferilsins, du_ss/dT [%/°C] (= 1/K staðbundið)."""
    pts = _eq_points(model)
    lo, hi = pts[0][0], pts[-1][0]
    T = min(max(T, lo), hi)
    h = 1e-3
    return (_lagrange(pts, T + h) - _lagrange(pts, T - h)) / (2 * h)


def _lagrange(pts, x):
    total = 0.0
    for i, (xi, yi) in enumerate(pts):
        term = yi
        for j, (xj, _) in enumerate(pts):
            if i != j:
                term *= (x - xj) / (xi - xj)
        total += term
    return total


def plant_at(model, T):
    """FOPDT stuðlar (K, tau, theta) við hitastig T - línuleg brúun milli
    þrepasvarana (gain scheduling). Utan bilsins er næsta líkan notað."""
    steps = sorted(model["steps"], key=lambda s: s["T_mid"])
    if T <= steps[0]["T_mid"]:
        s = steps[0]
        return s["K"], s["tau"], s["theta"]
    if T >= steps[-1]["T_mid"]:
        s = steps[-1]
        return s["K"], s["tau"], s["theta"]
    for a, b in zip(steps, steps[1:]):
        if a["T_mid"] <= T <= b["T_mid"]:
            w = (T - a["T_mid"]) / (b["T_mid"] - a["T_mid"])
            return tuple(a[k] + w * (b[k] - a[k]) for k in ("K", "tau", "theta"))


def plant_avg(model):
    """Meðallíkan (notað í upprunalegu útgáfunum)."""
    n = len(model["steps"])
    return tuple(sum(s[k] for s in model["steps"]) / n for k in ("K", "tau", "theta"))


def simc(K, tau, theta, tc):
    kc = tau / (abs(K) * (tc + theta))
    ti = min(tau, 4.0 * (tc + theta))
    return kc, ti


# ---------------------------------------------------------------------------
# Útgáfur stýringa
# ---------------------------------------------------------------------------
#  tc_tau / tc_theta: tc = max(tc_tau*tau, tc_theta*theta_eff)
#  model:     "avg" = eitt meðallíkan, "local" = líkan við óskgildi (scheduling)
#  ff:        None, "static" (u_ss(r)) eða "dynamic" (u_ss(r) + tau*du/dT*dr/dt)
#  preview:   nota r(t + theta) í framvirku stýringunni
#  notch/lp:  síur á mælingu (liður 3)
PRESETS = {
    1: {
        "v1": dict(desc="PI, lambda-stilling tc = tau/3, meðallíkan, ekkert anti-windup",
                   tc_tau=1 / 3, model="avg", antiwindup=False, ff=None),
        "v2": dict(desc="PI, SIMC tc = 2*theta (hraðari), líkan við óskgildi, "
                        "anti-windup, kyrrstöðu-feedforward",
                   tc_theta=2.0, model="local", antiwindup=True, ff="static"),
    },
    2: {
        "v1": dict(desc="PI, lambda-stilling tc = tau/3, meðallíkan, anti-windup",
                   tc_tau=1 / 3, model="avg", antiwindup=True, ff=None),
        "v2": dict(desc="PI, SIMC tc = 2*theta, gain scheduling, anti-windup, "
                        "dýnamískt feedforward með forsýn (preview = theta)",
                   tc_theta=2.0, model="schedule", antiwindup=True, ff="dynamic",
                   preview=True),
    },
    3: {
        "v1": dict(desc="Sama og endurbætt stýring í lið 2 (engar síur)",
                   tc_theta=2.0, model="schedule", antiwindup=True, ff="dynamic",
                   preview=True),
        "v2": dict(desc="Liður 2 v2 + hakasía (notch) við 1/8 Hz og lágtíðnisía á mælingu, "
                        "tc stækkað til að taka tillit til fasavik síanna",
                   tc_theta=3.0, model="schedule", antiwindup=True, ff="dynamic",
                   preview=True, notch=True, notch_q=1.0, lp_tf=1.0),
    },
}


def _tc(spec, tau, theta):
    return max(spec.get("tc_tau", 0.0) * tau, spec.get("tc_theta", 0.0) * theta)


def build_controller(part, version, model, ts=config.TS, noise_period=8.0):
    spec = PRESETS[part][version]
    extra_lag = 0.0
    filters = []
    if spec.get("notch"):
        filters.append(Notch(1.0 / noise_period, ts, q=spec.get("notch_q", 1.0)))
        extra_lag += noise_period / 8  # gróf nálgun á seinkun hakasíunnar
    if spec.get("lp_tf"):
        filters.append(LowPass(spec["lp_tf"]))
        extra_lag += spec["lp_tf"]

    def theta_eff(theta):
        # dauðtími + hálfur söfnunartími (zero-order hold) + seinkun sía
        return theta + ts / 2 + extra_lag

    def tune(K, tau, theta):
        th = theta_eff(theta)
        return simc(K, tau, th, _tc(spec, tau, th))

    if spec["model"] == "avg":
        K, tau, theta = plant_avg(model)
    else:
        K, tau, theta = plant_at(model, model["T50"])
    kc, ti = tune(K, tau, theta)
    sign = -1 if K < 0 else 1

    schedule = None
    if spec["model"] == "schedule":
        def schedule(r):
            return tune(*plant_at(model, r))

    feedforward = None
    if spec.get("ff") == "static":
        def feedforward(r, rdot):
            return u_static(model, r)
    elif spec.get("ff") == "dynamic":
        def feedforward(r, rdot):
            _, tau_r, _ = plant_at(model, r)
            return u_static(model, r) + tau_r * du_dT(model, r) * rdot

    # Framvirka stýringin fer EKKI í gegnum síurnar á mælingunni, svo forsýnin
    # bætir aðeins upp dauðtíma kerfisins + hálfan söfnunartíma.
    preview = (theta + ts / 2) if spec.get("preview") else 0.0

    pid = PID(kc, ti, sign=sign, umin=config.DUTY_MIN, umax=config.DUTY_MAX,
              antiwindup=spec["antiwindup"])
    ctrl = Controller("lidur%d_%s" % (part, version), pid, filters=filters,
                      feedforward=feedforward, schedule=schedule,
                      preview=preview, description=spec["desc"])
    ctrl.design = dict(K=K, tau=tau, theta=theta, theta_eff=theta_eff(theta),
                       tc=_tc(spec, tau, theta_eff(theta)), kc=kc, ti=ti)
    return ctrl
