#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from wkical.ical import update_ics_file
from wkical.sources import fetch_games

def main() -> int:
    calendar = ROOT / "wk2026.ics"
    games = fetch_games()
    if not games:
        print("Geen wedstrijden gevonden; niets aangepast.")
        return 0
    changed = update_ics_file(calendar, games)
    print(f"Kalender bijgewerkt: {changed}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
