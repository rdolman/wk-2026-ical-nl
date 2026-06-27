# WK 2026 iCal NL

Live iCal-kalender voor het WK 2026-speelschema in Nederlandse aanduiding.

## Agenda-URL

```text
https://rdolman.github.io/wk-2026-ical-nl/wk2026.ics
```

Gebruik in Apple Agenda bij voorkeur **Nieuw agenda-abonnement** in plaats van importeren.

## Wat doet deze repository?

- `wk2026.ics` is het kalenderbestand dat GitHub Pages publiceert.
- `scripts/build_calendar.py` haalt actuele wedstrijdinformatie op.
- `scripts/wkical/translate.py` zet teamnamen om naar het Nederlands.
- `.github/workflows/update-calendar.yml` draait automatisch elk uur.
- Alleen als `wk2026.ics` verandert, wordt er automatisch een commit gemaakt.

## Handmatig draaien via GitHub

Ga naar:

**Actions → Update WK 2026 kalender → Run workflow**

## GitHub Pages

Zet GitHub Pages aan via:

**Settings → Pages → Deploy from a branch → main → / (root)**

Daarna is de kalender beschikbaar op:

```text
https://rdolman.github.io/wk-2026-ical-nl/wk2026.ics
```

## Bron

De huidige versie gebruikt een publieke ESPN-scoreboardfeed. De bronlaag zit apart in `scripts/wkical/sources.py`, zodat later eenvoudig een officiële FIFA-feed kan worden toegevoegd als die stabiel beschikbaar is.
