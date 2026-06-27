from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .sources import Game
from .translate import matchup_title, translate_text

AMSTERDAM = ZoneInfo("Europe/Amsterdam")


def unfold_ics(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n[ \t]", "", text)


def fold_ics(text: str) -> str:
    result: list[str] = []

    for line in text.split("\n"):
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

    return "\r\n".join(result).rstrip() + "\r\n"


def get_prop(block: str, name: str) -> str | None:
    m = re.search(rf"^{re.escape(name)}(?:;[^:]*)?:(.*)$", block, flags=re.M)
    return m.group(1) if m else None


def set_prop(block: str, name: str, value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )
    line = f"{name}:{escaped}"
    pattern = rf"^{re.escape(name)}(?:;[^:]*)?:.*$"

    if re.search(pattern, block, flags=re.M):
        return re.sub(pattern, line, block, count=1, flags=re.M)

    return line + "\n" + block


def set_raw_prop(block: str, name: str, value: str) -> str:
    line = f"{name}:{value}"
    pattern = rf"^{re.escape(name)}(?:;[^:]*)?:.*$"

    if re.search(pattern, block, flags=re.M):
        return re.sub(pattern, line, block, count=1, flags=re.M)

    return line + "\n" + block


def event_start(block: str) -> datetime | None:
    m = re.search(
        r"^DTSTART(?:;TZID=Europe/Amsterdam)?:(\d{8}T\d{6})$",
        block,
        flags=re.M,
    )
    if not m:
        return None

    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=AMSTERDAM)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""

    value = translate_text(value)
    value = value.lower()
    value = value.replace("wk 2026:", "").replace("wk:", "")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\d+\s*[–:-]\s*\d+", " ", value)
    value = re.sub(r"[^a-z0-9À-ÿ\s-]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def _event_identity_text(block: str) -> str:
    parts = [
        get_prop(block, "SUMMARY") or "",
        get_prop(block, "DESCRIPTION") or "",
        get_prop(block, "LOCATION") or "",
    ]
    return _clean_text(" ".join(parts))


def _game_team_names(game: Game) -> tuple[str, str]:
    return _clean_text(game.home), _clean_text(game.away)


def _contains_team(text: str, team: str) -> bool:
    if not text or not team:
        return False

    # Exact substring works for most teams after translation.
    if team in text:
        return True

    # For longer names, allow all meaningful words to appear in any order.
    words = [w for w in team.split() if len(w) >= 4]
    if len(words) >= 2 and all(w in text for w in words):
        return True

    return False


def best_game_for_event(
    block: str,
    games: list[Game],
    used_game_ids: set[str],
) -> Game | None:
    """Find the best source game for a VEVENT.

    The important bit: do not match purely on time when several matches kick off
    simultaneously. Prefer team-name and location evidence, and never reuse the
    same source game for two calendar events in one update run.
    """

    start = event_start(block)
    if not start:
        return None

    start_utc = start.astimezone(timezone.utc)
    event_text = _event_identity_text(block)
    event_location = _clean_text(get_prop(block, "LOCATION") or "")

    candidates: list[tuple[int, Game]] = []

    for game in games:
        if game.id in used_game_ids:
            continue

        diff = abs((game.start_utc - start_utc).total_seconds())
        if diff > 4 * 3600:
            continue

        home_nl, away_nl = _game_team_names(game)

        home_match = _contains_team(event_text, home_nl)
        away_match = _contains_team(event_text, away_nl)
        name_matches = int(home_match) + int(away_match)

        venue_match = False
        if game.venue:
            venue = _clean_text(game.venue)
            venue_match = bool(venue and (venue in event_text or venue in event_location))

        # If we have no team evidence and no venue evidence, do not attach this
        # source game. This avoids duplicate matches at the same kickoff time.
        if name_matches == 0 and not venue_match:
            continue

        score = int(diff)

        # Strongly prefer team-name evidence.
        score -= name_matches * 100_000

        # Venue is helpful, but team names are more reliable.
        if venue_match:
            score -= 25_000

        candidates.append((score, game))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]


def update_ics_text(text: str, games: list[Game]) -> tuple[str, int]:
    text = unfold_ics(text)
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    text = re.sub(
        r"^PRODID:.*$",
        "PRODID:-//Ronald Dolman//WK 2026 iCal NL//NL",
        text,
        flags=re.M,
    )

    if "METHOD:PUBLISH" not in text:
        text = text.replace("VERSION:2.0", "VERSION:2.0\nMETHOD:PUBLISH", 1)

    if "X-WR-TIMEZONE:" not in text:
        text = text.replace(
            "BEGIN:VCALENDAR",
            "BEGIN:VCALENDAR\nX-WR-TIMEZONE:Europe/Amsterdam",
            1,
        )

    if "X-WR-CALNAME:" in text:
        text = re.sub(
            r"^X-WR-CALNAME:.*$",
            "X-WR-CALNAME:WK 2026 Speelschema NL",
            text,
            flags=re.M,
        )
    else:
        text = text.replace(
            "BEGIN:VCALENDAR",
            "BEGIN:VCALENDAR\nX-WR-CALNAME:WK 2026 Speelschema NL",
            1,
        )

    events = re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, flags=re.S)
    updated: list[str] = []
    changed = 0
    used_game_ids: set[str] = set()

    for block in events:
        before = block
        game = best_game_for_event(block, games, used_game_ids)

        if game:
            used_game_ids.add(game.id)

            block = set_prop(
                block,
                "SUMMARY",
                matchup_title(
                    game.home,
                    game.away,
                    game.home_score,
                    game.away_score,
                    game.completed,
                ),
            )

            desc = translate_text(get_prop(block, "DESCRIPTION") or "")
            additions = [
                "Live bron: ESPN",
                f"Wedstrijd-id: {game.id}",
            ]

            if game.status:
                additions.append(f"Status: {game.status}")

            if game.venue:
                additions.append(f"Bronlocatie: {game.venue}")

            if "Wedstrijd-id:" not in desc:
                desc = desc + ("\n" if desc else "") + "\n".join(additions)

            block = set_prop(block, "DESCRIPTION", desc)

            if game.venue:
                block = set_prop(block, "LOCATION", game.venue)

        # Always translate any lingering English in the current event.
        block = set_prop(block, "SUMMARY", translate_text(get_prop(block, "SUMMARY") or ""))

        if get_prop(block, "DESCRIPTION"):
            block = set_prop(
                block,
                "DESCRIPTION",
                translate_text(get_prop(block, "DESCRIPTION") or ""),
            )

        if block != before:
            changed += 1
            try:
                seq = int(get_prop(block, "SEQUENCE") or "0") + 1
            except ValueError:
                seq = 1

            block = set_raw_prop(block, "SEQUENCE", str(seq))
            block = set_raw_prop(block, "LAST-MODIFIED", now)

        block = set_raw_prop(block, "DTSTAMP", now)
        updated.append("BEGIN:VEVENT\n" + block.strip() + "\nEND:VEVENT")

    iterator = iter(updated)
    text = re.sub(
        r"BEGIN:VEVENT\n.*?\nEND:VEVENT",
        lambda _m: next(iterator),
        text,
        flags=re.S,
    )

    return fold_ics(text), changed


def update_ics_file(path: Path, games: list[Game]) -> int:
    old = path.read_text(encoding="utf-8", errors="replace")
    new, changed = update_ics_text(old, games)

    if new != old:
        path.write_text(new, encoding="utf-8", newline="")

    return changed
