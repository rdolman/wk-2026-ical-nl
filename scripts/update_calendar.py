#!/usr/bin/env python3
"""
Update wk2026.ics met actuele WK 2026-wedstrijden.

Bron: ESPN site scoreboard endpoint. Dit is een publieke JSON-feed zonder API-key.
Als de feed tijdelijk niet beschikbaar is, stopt het script zonder de kalender te wijzigen.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ICS_PATH = ROOT / "wk2026.ics"
NAMES_PATH = ROOT / "data" / "team_names_nl.json"
AMSTERDAM = ZoneInfo("Europe/Amsterdam")

# ESPN gebruikt doorgaans fifa.world voor FIFA World Cup.
ESPN_SCOREBOARD_URL = os.environ.get(
    "ESPN_SCOREBOARD_URL",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260719&limit=300",
)

@dataclass
class Game:
    id: str
    start_utc: datetime
    home: str
    away: str
    home_score: int | None
    away_score: int | None
    completed: bool
    status: str
    venue: str | None = None

def load_team_names() -> dict[str, str]:
    return json.loads(NAMES_PATH.read_text(encoding="utf-8"))

TEAM_NL = load_team_names()

def nl_team(name: str | None) -> str:
    if not name:
        return "Nog te bepalen"
    name = name.strip()
    return TEAM_NL.get(name, name)

def fetch_games() -> list[Game]:
    req = urllib.request.Request(
        ESPN_SCOREBOARD_URL,
        headers={"User-Agent": "rdolman-wk2026-ical-nl/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    games: list[Game] = []
    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        if len(competitors) < 2:
            continue

        home_c = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away_c = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        def team_name(c):
            t = c.get("team") or {}
            return t.get("displayName") or t.get("name") or t.get("shortDisplayName") or "TBD"

        def score(c):
            raw = c.get("score")
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        status_obj = event.get("status") or {}
        status_type = status_obj.get("type") or {}
        completed = bool(status_type.get("completed"))
        status = status_type.get("description") or status_type.get("name") or ""

        dt_raw = event.get("date")
        if not dt_raw:
            continue
        # ESPN date is ISO UTC, usually ending in Z.
        start_utc = datetime.fromisoformat(dt_raw.replace("Z", "+00:00")).astimezone(timezone.utc)

        venue = None
        if comp.get("venue"):
            venue = comp["venue"].get("fullName") or comp["venue"].get("address", {}).get("city")

        games.append(
            Game(
                id=str(event.get("id")),
                start_utc=start_utc,
                home=team_name(home_c),
                away=team_name(away_c),
                home_score=score(home_c),
                away_score=score(away_c),
                completed=completed,
                status=status,
                venue=venue,
            )
        )
    return games

def unfold_ics(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n[ \t]", "", text)

def fold_ics(text: str) -> str:
    out = []
    for line in text.split("\n"):
        b = line.encode("utf-8")
        first = True
        while len(b) > 75:
            cut = 75
            while cut > 0:
                try:
                    part = b[:cut].decode("utf-8")
                    break
                except UnicodeDecodeError:
                    cut -= 1
            out.append(part)
            rest = b[cut:]
            b = (" " + rest.decode("utf-8")).encode("utf-8")
            first = False
        out.append(b.decode("utf-8"))
    return "\r\n".join(out).rstrip() + "\r\n"

def prop(block: str, name: str) -> str | None:
    m = re.search(rf"^{re.escape(name)}(?:;[^:]*)?:(.*)$", block, flags=re.M)
    return m.group(1) if m else None

def set_prop(block: str, name: str, value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    line = f"{name}:{escaped}"
    if re.search(rf"^{re.escape(name)}(?:;[^:]*)?:.*$", block, flags=re.M):
        return re.sub(rf"^{re.escape(name)}(?:;[^:]*)?:.*$", line, block, count=1, flags=re.M)
    return line + "\n" + block

def set_raw(block: str, name: str, value: str) -> str:
    line = f"{name}:{value}"
    if re.search(rf"^{re.escape(name)}(?:;[^:]*)?:.*$", block, flags=re.M):
        return re.sub(rf"^{re.escape(name)}(?:;[^:]*)?:.*$", line, block, count=1, flags=re.M)
    return line + "\n" + block

def parse_event_start(block: str) -> datetime | None:
    m = re.search(r"^DTSTART(?:;TZID=Europe/Amsterdam)?:(\d{8}T\d{6})$", block, flags=re.M)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=AMSTERDAM)

def clean_summary_team_text(summary: str) -> str:
    s = summary.replace("WK 2026:", "")
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\b\d+\s*[–:-]\s*\d+\b", "", s)
    return s.strip().lower()

def match_score_title(game: Game) -> str:
    home = nl_team(game.home)
    away = nl_team(game.away)
    if game.completed and game.home_score is not None and game.away_score is not None:
        return f"WK 2026: {home} {game.home_score}–{game.away_score} {away}"
    return f"WK 2026: {home} vs {away}"

def update_calendar() -> bool:
    if not ICS_PATH.exists():
        raise FileNotFoundError(f"{ICS_PATH} niet gevonden")

    games = fetch_games()
    if not games:
        print("Geen wedstrijden gevonden; kalender niet aangepast.")
        return False

    text = unfold_ics(ICS_PATH.read_text(encoding="utf-8", errors="replace"))
    original = text
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    events = re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, flags=re.S)
    updated_blocks = []

    for block in events:
        start = parse_event_start(block)
        current_summary = prop(block, "SUMMARY") or ""
        best: tuple[int, Game] | None = None

        if start is not None:
            start_utc = start.astimezone(timezone.utc)
            for game in games:
                diff_seconds = abs((game.start_utc - start_utc).total_seconds())
                # Within 4 hours is usually enough for timezone/source differences.
                if diff_seconds <= 4 * 3600:
                    score = int(diff_seconds)
                    # Prefer games whose names already resemble the summary.
                    summary_l = clean_summary_team_text(current_summary)
                    if nl_team(game.home).lower() in summary_l or nl_team(game.away).lower() in summary_l:
                        score -= 1800
                    if best is None or score < best[0]:
                        best = (score, game)

        if best is not None:
            game = best[1]
            new_summary = match_score_title(game)
            block = set_prop(block, "SUMMARY", new_summary)
            desc = prop(block, "DESCRIPTION") or ""
            extra = f"ESPN wedstrijd-id: {game.id}"
            if game.status:
                extra += f"\\nStatus: {game.status}"
            if game.venue:
                extra += f"\\nLocatiebron: {game.venue}"
            if "ESPN wedstrijd-id:" not in desc:
                desc = desc + ("\\n" if desc else "") + extra
            block = set_prop(block, "DESCRIPTION", desc.replace("\\n", "\n"))
            block = set_raw(block, "LAST-MODIFIED", now)
            try:
                seq = int(prop(block, "SEQUENCE") or "0") + 1
            except ValueError:
                seq = 1
            block = set_raw(block, "SEQUENCE", str(seq))

        block = set_raw(block, "DTSTAMP", now)
        updated_blocks.append("BEGIN:VEVENT\n" + block.strip() + "\nEND:VEVENT")

    iterator = iter(updated_blocks)
    text = re.sub(r"BEGIN:VEVENT\n.*?\nEND:VEVENT", lambda m: next(iterator), text, flags=re.S)

    if text != original:
        ICS_PATH.write_text(fold_ics(text), encoding="utf-8", newline="")
        return True
    return False

def main() -> int:
    try:
        changed = update_calendar()
    except Exception as exc:
        print(f"Update mislukt: {exc}", file=sys.stderr)
        return 1
    print("Kalender bijgewerkt." if changed else "Geen wijzigingen.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
