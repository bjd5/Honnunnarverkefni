"""Stakræn PID stýring og síur.

Grunnformið er úr glærunum "Stakræn útfærsla á stýringu":

    u(kT) = K ( e(kT) + T/T_I * sum_{i=0}^{k-1} e(iT) + T_D/T * (e(kT) - e((k-1)T)) )

Viðbætur sem hægt er að kveikja á (notaðar í endurbættum útgáfum):
  * anti-windup (back-calculation) þegar stýrimerkið mettast í 0% / 100%
  * vigtun óskgildis í P-lið (b) og afleiða reiknuð af mælingu, ekki skekkju
  * síaður afleiðuliður (N)
  * framvirk stýring (feedforward) sem bætist við úttak PID
  * síur á mælingu (lágtíðnisía, hakasía/notch)
  * breytilegir stuðlar (gain scheduling)

Formerki: viftan KÆLIR, þ.e. hærra duty cycle -> lægra hitastig (K < 0).
Því er sign = -1 og skekkjan e = sign*(r - y) = y - r: ef of heitt þá eykst
duty cycle.
"""
import math


class LowPass:
    """Fyrstu gráðu lágtíðnisía, y_f' = (y - y_f)/Tf (backward Euler)."""

    def __init__(self, tf):
        self.tf = tf
        self.y = None

    def reset(self, y0):
        self.y = y0

    def __call__(self, x, dt):
        if self.y is None:
            self.y = x
        a = dt / (self.tf + dt)
        self.y += a * (x - self.y)
        return self.y


class Notch:
    """Stakræn hakasía (biquad) sem dempar tíðnina f0 [Hz]. DC mögnun = 1."""

    def __init__(self, f0, ts, q=2.0):
        w0 = 2 * math.pi * f0 * ts
        alpha = math.sin(w0) / (2 * q)
        c = math.cos(w0)
        a0 = 1 + alpha
        self.b = (1 / a0, -2 * c / a0, 1 / a0)
        self.a = (-2 * c / a0, (1 - alpha) / a0)
        self.x1 = self.x2 = self.y1 = self.y2 = None

    def reset(self, y0):
        self.x1 = self.x2 = self.y1 = self.y2 = y0

    def __call__(self, x, dt=None):
        if self.x1 is None:
            self.reset(x)
        b, a = self.b, self.a
        y = b[0] * x + b[1] * self.x1 + b[2] * self.x2 - a[0] * self.y1 - a[1] * self.y2
        self.x2, self.x1 = self.x1, x
        self.y2, self.y1 = self.y1, y
        return y


class PID:
    def __init__(self, kc, ti, td=0.0, n=10.0, b=1.0, sign=-1,
                 umin=0.0, umax=100.0, antiwindup=True, tt=None):
        self.kc, self.ti, self.td, self.n, self.b = kc, ti, td, n, b
        self.sign = sign
        self.umin, self.umax = umin, umax
        self.antiwindup = antiwindup
        self.tt = tt  # tímastuðull back-calculation (None -> T_I)
        self.i = 0.0
        self.d = 0.0
        self.y_prev = None

    def reset(self, y0, i0=0.0):
        self.i = i0
        self.d = 0.0
        self.y_prev = y0

    def update(self, r, y, dt, bias=0.0):
        s = self.sign
        if self.y_prev is None:
            self.y_prev = y
        e = s * (r - y)
        p = self.kc * s * (self.b * r - y)
        if self.td > 0:
            a = self.td / (self.td + self.n * dt)
            self.d = a * self.d - self.kc * self.td * self.n / (self.td + self.n * dt) * s * (y - self.y_prev)
        else:
            self.d = 0.0
        v = bias + p + self.i + self.d                 # ómettað stýrimerki
        u = min(max(v, self.umin), self.umax)          # mettað stýrimerki
        # heildun (summa skekkju) - uppfærð EFTIR að úttak er reiknað
        di = self.kc * dt / self.ti * e if self.ti > 0 else 0.0
        if self.antiwindup:
            tt = self.tt or self.ti
            di += dt / tt * (u - v)
        self.i += di
        self.y_prev = y
        return u, {"e": e, "p": p, "i": self.i, "d": self.d, "v": v}


class Controller:
    """Heildarstýring: síur á mælingu + framvirk stýring + PID (+ gain scheduling).

    preview [s]: framvirka stýringin notar óskgildið r(t + preview) til að
    vega upp á móti dauðtíma kerfisins (óskgildisferillinn er þekktur fyrirfram).
    """

    def __init__(self, name, pid, filters=(), feedforward=None, schedule=None,
                 preview=0.0, description=""):
        self.name = name
        self.pid = pid
        self.filters = list(filters)
        self.feedforward = feedforward    # fall (r, r_dot) -> u_ff
        self.schedule = schedule          # fall (r) -> (kc, ti)
        self.preview = preview
        self.description = description

    def reset(self, y0, r0, u0):
        for f in self.filters:
            f.reset(y0)
        ff = self.feedforward(r0, 0.0) if self.feedforward else 0.0
        self.pid.reset(y0, i0=u0 - ff)  # "bumpless" ræsing: u = u0 í byrjun

    def update(self, r, y, dt, r_ff=None, rdot_ff=0.0):
        yf = y
        for f in self.filters:
            yf = f(yf, dt)
        if self.schedule:
            self.pid.kc, self.pid.ti = self.schedule(r)
        ff = 0.0
        if self.feedforward:
            ff = self.feedforward(r if r_ff is None else r_ff, rdot_ff)
        u, info = self.pid.update(r, yf, dt, bias=ff)
        info.update({"y_f": yf, "u_ff": ff, "kc": self.pid.kc, "ti": self.pid.ti})
        return u, info
