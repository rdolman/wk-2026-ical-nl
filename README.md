# WK 2026 iCal NL

Live iCal-kalender voor het WK 2026-speelschema in Nederlandse aanduiding.

## Agenda-URL

```text
https://rdolman.github.io/wk-2026-ical-nl/wk2026.ics
```

## v4

Vereenvoudigde matching: gebeurt uitsluitend op ESPN-ID. Niet meer op tijdstip, teamnaam of stad. Geen bestaand .ics als template nodig, de engine bouwt alles opnieuw op vanuit de ESPN-data, en hergebruikt alleen de UIDs van vorige runs zodat agenda-abonnees geen dubbele events krijgen.

Titelvorm:

```text
WK: 🇳🇱 Nederland - 🇲🇦 Marokko (3–1)
```

Voor nog niet gespeelde wedstrijden:

```text
WK: 🇳🇱 Nederland - 🇲🇦 Marokko
```
## Updates

Matching-script draait elk uur en update de agenda met uitslagen en nieuwe wedstrijden in de knock-out fase.

## Handmatig draaien

Kun je niet wachten en wil je gelijk de uitslagen in je agenda, 
ga dan naar **Actions → Update WK 2026 kalender → Run workflow**.
