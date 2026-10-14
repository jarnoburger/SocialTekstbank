# SocialTekstbank

> **Bevroren 2026-10-14:** fase 2 (Nieuw, Plannen, Planning, Posten) is verhuisd naar Honey (stap 11b, Social-tab). Deze app nog alleen voor fase 1 (aanvullen). Export voor Honey: `python tools\export_voor_honey.py`.

Lokale web-app die de **tekst bij je werk** verzamelt en je socials (SJB en Lichtjes, IG en FB) controleert.

- **Lokaal:** scant de `_To Promote`-mappen en laat per werk zien of er een korte tekst, een lange tekst en een caption is.
- **Online:** haalt alle posts op via de Meta Graph API en laat zien welke posts geen caption hebben.
- **Koppelen:** verbindt een post met een werk. De caption gaat automatisch naar de lokale tekstbank (dat is het oogsten).
- **Export:** één `Tekstbank.md` met alle teksten, voor portfolio, bio en aanvragen.

## Starten
Dubbelklik `start.bat` en open http://127.0.0.1:5077. Ontbrekende packages (flask, pillow, requests) worden de eerste keer zelf geïnstalleerd.

## Waar staat wat
| Bestand | Plek | Inhoud |
|---|---|---|
| `_tekst.md` | in elke projectmap | Titel, Jaar en plek, Kort, Lang, Caption NL/EN, Hashtags, Credits, tekst per bestand, eerdere captions. **Dit is de bron van waarheid.** Te bewerken in elke editor. |
| `_social.json` | in een projectmap | Spiegel van de gekoppelde posts (link, datum, caption) |
| `_project.yml` | in een projectmap | Bestaande portfolio-kaart. Wordt alleen gelezen, nooit aangepast. |
| `data\config.json` | app-map | Meta-tokens en mapinstellingen. **Privé, niet delen.** |
| `data\online.json` | app-map | Laatst opgehaalde posts |
| `data\links.json` | app-map | Koppelingen post → werk |
| `data\hashes.json`, `data\thumbs\` | app-map | Caches. Mag je weggooien. |

## Hoe een werk wordt herkend
- Een map met `_project.yml` is een werk.
- In de containermappen `Done`, `ToDo`, `_ToDo` en `1` is elke submap een werk.
- Losse media direct in een containermap vormen samen "Losse bestanden (…)".
- Codemappen (`.git`, `lib`, `node_modules`, …) worden overgeslagen.

## Matching (voorstellen voor koppelen)
| Signaal | Gewicht |
|---|---|
| Caption staat al in `_tekst.md` | zeker |
| Woord uit map- of projectnaam staat in de caption | sterk |
| Datum in een bestandsnaam (`jarnoburger-20250411_…`) ligt binnen 3 dagen van de post | middel |
| Beeld gelijk (dHash) | sterk, alleen na *Voorstellen verbeteren* |

**OneDrive:** ongeveer 93% van de bestanden staat alleen online. De app opent die bestanden niet, behalve als jij per werk op *Previews laden* of *Beelden vergelijken* klikt. Dan downloadt OneDrive alleen dat werk.

## Onderhoud
- De pagina-tokens verlopen in principe niet. Ze worden ongeldig als je je FB-wachtwoord wijzigt of de app-rechten intrekt. Dan doe je de installatie bij Instellingen opnieuw.
- Faseert Meta de API-versie uit, verhoog dan de versie bij Instellingen (bijv. `v25.0` → `v26.0`).

## Modules
`core/local.py` scanner · `core/textfile.py` _tekst.md · `core/meta.py` Graph API · `core/match.py` matcher · `app.py` web-UI
