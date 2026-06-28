"""
build_calendar.py – WK 2026 iCal generator (schone versie, geen legacy-afhankelijkheid)

Bouwt wk2026.ics volledig opnieuw op vanuit de ESPN API.
Bestaand bestand wordt alleen gebruikt om eerder toegewezen UIDs te hergebruiken
(zodat agenda-abonnees geen dubbele events krijgen). De matching gebeurt
UITSLUITEND op ESPN wedstrijd-ID – nooit op tijdstip of teamnaam.

NOS Sport YouTube playlist wordt gebruikt om samenvattingen toe te voegen
aan afgelopen wedstrijden (vereist YT_API_KEY omgevingsvariabele).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
ICS_PATH = ROOT / "wk2026.ics"
TEAMS_PATH = ROOT / "data" / "teams_nl.json"

AMSTERDAM = ZoneInfo("Europe/Amsterdam")

ESPN_URL = os.environ.get(
    "ESPN_SCOREBOARD_URL",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
    "?dates=20260611-20260719&limit=300",
)

NOS_PLAYLIST_ID = "PLnJJ42LOJsdHCqcsxa9fl9jZgmUqcMjbu"
YT_API_KEY = os.environ.get("YT_API_KEY", "")

CALENDAR_HEADER = """\
BEGIN:VCALENDAR
CALSCALE:GREGORIAN
PRODID:-//Ronald Dolman//WK 2026 iCal NL//NL
VERSION:2.0
METHOD:PUBLISH
X-WR-CALNAME:WK 2026 Speelschema NL
X-WR-TIMEZONE:Europe/Amsterdam
BEGIN:VTIMEZONE
TZID:Europe/Amsterdam
BEGIN:DAYLIGHT
DTSTART:19810329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
TZNAME:CEST
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:19961027T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
TZNAME:CET
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
END:STANDARD
END:VTIMEZONE
"""

CALENDAR_FOOTER = "END:VCALENDAR\r\n"

# ---------------------------------------------------------------------------
# Vertaling
# ---------------------------------------------------------------------------

TEAMS: dict = json.loads(TEAMS_PATH.read_text(encoding="utf-8"))

STATUS_NL = {
    "Scheduled": "Gepland",
    "In Progress": "Bezig",
    "Half Time": "Rust",
    "First Half": "Eerste helft",
    "Second Half": "Tweede helft",
    "Full Time": "Afgelopen",
    "Final": "Afgelopen",
    "Postponed": "Uitgesteld",
    "Canceled": "Geannuleerd",
    "Suspended": "Gestaakt",
}


def team_nl(name: str | None, with_emoji: bool = False) -> str:
    if not name:
        return "Nog te bepalen"
    info = TEAMS.get(name.strip())
    if not info:
        return name.strip()
    if with_emoji:
        emoji = info.get("emoji", "").strip()
        return f"{emoji} {info['nl']}".strip() if emoji else info["nl"]
    return info["nl"]


def team_nl_name(name: str | None) -> str:
    """Geeft alleen de Nederlandse naam terug (zonder emoji), voor matching."""
    if not name:
        return ""
    info = TEAMS.get(name.strip())
    return info["nl"] if info else name.strip()


def matchup_title(home: str, away: str, home_score: int | None,
                  away_score: int | None, completed: bool) -> str:
    h = team_nl(home, with_emoji=True)
    a = team_nl(away, with_emoji=True)
    if completed and home_score is not None and away_score is not None:
        return f"WK: {h} - {a} ({home_score}\u2013{away_score})"
    return f"WK: {h} - {a}"


# ---------------------------------------------------------------------------
# ESPN ophalen
# ---------------------------------------------------------------------------

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
    venue: str | None
    city: str | None


def fetch_games() -> list[Game]:
    req = urllib.request.Request(
        ESPN_URL, headers={"User-Agent": "rdolman-wk2026-ical-nl/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())

    games: list[Game] = []
    seen_ids: set[str] = set()

    for event in data.get("events", []):
        espn_id = str(event.get("id", ""))
        if not espn_id or espn_id in seen_ids:
            continue
        seen_ids.add(espn_id)

        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        def tname(c: dict) -> str:
            t = c.get("team") or {}
            return (t.get("displayName") or t.get("name") or
                    t.get("shortDisplayName") or "TBD")

        def score(c: dict) -> int | None:
            try:
                return int(c.get("score"))
            except (TypeError, ValueError):
                return None

        st = (event.get("status") or {}).get("type") or {}
        completed = bool(st.get("completed"))
        status_raw = st.get("description") or st.get("name") or ""
        status = STATUS_NL.get(status_raw, status_raw)

        raw_date = event.get("date")
        if not raw_date:
            continue
        start_utc = datetime.fromisoformat(
            raw_date.replace("Z", "+00:00")
        ).astimezone(timezone.utc)

        venue_obj = comp.get("venue") or {}
        venue = venue_obj.get("fullName")
        city = (venue_obj.get("address") or {}).get("city")

        games.append(Game(
            id=espn_id,
            start_utc=start_utc,
            home=tname(home),
            away=tname(away),
            home_score=score(home),
            away_score=score(away),
            completed=completed,
            status=status,
            venue=venue,
            city=city,
        ))

    return sorted(games, key=lambda g: g.start_utc)


# ---------------------------------------------------------------------------
# NOS Sport YouTube playlist ophalen via YouTube Data API v3
# ---------------------------------------------------------------------------

@dataclass
class NosVideo:
    title: str
    url: str
    published: datetime


def fetch_nos_videos() -> list[NosVideo]:
    """Haalt ALLE video's op uit de NOS Sport WK2026 playlist via YouTube Data API v3."""
    if not YT_API_KEY:
        print("Geen YT_API_KEY gevonden, NOS samenvattingen overgeslagen.")
        return []

    videos: list[NosVideo] = []
    next_page_token = None

    while True:
        params = {
            "part": "snippet",
            "playlistId": NOS_PLAYLIST_ID,
            "maxResults": "50",
            "key": YT_API_KEY,
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        url = "https://www.googleapis.com/youtube/v3/playlistItems?" + urllib.parse.urlencode(params)

        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "rdolman-wk2026-ical-nl/5.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            print(f"YouTube API fout: {e}")
            break

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            video_id = snippet.get("resourceId", {}).get("videoId", "")
            published_str = snippet.get("publishedAt", "")

            if not video_id or not title:
                continue

            # Sla privé/verwijderde video's over
            if title in ("Deleted video", "Private video"):
                continue

            try:
                published = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except ValueError:
                continue

            videos.append(NosVideo(
                title=title,
                url=f"https://www.youtube.com/watch?v={video_id}",
                published=published,
            ))

        # Volgende pagina ophalen indien beschikbaar
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    print(f"{len(videos)} NOS Sport video's opgehaald uit playlist.")
    return videos


def find_nos_summary(game: Game, videos: list[NosVideo]) -> str | None:
    """
    Zoekt een NOS samenvatting voor een wedstrijd.
    Titel formaat: "Samenvatting {Team A} - {Team B} | ..."
    Matching op Nederlandse teamnamen, gepubliceerd na de wedstrijd.
    """
    if not game.completed:
        return None

    home_nl = team_nl_name(game.home).lower()
    away_nl = team_nl_name(game.away).lower()

    # Wedstrijd eindigt ongeveer 2 uur na aftrap
    game_end_utc = game.start_utc + timedelta(hours=2)

    for video in videos:
        title_lower = video.title.lower()

        # Moet beginnen met "samenvatting"
        if not title_lower.startswith("samenvatting"):
            continue

        # Moet na de wedstrijd gepubliceerd zijn
        if video.published < game_end_utc:
            continue

        # Beide teamnamen moeten in de titel voorkomen
        if home_nl in title_lower and away_nl in title_lower:
            return video.url

    return None


# ---------------------------------------------------------------------------
# Bestaande UIDs en sequences ophalen
# ---------------------------------------------------------------------------

def load_existing_uids(path: Path) -> dict[str, str]:
    """Geeft {espn_id: uid} terug voor events die al een UID hebben."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]", "", text)

    result: dict[str, str] = {}
    for block in re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, re.S):
        uid_m = re.search(r"^UID:(.+)$", block, re.M)
        espn_m = re.search(r"(?:espn-|Wedstrijd-id:\s*)([0-9]+)", block)
        if uid_m and espn_m:
            espn_id = espn_m.group(1)
            uid = uid_m.group(1).strip()
            if espn_id not in result:
                result[espn_id] = uid
    return result


def load_existing_sequences(path: Path) -> dict[str, int]:
    """Geeft {espn_id: sequence} terug zodat we de teller ophogen."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]", "", text)

    result: dict[str, int] = {}
    for block in re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, re.S):
        espn_m = re.search(r"(?:espn-|Wedstrijd-id:\s*)([0-9]+)", block)
        seq_m = re.search(r"^SEQUENCE:(\d+)$", block, re.M)
        if espn_m and seq_m:
            espn_id = espn_m.group(1)
            seq = int(seq_m.group(1))
            if espn_id not in result or seq > result[espn_id]:
                result[espn_id] = seq + 1
    return result


# ---------------------------------------------------------------------------
# iCal hulpfuncties
# ---------------------------------------------------------------------------

def ical_escape(value: str) -> str:
    return (value
            .replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n"))


def fold(line: str) -> str:
    """Vouw lange iCal-regels op 75 bytes."""
    result: list[str] = []
    b = line.encode("utf-8")
    while len(b) > 75:
        cut = 75
        while cut > 0:
            try:
                part = b[:cut].decode("utf-8")
                break
            except UnicodeDecodeError:
                cut -= 1
        result.append(part)
        b = (" " + b[cut:].decode("utf-8")).encode("utf-8")
    result.append(b.decode("utf-8"))
    return "\r\n".join(result)


def fmt_dt(dt: datetime) -> str:
    return dt.astimezone(AMSTERDAM).strftime("%Y%m%dT%H%M%S")


def fmt_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Event bouwen
# ---------------------------------------------------------------------------

def build_event(game: Game, uid: str, now: str, sequence: int,
                nos_url: str | None = None) -> str:
    start = fmt_dt(game.start_utc)
    end = fmt_dt(game.start_utc + timedelta(hours=2))
    summary = matchup_title(
        game.home, game.away,
        game.home_score, game.away_score,
        game.completed,
    )

    desc_lines = [
        "Live bron: ESPN",
        f"Wedstrijd-id: {game.id}",
        f"Status: {game.status}",
    ]
    if game.venue:
        desc_lines.append(f"Locatie: {game.venue}")
    if nos_url:
        desc_lines.append(f"Samenvatting: {nos_url}")

    description = "\\n".join(desc_lines)
    location = ical_escape(game.venue or (game.city or ""))

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"LAST-MODIFIED:{now}",
        f"DTSTART;TZID=Europe/Amsterdam:{start}",
        f"DTEND;TZID=Europe/Amsterdam:{end}",
        f"SUMMARY:{ical_escape(summary)}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{location}",
        f"SEQUENCE:{sequence}",
        "TRANSP:OPAQUE",
    ]

    if nos_url:
        lines.append(f"URL:{nos_url}")

    lines.append("END:VEVENT")
    return "\r\n".join(fold(line) for line in lines)


# ---------------------------------------------------------------------------
# Hoofdfunctie
# ---------------------------------------------------------------------------

def build_calendar(games: list[Game], existing_uids: dict[str, str],
                   existing_sequences: dict[str, int],
                   nos_videos: list[NosVideo]) -> str:
    now = fmt_now()
    events: list[str] = []
    nos_found = 0

    for game in games:
        uid = existing_uids.get(game.id, f"wk2026-espn-{game.id}@rdolman.github.io")
        seq = existing_sequences.get(game.id, 0)
        nos_url = find_nos_summary(game, nos_videos)
        if nos_url:
            nos_found += 1
        events.append(build_event(game, uid, now, seq, nos_url))

    print(f"{nos_found} wedstrijden hebben een NOS samenvatting.")
    body = "\r\n".join(events)
    return CALENDAR_HEADER.replace("\n", "\r\n") + body + "\r\n" + CALENDAR_FOOTER


def main() -> None:
    print("ESPN-data ophalen…")
    games = fetch_games()
    print(f"{len(games)} wedstrijden opgehaald.")

    existing_uids = load_existing_uids(ICS_PATH)
    existing_sequences = load_existing_sequences(ICS_PATH)
    print(f"{len(existing_uids)} bestaande UIDs geladen.")

    print("NOS Sport playlist ophalen…")
    nos_videos = fetch_nos_videos()

    new_ics = build_calendar(games, existing_uids, existing_sequences, nos_videos)

    if ICS_PATH.exists():
        old_ics = ICS_PATH.read_text(encoding="utf-8", errors="replace")
        if old_ics == new_ics:
            print("Geen wijzigingen.")
            return

    ICS_PATH.write_text(new_ics, encoding="utf-8", newline="")
    print(f"wk2026.ics bijgewerkt met {len(games)} events.")


if __name__ == "__main__":
    main()