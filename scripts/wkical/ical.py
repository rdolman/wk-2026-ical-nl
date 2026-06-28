from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .sources import Game
from .translate import matchup_title, team_nl, translate_text

AMSTERDAM = ZoneInfo("Europe/Amsterdam")

@dataclass
class Event:
    block: str
    uid: str | None
    espn_id: str | None
    start: datetime | None
    summary: str
    location: str
    description: str

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

def remove_prop(block: str, name: str) -> str:
    return re.sub(rf"^{re.escape(name)}(?:;[^:]*)?:.*\n?", "", block, flags=re.M)

def event_start(block: str) -> datetime | None:
    m = re.search(r"^DTSTART(?:;TZID=Europe/Amsterdam)?:(\d{8}T\d{6})$", block, flags=re.M)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=AMSTERDAM)

def format_dt_local(dt: datetime) -> str:
    return dt.astimezone(AMSTERDAM).strftime("%Y%m%dT%H%M%S")

def parse_events(text: str) -> tuple[str, list[Event], str]:
    first = text.find("BEGIN:VEVENT")
    last = text.rfind("END:VEVENT")
    if first == -1 or last == -1:
        return text, [], ""
    prefix = text[:first]
    suffix = text[last + len("END:VEVENT"):]
    blocks = re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, flags=re.S)

    events: list[Event] = []
    for block in blocks:
        desc = get_prop(block, "DESCRIPTION") or ""
        espn_id = None
        m = re.search(r"(?:ESPN wedstrijd-id|Wedstrijd-id):\s*([0-9]+)", desc)
        if m:
            espn_id = m.group(1)
        uid = get_prop(block, "UID")
        # Existing v4-style UID can also carry the source id.
        if not espn_id and uid:
            m = re.search(r"espn-([0-9]+)@", uid)
            if m:
                espn_id = m.group(1)
        events.append(
            Event(
                block=block,
                uid=uid,
                espn_id=espn_id,
                start=event_start(block),
                summary=get_prop(block, "SUMMARY") or "",
                location=get_prop(block, "LOCATION") or "",
                description=desc,
            )
        )
    return prefix, events, suffix

def normalize(value: str | None) -> str:
    if not value:
        return ""
    value = translate_text(value).lower()
    value = value.replace("wk 2026:", "").replace("wk:", "")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\d+\s*[–:-]\s*\d+", " ", value)
    value = re.sub(r"[^a-z0-9À-ÿ\s-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()

def contains_team(text: str, team: str) -> bool:
    if not text or not team:
        return False
    if team in text:
        return True
    words = [w for w in team.split() if len(w) >= 4]
    return len(words) >= 2 and all(w in text for w in words)

def event_text(event: Event) -> str:
    return normalize(" ".join([event.summary, event.description, event.location]))

def game_home_away_nl(game: Game) -> tuple[str, str]:
    return normalize(team_nl(game.home)), normalize(team_nl(game.away))

def find_event_for_game(game: Game, events: list[Event], used_event_indexes: set[int]) -> int | None:
    # 1. Best path: source ID already embedded in previous runs.
    for i, event in enumerate(events):
        if i in used_event_indexes:
            continue
        if event.espn_id == game.id:
            return i

    game_start = game.start_utc.astimezone(AMSTERDAM)
    home_nl, away_nl = game_home_away_nl(game)

    # Check of er andere games zijn met exact hetzelfde starttijdstip
    simultaneous_game_starts = {
        g.start_utc for g in []  # wordt hieronder ingevuld
    }

    candidates: list[tuple[int, int]] = []

    for i, event in enumerate(events):
        if i in used_event_indexes or not event.start:
            continue

        diff = abs((event.start.astimezone(timezone.utc) - game.start_utc).total_seconds())
        if diff > 4 * 3600:
            continue

        text = event_text(event)
        home_match = contains_team(text, home_nl)
        away_match = contains_team(text, away_nl)
        name_matches = int(home_match) + int(away_match)

        venue_match = False
        if game.venue and normalize(game.venue) and normalize(game.venue) in text:
            venue_match = True
        if game.city and normalize(game.city) and normalize(game.city) in text:
            venue_match = True

        # Bij exact gelijktijdige wedstrijden (binnen 5 minuten): eis minstens één teamnaam
        is_simultaneous = diff < 300  # binnen 5 minuten
        if is_simultaneous and name_matches == 0:
            continue

        if name_matches == 0 and not venue_match:
            continue

        score = int(diff)
        score -= name_matches * 100_000
        if venue_match:
            score -= 25_000
        if name_matches == 2:
            score -= 100_000

        candidates.append((score, i))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]

def build_description(game: Game, old_description: str) -> str:
    # Keep user/source notes, but remove stale autogenerated live lines.
    old = translate_text(old_description)
    kept: list[str] = []
    for line in old.replace("\\n", "\n").splitlines():
        if line.startswith(("Live bron:", "Wedstrijd-id:", "ESPN wedstrijd-id:", "Status:", "Bronlocatie:")):
            continue
        if line.strip():
            kept.append(line.strip())

    additions = [
        "Live bron: ESPN",
        f"Wedstrijd-id: {game.id}",
    ]
    if game.status:
        additions.append(f"Status: {game.status}")
    if game.venue:
        additions.append(f"Bronlocatie: {game.venue}")

    return "\n".join(kept + additions)

def build_event_block(game: Game, old_event: Event | None, now: str) -> str:
    if old_event:
        block = old_event.block
        old_uid = old_event.uid
        old_description = old_event.description
    else:
        block = ""
        old_uid = None
        old_description = ""

    uid = old_uid or f"wk2026-espn-{game.id}@rdolman.github.io"
    start_local = format_dt_local(game.start_utc)
    end_local = format_dt_local(game.start_utc + timedelta(hours=2))

    block = set_raw_prop(block, "UID", uid)
    block = set_raw_prop(block, "DTSTAMP", now)
    block = set_raw_prop(block, "LAST-MODIFIED", now)
    block = set_raw_prop(block, "DTSTART;TZID=Europe/Amsterdam", start_local)
    block = set_raw_prop(block, "DTEND;TZID=Europe/Amsterdam", end_local)
    block = set_prop(
        block,
        "SUMMARY",
        matchup_title(game.home, game.away, game.home_score, game.away_score, game.completed),
    )
    block = set_prop(block, "DESCRIPTION", build_description(game, old_description))
    if game.venue:
        block = set_prop(block, "LOCATION", game.venue)

    try:
        seq = int(get_prop(block, "SEQUENCE") or "0") + 1
    except ValueError:
        seq = 1
    block = set_raw_prop(block, "SEQUENCE", str(seq))
    return block.strip()

def clean_unmatched_event(block: str, now: str) -> str:
    # Preserve future placeholders and unmatched events, but translate English and update metadata.
    before = block
    block = set_prop(block, "SUMMARY", translate_text(get_prop(block, "SUMMARY") or ""))
    if get_prop(block, "DESCRIPTION"):
        block = set_prop(block, "DESCRIPTION", translate_text(get_prop(block, "DESCRIPTION") or ""))
    if block != before:
        try:
            seq = int(get_prop(block, "SEQUENCE") or "0") + 1
        except ValueError:
            seq = 1
        block = set_raw_prop(block, "SEQUENCE", str(seq))
        block = set_raw_prop(block, "LAST-MODIFIED", now)
    block = set_raw_prop(block, "DTSTAMP", now)
    return block.strip()

def ensure_calendar_metadata(prefix: str) -> str:
    prefix = re.sub(
        r"^PRODID:.*$",
        "PRODID:-//Ronald Dolman//WK 2026 iCal NL//NL",
        prefix,
        flags=re.M,
    )
    if "METHOD:PUBLISH" not in prefix:
        prefix = prefix.replace("VERSION:2.0", "VERSION:2.0\nMETHOD:PUBLISH", 1)
    if "X-WR-TIMEZONE:" not in prefix:
        prefix = prefix.replace("BEGIN:VCALENDAR", "BEGIN:VCALENDAR\nX-WR-TIMEZONE:Europe/Amsterdam", 1)
    if "X-WR-CALNAME:" in prefix:
        prefix = re.sub(r"^X-WR-CALNAME:.*$", "X-WR-CALNAME:WK 2026 Speelschema NL", prefix, flags=re.M)
    else:
        prefix = prefix.replace("BEGIN:VCALENDAR", "BEGIN:VCALENDAR\nX-WR-CALNAME:WK 2026 Speelschema NL", 1)
    return prefix

def update_ics_text(text: str, games: list[Game]) -> tuple[str, int]:
    text = unfold_ics(text)
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix, events, suffix = parse_events(text)
    prefix = ensure_calendar_metadata(prefix)

    used_event_indexes: set[int] = set()
    rebuilt_blocks_by_index: dict[int, str] = {}
    new_blocks: list[str] = []

    games_sorted = sorted(games, key=lambda g: g.start_utc)

    for game in games_sorted:
        idx = find_event_for_game(game, events, used_event_indexes)
        if idx is not None:
            used_event_indexes.add(idx)
            rebuilt_blocks_by_index[idx] = build_event_block(game, events[idx], now)
        else:
            # Only create new events when a source game has no matching placeholder.
            # This is useful for late-added knockout games, and safe because UID is source-ID based.
            new_blocks.append(build_event_block(game, None, now))

    final_blocks: list[str] = []
    for i, event in enumerate(events):
        if i in rebuilt_blocks_by_index:
            final_blocks.append(rebuilt_blocks_by_index[i])
        else:
            final_blocks.append(clean_unmatched_event(event.block, now))

    final_blocks.extend(new_blocks)

    # De-duplicate by UID as a final safety net.
    seen_uids: set[str] = set()
    deduped_blocks: list[str] = []
    for block in final_blocks:
        uid = get_prop(block, "UID") or ""
        if uid and uid in seen_uids:
            continue
        if uid:
            seen_uids.add(uid)
        deduped_blocks.append("BEGIN:VEVENT\n" + block.strip() + "\nEND:VEVENT")

    body = "\n".join(deduped_blocks)
    new_text = prefix.rstrip() + "\n" + body + "\n" + suffix.lstrip()
    folded = fold_ics(new_text)
    changed = 1 if folded != fold_ics(text) else 0
    return folded, changed

def update_ics_file(path: Path, games: list[Game]) -> int:
    old = path.read_text(encoding="utf-8", errors="replace")
    new, changed = update_ics_text(old, games)
    if new != old:
        path.write_text(new, encoding="utf-8", newline="")
    return changed
