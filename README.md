# WK 2026 iCal NL

Live iCal-kalender voor het WK 2026-speelschema in Nederlandse aanduiding.

Agenda-URL:

```text
https://rdolman.github.io/wk-2026-ical-nl/wk2026.ics
```

## Automatische updates

De GitHub Action `.github/workflows/update-calendar.yml` draait automatisch en kan ook handmatig worden gestart via **Actions → Update WK 2026 kalender → Run workflow**.

Het script:
- haalt actuele wedstrijdinformatie op;
- zet landnamen om naar het Nederlands;
- zet uitslagen in de titel zodra een wedstrijd is afgelopen;
- behoudt bestaande `UID`s zodat agenda-abonnementen netjes bijwerken.
