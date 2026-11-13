#!/usr/bin/env python3
"""Liður 2: Fylgja breytingum í óskgildi: T50 (180 s) -> rampur í T20 (120 s) -> T20 (180 s)
   -> rampur í T80 (120 s) -> T80 (180 s).

Keyrsla:  python3 run_part2.py v1        (upprunaleg stýring)
          python3 run_part2.py v2        (endurbætt stýring)
          python3 run_part2.py v1 --sim  (hermir)
"""
from runner import main

if __name__ == "__main__":
    main(2)
