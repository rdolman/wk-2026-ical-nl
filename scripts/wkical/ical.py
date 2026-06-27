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
    escaped = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
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
    m = re.search(r"^DTSTART(?:;TZID=Europe/Amsterdam)?:(\d{8}T\d{6})$", block, flags=re.M)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=AMSTERDAM)

def normalized_summary(summary: str) -> str:
    s = summary.replace("WK 2026:", "")
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\d+\s*[–:-]\s*\d+", "", s)
    return s.lower().strip()

def best_game_for_event(block: str, games: list[Game]) -> Game | None:
    start = event_start(block)
    if not start:
        return None
    start_utc = start.astimezone(timezone.utc)
    summary = translate_text(normalized_summary(get_prop(block, "SUMMARY") or ""))

    best: tuple[int, Game] | None = None
    for game in games:
        diff = abs((game.start_utc - start_utc).total_seconds())
        if diff > 4 * 3600:
            continue
        score = int(diff)
        # Small preference for already matching team names.
        title = matchup_title(game.home, game.away).lower()
        if any(part in title for part in summary.split(" vs ")):
            score -= 1800
        if best is None or score < best[0]:
            best = (score, game)
    return best[1] if best else None

def update_ics_text(text: str, games: list[Game]) -> tuple[str, int]:
    text = unfold_ics(text)
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    text = re.sub(r"^PRODID:.*$", "PRODID:-//Ronald Dolman//WK 2026 iCal NL//NL", text, flags=re.M)
    if "METHOD:PUBLISH" not in text:
        text = text.replace("VERSION:2.0", "VERSION:2.0\nMETHOD:PUBLISH", 1)
    if "X-WR-TIMEZONE:" not in text:
        text = text.replace("BEGIN:VCALENDAR", "BEGIN:VCALENDAR\nX-WR-TIMEZONE:Europe/Amsterdam", 1)
    if "X-WR-CALNAME:" in text:
        text = re.sub(r"^X-WR-CALNAME:.*$", "X-WR-CALNAME:WK 2026 Speelschema NL", text, flags=re.M)
    else:
        text = text.replace("BEGIN:VCALENDAR", "BEGIN:VCALENDAR\nX-WR-CALNAME:WK 2026 Speelschema NL", 1)

    events = re.findall(r"BEGIN:VEVENT\n(.*?)\nEND:VEVENT", text, flags=re.S)
    updated: list[str] = []
    changed = 0

    for block in events:
        before = block
        game = best_game_for_event(block, games)
        if game:
            block = set_prop(block, "SUMMARY", matchup_title(game.home, game.away, game.home_score, game.away_score, game.completed))
            desc = translate_text(get_prop(block, "DESCRIPTION") or "")
            additions = [
                f"Live bron: ESPN",
                f"Wedstrijd-id: {game.id}",
            ]
            if game.status:
                additions.append(f"Status: {game.status}")
            if game.venue:
                additions.append(f"Bronlocatie: {game.venue}")
            if "Wedstrijd-id:" not in desc:
                desc = desc + ("\n" if desc else "") + "\n".join(additions)
            block = set_prop(block, "DESCRIPTION", desc)
            if game.venue and not get_prop(block, "LOCATION"):
                block = set_prop(block, "LOCATION", game.venue)

        # Always translate lingering English in current event.
        block = set_prop(block, "SUMMARY", translate_text(get_prop(block, "SUMMARY") or ""))
        if get_prop(block, "DESCRIPTION"):
            block = set_prop(block, "DESCRIPTION", translate_text(get_prop(block, "DESCRIPTION") or ""))

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
    text = re.sub(r"BEGIN:VEVENT\n.*?\nEND:VEVENT", lambda m: next(iterator), text, flags=re.S)
    return fold_ics(text), changed

def update_ics_file(path: Path, games: list[Game]) -> int:
    old = path.read_text(encoding="utf-8", errors="replace")
    new, changed = update_ics_text(old, games)
    if new != old:
        path.write_text(new, encoding="utf-8", newline="")
    return changed
