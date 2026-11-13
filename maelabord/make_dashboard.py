#!/usr/bin/env python3
"""Býr til mælaborð (maelabord/maelabord.html) með gögnunum úr data/ innbyggðum.

Opnið skrána í vafra (tvísmellið). Hún þarf netsamband aðeins fyrir letur.
Einnig er hægt að draga CSV/JSON skrár inn á síðuna eftir á.

Keyrsla (úr rót repo-sins eða úr þessari möppu):
    python3 maelabord/make_dashboard.py          -> maelabord/maelabord.html      (ykkar mælingar)
    python3 maelabord/make_dashboard.py --sim    -> maelabord/maelabord_sim.html  (hermir)
"""
import argparse
import datetime
import glob
import json
import os

import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pi_kodi"))
import config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true", help="nota gögn úr data_sim/")
    ap.add_argument("--fragment", action="store_true",
                    help="sleppa <html>/<head> umgjörð (fyrir birtingu sem Artifact)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    files = {}
    patterns = ["step1_equilibrium*.csv", "model.json", "part*_v*.csv", "part*_v*_design.json"]
    for pat in patterns:
        for p in sorted(glob.glob(os.path.join(config.DATA_DIR, pat))):
            with open(p, encoding="utf-8") as f:
                files[os.path.basename(p)] = f.read()
    if not files:
        print("Engin gögn fundust í %s/ - keyrið fyrst mælingarnar." % config.DATA_DIR)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {"files": files, "real": not config.SIM,
            "label": "%s · %d skrár · %s" % (os.path.basename(config.DATA_DIR) + "/", len(files), stamp)}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        html = f.read().replace("__DATA__", payload)
    if not args.fragment:
        html = ('<!doctype html>\n<html lang="is">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                '</head>\n<body>\n' + html + '\n</body>\n</html>\n')
    out = args.out or os.path.join(HERE, "maelabord_sim.html" if config.SIM else "maelabord.html")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("Mælaborð vistað í %s (%d skrár innbyggðar, %.0f kB)" % (out, len(files), len(html) / 1024))


if __name__ == "__main__":
    main()
