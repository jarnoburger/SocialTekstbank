"""Naamconventie voor werkmappen: 'JJJJ Naam' of 'JJJJ-JJJJ Naam', Title Case.

- Jaartal vooraan: één jaar of een bereik. Volledige datums (2022-03-01) worden het jaar.
- Elk woord met hoofdletter, behalve korte verbindingswoorden (niet als eerste woord).
- Bestaande hoofdletters binnen een woord blijven staan (EyeBox, TodaysArt, QVC, LG G2).
- Vaste correcties via VASTE_NAMEN.
"""
import re

KLEINE_WOORDEN = {"en", "de", "het", "een", "van", "uit", "in", "op", "met", "voor", "bij", "aan",
                  "the", "of", "at", "a", "an", "and", "for", "to", "on", "by"}
VASTE_NAMEN = {"ijsalfabet": "IJsalfabet", "bmr": "BMR", "qvc": "QVC", "lg": "LG", "tu": "TU",
               "qdance": "QDance", "slider": "Slider", "visuals": "Visuals", "floyd": "Floyd",
               "coding": "Coding"}

_PREFIX_RE = re.compile(r"^((?:19|20)\d{2})(?:-(\d{2})-(\d{2})|[-–]((?:19|20)\d{2}))?\s+(.*)$")


def splits(mapnaam):
    """-> (jaar_label of '', naam)"""
    m = _PREFIX_RE.match(mapnaam.strip())
    if not m:
        return "", mapnaam.strip()
    j1, _, _, j2, rest = m.groups()
    return (f"{j1}-{j2}" if j2 else j1), rest.strip()


def _woord(w, eerste):
    laag = w.lower()
    if laag in VASTE_NAMEN:
        return VASTE_NAMEN[laag]
    if not eerste and laag in KLEINE_WOORDEN and w.islower():
        return w  # verbindingswoord dat al klein is, blijft klein
    if len(w) > 2 and w[0].islower() and any(c.isupper() for c in w[1:]):
        return w.capitalize()  # cODING -> Coding
    if w[0].islower():
        return w[0].upper() + w[1:]
    return w  # bestaande hoofdletters (EyeBox, TodaysArt, Plugged In) blijven


def title_case(naam):
    return " ".join(_woord(w, i == 0) for i, w in enumerate(naam.split()))


def voorstel(mapnaam, jaar=None):
    """Genormaliseerde mapnaam. jaar = optioneel jaarlabel als de map er nog geen heeft."""
    j, naam = splits(mapnaam)
    j = j or (jaar or "")
    naam = title_case(naam)
    return f"{j} {naam}".strip()
