# Changelog

Alle wijzigingen in dit project worden in dit bestand bijgehouden.

## [5.3] - 2026-06-30

### Toegevoegd

- Ondersteuning voor verlenging en strafschoppen in de knock-outfase
- shootoutScore van ESPN wordt uitgelezen en getoond als "(1–1), 2–3 n.s." in de wedstrijdtitel
- matchup_title() herschreven om het volledige Game-object te gebruiken in plaats van losse parameters

## [5.2] - 2026-06-28

### Toegevoegd
- NOS Sport samenvattingen ophalen via YouTube Data API v3 in plaats van RSS feed
- Volledige playlist wordt opgehaald via paginering (niet meer beperkt tot 15 video's)
- YouTube API key wordt veilig opgeslagen als GitHub Secret (`YT_API_KEY`)

## [5.1] - 2026-06-28

### Toegevoegd
- NOS Sport YouTube RSS feed koppeling
- Na afloop van een wedstrijd verschijnt automatisch een link naar de samenvatting
- Link staat zowel in het `URL`-veld als in de beschrijving van het agenda-event

## [5.0] - 2026-06-28

### Toegevoegd
- Volledig nieuwe `build_calendar.py` — één zelfstandig script zonder legacy-afhankelijkheden
- Matching uitsluitend op ESPN wedstrijd-ID, nooit op tijdstip of teamnaam
- Automatische deduplicatie via ESPN-ID voorkomt dubbele wedstrijden
- Bestaande UIDs worden hergebruikt zodat agenda-abonnees geen dubbele events krijgen
- Correcte afhandeling van gelijktijdige poulewedstrijden (dag 3 per groep)

### Verwijderd
- `scripts/ical.py`, `scripts/sources.py`, `scripts/translate.py` — vervangen door `build_calendar.py`

## [4.0] - 2026-06-11

### Toegevoegd
- ESPN API koppeling voor live uitslagen
- GitHub Actions workflow voor automatische updates elk uur
- Nederlandse vertaling van teamnamen via `data/teams_nl.json`
- Emoji vlaggen per land
- Knock-outfase: tegenstanders automatisch bijgewerkt na poulefase

## [3.0] - 2026-06-07

### Toegevoegd
- Volledige wedstrijdkalender WK 2026 (104 wedstrijden)
- Locaties en speeltijden in Nederlandse tijd (Europe/Amsterdam)
- Abonneerbaar via GitHub Pages

## [1.0] - 2026-06-07

### Toegevoegd
- Initiële opzet van het project