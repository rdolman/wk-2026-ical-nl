# WK 2026 Speelschema NL 🇳🇱⚽

Een abonneerbare agenda met alle 104 wedstrijden van het FIFA Wereldkampioenschap voetbal 2026, automatisch bijgewerkt met live uitslagen en links naar NOS Sport samenvattingen.

## Wat doet het?

- 📅 **Alle wedstrijden** — van de poulefase tot en met de finale, inclusief locatie en speeltijd in Nederlandse tijd
- 🔄 **Live uitslagen** — elk uur automatisch bijgewerkt via de ESPN API
- 🎬 **NOS samenvattingen** — na afloop van elke wedstrijd verschijnt automatisch een link naar de samenvatting op YouTube
- 🏆 **Knock-outfase** — tegenstanders worden automatisch bijgewerkt zodra de poulestand bekend is

## Abonneren

Voeg de volgende URL toe als agenda-abonnement in Apple Calendar, Google Calendar of Outlook:

```
https://rdolman.github.io/wk-2026-ical-nl/wk2026.ics
```

**Apple Calendar:** Archief → Abonnement op kalender → URL plakken  
**Google Calendar:** Andere agenda's → Via URL → URL plakken  
**Outlook:** Agenda toevoegen → Via internet → URL plakken

> 💡 Stel de verversfrequentie in op "elk kwartier" of "elk uur" voor de meest actuele uitslagen.

## Hoe werkt het?

Een GitHub Actions workflow draait elk uur en haalt live data op via de ESPN API en de NOS Sport YouTube playlist. Het resultaat wordt als `.ics` bestand gepubliceerd via GitHub Pages.

```
ESPN API → uitslagen & wedstrijddata
NOS Sport YouTube → links naar samenvattingen
        ↓
GitHub Actions (elk uur)
        ↓
wk2026.ics → GitHub Pages
        ↓
Jouw agenda-app
```

## Technische details

- **Taal:** Python 3.12
- **Data:** [ESPN API](https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard)
- **Samenvattingen:** [NOS Sport YouTube](https://www.youtube.com/@nossport)
- **Schema:** Elk uur via GitHub Actions
- **Formaat:** iCalendar (RFC 5545), tijdzone Europe/Amsterdam

## Licentie

MIT — vrij te gebruiken en aan te passen.