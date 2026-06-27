from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class Game:
    id: str
    start_utc: datetime
    home: str
    away: str
    home_score: int | None
    away_score: int | None
    completed: bool
    status: str
    stage: str | None = None
    venue: str | None = None

ESPN_SCOREBOARD_URL = os.environ.get(
    "ESPN_SCOREBOARD_URL",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260719&limit=300",
)

def _read_json_url(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "rdolman-wk2026-ical-nl/2.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def _score(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def fetch_espn_games() -> list[Game]:
    """Haal wedstrijden op uit de publieke ESPN site scoreboard-feed."""
    data = _read_json_url(ESPN_SCOREBOARD_URL)
    games: list[Game] = []

    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        def team_name(c: dict) -> str:
            t = c.get("team") or {}
            return t.get("displayName") or t.get("name") or t.get("shortDisplayName") or "TBD"

        status_type = ((event.get("status") or {}).get("type") or {})
        completed = bool(status_type.get("completed"))
        status = status_type.get("description") or status_type.get("name") or ""

        raw_date = event.get("date")
        if not raw_date:
            continue
        start_utc = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).astimezone(timezone.utc)

        venue = None
        if comp.get("venue"):
            venue = comp["venue"].get("fullName") or (comp["venue"].get("address") or {}).get("city")

        stage = None
        if event.get("season", {}).get("type"):
            stage = str(event["season"]["type"])

        games.append(Game(
            id=str(event.get("id")),
            start_utc=start_utc,
            home=team_name(home),
            away=team_name(away),
            home_score=_score(home.get("score")),
            away_score=_score(away.get("score")),
            completed=completed,
            status=status,
            stage=stage,
            venue=venue,
        ))

    return games

def fetch_games() -> list[Game]:
    """Centrale ingang. Later kunnen we hier een officiële FIFA-feed aan toevoegen."""
    return fetch_espn_games()
