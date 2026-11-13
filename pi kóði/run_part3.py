#!/usr/bin/env python3
"""Liður 3: Eins og liður 2, en með sínustruflun á mælingunni:
   y_m = y + 0.03*|T20 - T80| * sin(2 pi t / 8 s), bætt við ÁÐUR en stýrimerkið er reiknað.

Keyrsla:  python3 run_part3.py v1        (upprunaleg stýring)
          python3 run_part3.py v2        (endurbætt stýring)
          python3 run_part3.py v1 --sim  (hermir)
"""
from runner import main

if __name__ == "__main__":
    main(3)
