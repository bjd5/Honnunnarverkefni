# Mælingar af raspi4 (13.11.2026)

Fyrstu mælingarnar, gerðar á Raspberry Pi #4 áður en skipt var yfir á raspi3.
Þær eru EKKI notaðar í hönnun stýringanna (hver vél hefur sinn eigin búnað).

- `step1_equilibrium_25kHz.csv` - jafnvægismæling við 25 kHz PWM (tíðni úr
  sýnidæmi kennara). Viftan breytti varla um hraða, svo hitinn var nánast sá
  sami við 20/50/80 % duty cycle.
- `fan_test_*Hz.csv` - snúningshraði viftu sem fall af duty cycle við
  25 kHz, 100 Hz og 1 kHz. Sýnir að hugbúnaðar-PWM (RPi.GPIO) við 25 kHz
  gefur ónothæfa svörun en 1 kHz nær línulega.
