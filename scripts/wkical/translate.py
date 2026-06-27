from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEAMS = json.loads((ROOT / "data" / "teams_nl.json").read_text(encoding="utf-8"))

ROUND_TRANSLATIONS = {
    "Group": "Groep",
    "Round of 32": "Laatste 32",
    "Round Of 32": "Laatste 32",
    "Round of 16": "Achtste finale",
    "Round Of 16": "Achtste finale",
    "Quarter-final": "Kwartfinale",
    "Quarterfinal": "Kwartfinale",
    "Semi-final": "Halve finale",
    "Semifinal": "Halve finale",
    "Third Place Playoff": "Troostfinale",
    "Final": "Finale",
}

TEXT_TRANSLATIONS = {
    "winners": "winnaars",
    "winner": "winnaar",
    "losers": "verliezers",
    "loser": "verliezer",
    "runners-up": "nummer 2",
    "runner-up": "nummer 2",
    "third place": "beste nummer 3",
    "Match": "wedstrijd",
    "Group": "Groep",
}

def team_nl(name: str | None, with_emoji: bool = False) -> str:
    if not name:
        return "Nog te bepalen"
    info = TEAMS.get(name.strip())
    if not info:
        return name.strip()
    return f"{info.get('emoji', '').strip()} {info['nl']}".strip() if with_emoji else info["nl"]

def translate_text(text: str | None) -> str:
    if not text:
        return ""
    s = text
    for source, info in sorted(TEAMS.items(), key=lambda item: -len(item[0])):
        s = re.sub(rf"\b{re.escape(source)}\b", info["nl"], s)
    for source, target in sorted(ROUND_TRANSLATIONS.items(), key=lambda item: -len(item[0])):
        s = s.replace(source, target)
    for source, target in sorted(TEXT_TRANSLATIONS.items(), key=lambda item: -len(item[0])):
        s = re.sub(rf"\b{re.escape(source)}\b", target, s)
    s = s.replace("UK time", "UK-tijd")
    s = s.replace("FIFA/Sky Sports speelschema", "FIFA/Sky Sports-speelschema")
    return s

def matchup_title(home: str | None, away: str | None, home_score: int | None = None, away_score: int | None = None, completed: bool = False) -> str:
    h = team_nl(home, with_emoji=True)
    a = team_nl(away, with_emoji=True)
    if completed and home_score is not None and away_score is not None:
        return f"WK: {h} - {a} ({home_score}–{away_score})"
    return f"WK: {h} - {a}"
