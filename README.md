# Hitastýring með viftu - hönnunarverkefni IÐN303G

Raspberry Pi stýrir hitastigi í litlu rými. 50 W hitaelement er alltaf í gangi
(kveikt með segulrofa) og DS18B20 hitanemi situr fyrir ofan það. Eina
stýribreytan er PWM vifta (Arctic F12 PWM): **hærra duty cycle = meiri kæling =
lægra hitastig**. Kerfið hefur því neikvæða mögnun (K < 0 °C/%).

Verkefnið skiptist í:

| Liður | Hvað | Skrifta |
|---|---|---|
| 1A/1B | Jafnvægishitastig við 20/50/80 % duty cycle og auðkenning líkans | `step1_equilibrium.py`, `identify.py` |
| 1 | Halda föstu óskgildi T50 í 240 s | `run_part1.py` |
| 2 | Fylgja óskgildisferli T50 → T20 → T80 (rampar og föst gildi) | `run_part2.py` |
| 3 | Eins og liður 2 en með sínustruflun á mælingunni | `run_part3.py` |

T20, T50 og T80 eru jafnvægishitastigin sem mældust við 20, 50 og 80 % duty
cycle. Athugið að T20 > T50 > T80 (meiri vifta → kaldara).

## Bálkarit

```text
                                       truflun d(t) (aðeins liður 3)
                                       A·sin(2πt / 8 s)
                                              │
              ┌───────────────────┐  u_ff     │
 r(t+θ) ─────►│ Feedforward       │─────┐     │
              │ u_ss(r) + τ·u'ss·ṙ│     │     │
              └───────────────────┘     ▼     │
           ┌────────┐  e   ┌──────┐  ┌───┐ u ┌────────────────┐  y   ┌─────────┐
 r(t) ────►│ e=y−r  │─────►│  PI  │─►│ + │──►│ Vifta + hita-  │─────►│ DS18B20 │──┐
           └────────┘      │ +AW  │  └───┘   │ gjafi + loft   │      └─────────┘  │
               ▲           └──────┘  mettun  │ G(s), K < 0    │                   │
               │                     0–100 % └────────────────┘                   │
               │      y_f  ┌───────────────┐   y_m                               ▼
               └───────────│ Síur (lið 3   │◄─────────────────────────────────(+)◄── d(t)
                           │ v2: notch+LP) │
                           └───────────────┘

   G(s) = K e^{-θs} / (τs + 1)      AW = anti-windup (back-calculation)
```

Í hverri lotu (T = 1 s): lesa y → (bæta við truflun) → sía → reikna r(t) →
PI + feedforward → mettun 0–100 % → stilla viftu → skrá í CSV.

## Skráaskipan

| Skrá / mappa | Hlutverk |
|---|---|
| `pi_kodi/config.py` | Pinnar, PWM tíðni, söfnunartími T = 1 s, öryggismörk (90 °C), möppur. `--sim` í skipanalínu beinir gögnum í `data_sim/` og `figures_sim/` |
| `pi_kodi/hardware.py` | `Hardware` (raunverulegur Pi: GPIO, PWM, segulrofar, DS18B20, Hall-nemi) og `SimHardware` (hermir með sama viðmóti) |
| `pi_kodi/controller.py` | Stakræn PID með anti-windup (back-calculation), síur (`LowPass`, `Notch`), `Controller` sem sameinar síur + feedforward + gain scheduling |
| `pi_kodi/design.py` | FOPDT líkan, SIMC/lambda stilling, kyrrstöðuferill u_ss(T), `PRESETS` með v1/v2 fyrir hvern lið |
| `pi_kodi/step1_equilibrium.py` | Liður 1B: þrep 20 → 50 → 80 % og mæling á jafnvægishitastigi |
| `pi_kodi/identify.py` | Auðkenning með t1/3, t2/3 aðferð → `data/model.json` + `figures/step1.png` |
| `pi_kodi/runner.py` | Sameiginleg reglunarlykkja, óskgildisferlar, aðlögunartími (settle) og CSV skráning |
| `pi_kodi/run_part1.py`, `run_part2.py`, `run_part3.py` | Keyra lið 1/2/3 með `v1` eða `v2` |
| `pi_kodi/analyze.py` | Mælikvarðar (tafla í Markdown + `data/metrics.csv`) og gröf `figures/partN.png` |
| `requirements.txt` | Python pakkar |
| `data/` | Mæligögn: `step1_equilibrium.csv`, `model.json`, `partN_vX.csv`, `partN_vX_design.json`, `metrics.csv` |
| `figures/` | Gröf: `step1.png`, `part1.png`, `part2.png`, `part3.png` |
| `data_sim/`, `figures_sim/` | Sama fyrir hermi (í `.gitignore`) |
| `maelabord/` | Gagnvirkt mælaborð í vafra: `template.html` (síðan), `make_dashboard.py` (byggir `maelabord.html` með gögnunum innbyggðum) |

## Tengingar (BCM númerun, úr `config.py`)

| Merki | GPIO (BCM) | Pinni á haus | Athugasemd |
|---|---|---|---|
| PWM til viftu | GPIO20 | 38 | 1 kHz (`FAN_PWM_FREQ`, valið út frá `fan_test.py`), blár vír á 4-pinna viftu |
| Hall-nemi (tach) | GPIO21 | 40 | Innri pull-up virkur, 2 púlsar á hring, grænn/gulur vír |
| Segulrofi viftu | GPIO26 | 37 | Virkur LOW (`RELAY_ACTIVE_LOW = True`) |
| Segulrofi hitagjafa | GPIO16 | 36 | Virkur LOW |
| DS18B20 gögn | GPIO4 | 7 | Sjálfgefinn 1-Wire pinni; 4,7 kΩ pull-up í 3,3 V |
| Jörð | GND | t.d. 39 | Sameiginleg jörð með viftu og segulrofum |

Neminn finnst sjálfkrafa (fyrsta `28-*` tækið í `/sys/bus/w1/devices`). Ef
fleiri en einn nemi er tengdur má setja `W1_DEVICE_ID` í `config.py`.

## Uppsetning á Raspberry Pi

1. Virkja 1-Wire. Bætið eftirfarandi línu neðst í `/boot/firmware/config.txt`
   (Bookworm og nýrra) eða `/boot/config.txt` (eldri útgáfur):

   ```text
   dtoverlay=w1-gpio
   ```

   Einnig má nota `sudo raspi-config` → *Interface Options* → *1-Wire*.

2. Endurræsa:

```bash
sudo reboot
```

3. Athuga að neminn sjáist (á að sýna `28-xxxxxxxxxxxx`):

```bash
ls /sys/bus/w1/devices/
```

4. Setja upp Python pakka. Á Pi þurfa keyrsluskrifturnar
   (`step1_equilibrium.py`, `run_partN.py`) **aðeins RPi.GPIO**, sem er yfirleitt
   þegar uppsett á Raspberry Pi OS:

```bash
sudo apt install python3-rpi.gpio
```

   `identify.py` og `analyze.py` þurfa **numpy og matplotlib**. Þær má keyra á
   Pi eða á fartölvu eftir að `data/` hefur verið afrituð þangað:

```bash
sudo apt install python3-numpy python3-matplotlib
```

   eða á fartölvu (RPi.GPIO er sjálfkrafa sleppt utan ARM):

```bash
pip install -r requirements.txt
```

> Á Raspberry Pi 5 virkar upprunalega RPi.GPIO ekki; þar má nota
> `python3-rpi-lgpio` sem býður upp á sama viðmót.

## Keyrsluröð

Allar Python skrárnar eru í möppunni `pi_kodi/` og skipanirnar hér fyrir neðan
eru keyrðar þaðan. Gögn og gröf fara samt alltaf í `data/` og `figures/` í rót
repo-sins. Farið fyrst inn í möppuna:

```bash
cd pi_kodi
```

 Hægt er að stöðva hvenær sem er
með Ctrl+C; þá er slökkt á hitagjafanum og viftan kælir á 100 % í allt að 60 s
(eða þar til hiti < 35 °C). Gögn eru skrifuð jafnóðum.

**1. Jafnvægishitastig (liður 1B)** - á Pi:

```bash
python3 step1_equilibrium.py
```

Viftan fer 20 % → 50 % → 80 %. Hvert þrep stendur í minnst 300 s og mest
1500 s. Jafnvægi telst náð þegar hallatala bestu línu síðustu 120 s er undir
0,1 °C/mín samfellt í 60 s. **Tími: um 20–75 mín** (fyrsta þrepið, upphitun frá
herbergishita, er lengst). Úttak: `data/step1_equilibrium.csv` og
`data/step1_equilibrium_meta.json`.

**2. Auðkenning líkans** - numpy + matplotlib, tekur nokkrar sekúndur:

```bash
python3 identify.py
```

Reiknar T20/T50/T80, metur FOPDT líkan (K, τ, θ) fyrir þrepin 20→50 og 50→80
með t1/3, t2/3 aðferðinni (bæði n = 1 og n = 2, n = 1 notað í hönnun) og
útslag truflunar í lið 3, A = 0,03·|T20 − T80|. Úttak: `data/model.json`,
`figures/step1.png`. **Þetta verður að keyra áður en liðir 1–3 eru keyrðir.**

**3. Lokaðar lykkjur (liðir 1–3)** - á Pi, hver lið bæði `v1` og `v2`:

```bash
python3 run_part1.py v1
```

```bash
python3 run_part1.py v2
```

```bash
python3 run_part2.py v1
```

```bash
python3 run_part2.py v2
```

```bash
python3 run_part3.py v1
```

```bash
python3 run_part3.py v2
```

Hver keyrsla byrjar á **aðlögunartíma** (settle): stýringin er virk við T50 þar
til hitinn hefur verið innan ±0,3 °C í 30 s (mest 600 s). Þá hefst sjálf
keyrslan og t = 0. Gagnlegir rofar: `--quiet` (prenta á 10 s fresti),
`--settle-max`, `--settle-hold`, `--tol`.

| Keyrsla | Aðlögun | Óskgildisferill | Kæling í lokin | Samtals |
|---|---|---|---|---|
| `run_part1.py` | 0,5–10 mín | 240 s | ≤ 1 mín | **~6–15 mín** |
| `run_part2.py` | 0,5–10 mín | 780 s (180+120+180+120+180) | ≤ 1 mín | **~15–25 mín** |
| `run_part3.py` | 0,5–10 mín | 780 s | ≤ 1 mín | **~15–25 mín** |

Allar sex keyrslurnar taka því um 1,5–2 klst. Ráð: keyrið þær beint hver á eftir
annarri meðan kerfið er heitt - þá styttist aðlögunin. Ef byrjað er kalt getur
upphitunin tekið lengri tíma en 600 s; hækkið þá `--settle-max`.

Úttak: `data/partN_vX.csv` (t, fasi, r, y, y_meas, y_filt, u, u_ff, P, I, Kc,
Ti) og `data/partN_vX_design.json` (líkan og stillistuðlar sem voru notaðir).

**4. Greining** - numpy + matplotlib:

```bash
python3 analyze.py
```

Prentar Markdown töflu með v1 vs. v2 og hlutfallslegri breytingu fyrir hvern
lið (beint í skýrsluna), vistar `data/metrics.csv` og teiknar
`figures/part1.png`, `part2.png`, `part3.png`. Aðeins `phase == run` hluti
gagnanna er notaður.

## Prófun með hermi (`--sim`)

`SimHardware` hermir ólínulegt fyrstu gráðu kerfi með dauðtíma, suði og 12 bita
upplausn DS18B20. Gildin eru ágiskun - **aðeins til að prófa kóðann, ekki til að
hanna eftir**. Með `--sim` fara öll gögn í `data_sim/` og `figures_sim/` svo
raunmælingar skrifast aldrei yfir. Allt ferlið keyrir á innan við mínútu:

```bash
python3 step1_equilibrium.py --sim
```

```bash
python3 identify.py --sim
```

```bash
python3 run_part2.py v2 --sim --quiet
```

```bash
python3 analyze.py --sim
```

Til að horfa á keyrsluna í „rauntíma“ (t.d. 20× hraðar) má nota `--speed`:

```bash
python3 run_part2.py v2 --sim --speed 20
```

## Stýringarnar: v1 (upprunaleg) og v2 (endurbætt)

Allar stýringarnar eru stakrænar PI stýringar (T_D = 0) samkvæmt glærunum
„Stakræn útfærsla á stýringu“, stilltar út frá FOPDT líkaninu

    G(s) = K e^{-θs} / (τs + 1),   K < 0

með SIMC/lambda aðferð (Skogestad 2003):

    Kc = τ / (|K| (τc + θ_eff)),    Ti = min(τ, 4 (τc + θ_eff))

þar sem θ_eff = θ + T/2 (zero-order hold) + seinkun sía. Formerkið er snúið
(e = y − r) þannig að of hár hiti eykur duty cycle. Gildin eru í `PRESETS` í
`design.py` og stillistuðlarnir prentast í upphafi hverrar keyrslu.

### Liður 1 - fast óskgildi T50

| | v1 | v2 |
|---|---|---|
| Stilling | Lambda, τc = τ/3 | SIMC, τc = 2·θ_eff |
| Líkan | Meðaltal þrepasvarananna | Líkan við óskgildið T50 |
| Anti-windup | Nei | Já (back-calculation) |
| Feedforward | Nei | Kyrrstöðu: u_ss(T50) |

Rök fyrir endurbótum:
- **Hraðari stilling.** τc = τ/3 er íhaldssöm; SIMC með τc = 2θ gefur mun hærra
  Kc og styttra Ti og gefur samt góð stöðugleikamörk (robust) gagnvart
  líkanskekkju.
- **Líkan við vinnupunkt.** Mögnunin |K| breytist mikið með duty cycle
  (viftan kælir minna og minna eftir því sem hún snýst hraðar), svo meðallíkan
  er rangt við T50.
- **Feedforward.** u_ss(r) fæst með 2. gráðu (Lagrange) brúun gegnum
  jafnvægispunktana (T_eq, duty). PI þarf þá aðeins að leiðrétta smáskekkju í
  stað þess að heildarliðurinn þurfi að „finna“ allt stýrimerkið.
- **Anti-windup.** Kemur í veg fyrir að heildarliðurinn safnist upp þegar
  viftan mettast í 0 % eða 100 % (t.d. í upphitun).

### Liður 2 - breytingar í óskgildi

| | v1 | v2 |
|---|---|---|
| Stilling | Lambda, τc = τ/3 | SIMC, τc = 2·θ_eff |
| Líkan | Meðaltal | Gain scheduling: K, τ, θ brúuð línulega eftir r(t) |
| Anti-windup | Já | Já |
| Feedforward | Nei | Dýnamískt: u_ss(r) + τ·du_ss/dT·ṙ |
| Forsýn (preview) | - | Feedforward notar r(t + θ_eff) |

Rök fyrir endurbótum:
- **Gain scheduling.** Óskgildið fer yfir allt bilið T80…T20 þar sem |K| er
  breytilegt; Kc og Ti eru endurreiknuð í hverju skrefi út frá líkani við r(t)
  svo lokaða lykkjan hagi sér eins á öllu bilinu.
- **Dýnamískt feedforward.** Í rampi dugar kyrrstöðugildið ekki því kerfið er
  hægt; liðurinn τ·du_ss/dT·ṙ (afleiða kyrrstöðuferilsins sinnum hallatala
  rampsins) bætir upp töfina og minnkar eftirdragið (tracking error) í rampinum.
- **Forsýn.** Óskgildisferillinn er þekktur fyrirfram, svo feedforward getur
  brugðist θ_eff sekúndum fyrr og þannig vegið upp dauðtímann.

### Liður 3 - breytingar í óskgildi + truflun á mælingu

Truflunin y_m = y + 0,03·|T20 − T80|·sin(2πt / 8 s) er lögð við mælinguna
**áður** en stýrimerkið er reiknað.

| | v1 | v2 |
|---|---|---|
| Grunnur | Sama og liður 2 v2 (engar síur) | Liður 2 v2 |
| Síur | Engar | Hakasía (notch) við 1/8 Hz, Q = 1, og lágtíðnisía T_f = 1 s |
| Stilling | SIMC, τc = 2·θ_eff | SIMC, τc = 3·θ_eff, θ_eff inniheldur seinkun sía |

Rök fyrir endurbótum:
- **v1 sýnir vandann:** hröð stýring með háu Kc magnar truflunina beint upp í
  stýrimerkið (Kc·A), viftan sveiflast með 8 s lotu og slitnar, en raunhitinn
  breytist lítið því kerfið (τ ≫ 8 s) síar truflunina hvort sem er.
- **Hakasía** fjarlægir þekkta tíðni truflunarinnar (1/8 Hz) með DC mögnun 1,
  þannig að hún hefur engin áhrif á jafnvægisskekkju. **Lágtíðnisían** dempar
  afganginn og mælisuð (0,0625 °C upplausn).
- **Hægari stilling.** Síurnar bæta við fasaviki (u.þ.b. 2 s töf), sem er tekið
  inn í θ_eff, og τc er stækkað úr 2θ í 3θ til að halda stöðugleikamörkum.
- Málamiðlun: v2 er nokkru hægari í að fylgja rampi en notar margfalt rólegra
  stýrimerki. Þetta á að ræða í skýrslunni út frá mælikvörðunum hér að neðan.

## Mælikvarðar (`analyze.py`) og rökstuðningur

Skekkjan er reiknuð sem e = r − y með **raunverulega** mælda hitanum y (án
viðbættrar truflunar í lið 3), því markmiðið er að raunhitinn fylgi óskgildinu,
ekki truflaða mælingin.

| Mælikvarði | Hvað hann mælir | Af hverju |
|---|---|---|
| IAE = Σ\|e\|·T | Heildarskekkja yfir keyrsluna | Ein tala sem tekur bæði hraða og nákvæmni með; algengur samanburðarkvarði |
| RMS(e), max\|e\| | Dæmigerð og versta skekkja | max\|e\| sýnir hvort hitinn fór langt frá óskgildi |
| e_ss (Hn) | Meðalskekkja síðustu 60 s hvers fasta bútar | Skekkja í jafnvægi - PI á að gefa ~0 |
| Meðal e (Rn) | Meðalskekkja í rampi | Eftirdragi (tracking error) - sýnir gagn feedforward |
| t_s (Hn) | Tími eftir ramp þar til \|e\| < 0,5 °C til enda bútar | Hraði svörunar |
| Yfirskot (Hn) | Mesta frávik handan óskgildis eftir ramp | Dempun/sveiflur |
| TV(u) = Σ\|Δu\|, std(Δu) | Breytileiki stýrimerkis | Slit á viftu, hávaði og næmni fyrir suði/truflun - lykilatriði í lið 3 |
| mean u | Meðal duty cycle | Orkunotkun viftu; sambærilegt milli v1 og v2 |

Hönnunarkröfurnar eru hraði, lítil skekkja í jafnvægi, lítil næmni fyrir
truflunum og hóflegt stýrimerki - og mælikvarðarnir ná utan um hvern þeirra.
Athugið að í lið 1 hefst keyrslan eftir að aðlögun er lokið, þannig að t_s er
þar yfirleitt 0 og munurinn á v1 og v2 sést helst í IAE/RMS og TV(u).

## Mælaborð (`maelabord/`)

Gagnvirk vefsíða sem sýnir óskgildi, hitastig og stýrimerki fyrir v1 og v2 í hverjum lið, ásamt sömu mælikvörðum og `analyze.py`. Ljóst þema er sjálfgefið, með rofa fyrir dökkt.

Byggja mælaborð með ykkar mælingum úr `data/` innbyggðum (býr til `maelabord/maelabord.html`). Keyrt úr rót repo-sins:

```bash
python3 maelabord/make_dashboard.py
```

Sama með hermigögnum úr `data_sim/` (býr til `maelabord/maelabord_sim.html`):

```bash
python3 maelabord/make_dashboard.py --sim
```

Opnið HTML skrána í vafra með því að tvísmella á hana. Einnig er hægt að draga CSV/JSON skrár úr `data/` beint inn á síðuna með „Hlaða inn gögnum“. Síðan þekkir skrárnar á nafninu (`part2_v1.csv`, `step1_equilibrium.csv`, `model.json` o.s.frv.).

## Ráð fyrir myndbandið

- **Búnaðurinn:** sýnið Pi, viftu, hitaelement, nema og segulrofa og útskýrið
  tengingarnar stuttlega (tafla hér að ofan).
- **Lið 1B:** sýnið `step1_equilibrium.py` í gangi (útprentun með hallatölu) og
  svo `figures/step1.png` með jafnvægisgildunum og FOPDT nálguninni. Ekki þarf
  að sýna alla keyrsluna - klippið eða hraðspólið.
- **Líkanið:** sýnið úttak `identify.py` (K, τ, θ, Q) og útskýrið að |K| breytist
  með vinnupunkti.
- **Hver liður:** sýnið skipunina (`python3 run_part2.py v2`), útprentunina
  (r, y, e, u, ff) og heyrið/sjáið viftuna breyta hraða. Hraðspólið langa
  kafla.
- **Samanburður:** sýnið `figures/partN.png` (v1 rautt, v2 blátt) og töfluna
  úr `analyze.py` og bendið á mikilvægustu tölurnar (IAE, eftirdragi í rampi,
  TV(u)).
- **Liður 3:** bendið á að mælingin (ljósa línan) sveiflast en raunhitinn
  ekki, og hvernig stýrimerkið í v1 sveiflast með 8 s lotu en ekki í v2.
- **Kóðinn:** sýnið stuttlega PI útfærsluna í `controller.py` (sama form og í
  glærunum + anti-windup) og `PRESETS` í `design.py`.
- Takið fram að hermirinn var aðeins notaður til að prófa kóðann; allar
  niðurstöður í myndbandinu eiga að vera úr raunmælingum.
