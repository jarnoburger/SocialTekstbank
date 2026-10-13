"""Lezen en schrijven van _tekst.md: de tekstbank per werk (projectmap).

Formaat (mens-leesbaar, in elke editor te bewerken):

    ## Titel
    ...
    ## Kort
    ...
    ## Per bestand
    ### foto1.jpg
    tekst bij deze foto
    ## Eerdere captions
    ### ig · 2024-02-09 · https://instagram.com/p/...
    caption-tekst

Onbekende kopjes blijven behouden.
"""
import os

TEKST_NAAM = "_tekst.md"
HEADER = ("<!-- _tekst.md: tekstbank voor dit werk (SocialTekstbank). "
          "Vrij te bewerken; laat de ##-kopjes staan. -->")

# Volgorde = volgorde in bestand en editor.
VELDEN = [
    ("Titel", "Naam van het werk zoals je het naar buiten brengt"),
    ("Jaar en plek", "Bijv. 2005, Ruigoord (LandJuweel)"),
    ("Kort", "1-2 zinnen: wat is het? (bio, portfolio-onderschrift)"),
    ("Lang", "Een alinea: idee, techniek, jouw rol, publiek (voor aanvragen en website)"),
    ("Beeldbeschrijving", "Wat er op de beelden te zien is (voorzet van Claude, door jou te controleren)"),
    ("Caption NL", "Social-caption in het Nederlands"),
    ("Caption EN", "Social-caption in het Engels"),
    ("Hashtags", "#dome #fulldome ..."),
    ("Credits", "Samenwerking, opdrachtgever, fotograaf"),
    ("Crosslinks", "Festival, venue, opdrachtgever, kunstenaar: website + Instagram (om te taggen en te linken)"),
    ("Pers", "Artikelen, recensies, interviews over het werk of event: titel · medium · datum · link · waar het over gaat"),
]
VELD_NAMEN = [v for v, _ in VELDEN]
PER_BESTAND = "Per bestand"
EERDER = "Eerdere captions"


def pad_voor(projectmap):
    return os.path.join(projectmap, TEKST_NAAM)


def _split(text, marker):
    """Splits tekst op regels die met marker beginnen -> [(kop, inhoud)]."""
    blokken, kop, buf = [], None, []
    for regel in text.splitlines():
        if regel.startswith(marker) and not regel.startswith(marker + "#"):
            if kop is not None:
                blokken.append((kop, "\n".join(buf).strip()))
            kop, buf = regel[len(marker):].strip(), []
        elif kop is not None:
            buf.append(regel)
    if kop is not None:
        blokken.append((kop, "\n".join(buf).strip()))
    return blokken


def parse_text(text):
    data = {"velden": {}, "per_bestand": {}, "eerder": [], "overig": []}
    for kop, inhoud in _split(text, "## "):
        if kop == PER_BESTAND:
            data["per_bestand"] = {k: v for k, v in _split(inhoud, "### ") if v}
        elif kop == EERDER:
            data["eerder"] = [{"kop": k, "tekst": v} for k, v in _split(inhoud, "### ")]
        elif kop in VELD_NAMEN:
            data["velden"][kop] = inhoud
        else:
            data["overig"].append((kop, inhoud))
    return data


def lees(projectmap):
    p = pad_voor(projectmap)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8-sig") as f:
        return parse_text(f.read())


def leeg():
    return {"velden": {}, "per_bestand": {}, "eerder": [], "overig": []}


def render(data):
    out = [HEADER, ""]
    for naam in VELD_NAMEN:
        out += [f"## {naam}", data["velden"].get(naam, "").strip(), ""]
    for kop, inhoud in data.get("overig", []):
        out += [f"## {kop}", inhoud, ""]
    out += [f"## {PER_BESTAND}"]
    for bestand, tekst in sorted(data.get("per_bestand", {}).items()):
        if tekst.strip():
            out += [f"### {bestand}", tekst.strip(), ""]
    out += ["", f"## {EERDER}"]
    for e in data.get("eerder", []):
        out += [f"### {e['kop']}", e["tekst"].strip(), ""]
    return "\n".join(out).rstrip() + "\n"


def schrijf(projectmap, data):
    p = pad_voor(projectmap)
    tekst = render(data)
    # Direct schrijven (geen tmp+replace): OneDrive verstoort os.replace.
    # Retry bij tijdelijke sync-lock; daarna verifiëren door terug te lezen.
    import time
    laatste_fout = None
    for poging in range(8):
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(tekst)
            with open(p, encoding="utf-8") as f:
                if f.read() == tekst:
                    break
        except PermissionError as e:
            laatste_fout = e
        time.sleep(0.25 * (poging + 1))
    else:
        raise laatste_fout or OSError(f"Schrijven niet geverifieerd: {p}")
    tmp = p + ".tmp"
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass


def status(data, n_media):
    """Samenvatting voor het dashboard."""
    if data is None:
        return {"bestaat": False, "kort": False, "lang": False, "caption": False,
                "per_bestand": 0, "score": 0}
    v = data["velden"]
    kort = bool(v.get("Kort", "").strip())
    lang = bool(v.get("Lang", "").strip())
    caption = bool(v.get("Caption NL", "").strip() or v.get("Caption EN", "").strip())
    pb = sum(1 for t in data["per_bestand"].values() if t.strip())
    score = int(kort) + int(lang) + int(caption)
    return {"bestaat": True, "kort": kort, "lang": lang, "caption": caption,
            "per_bestand": pb, "score": score}


def norm(s):
    return " ".join((s or "").lower().split())


def voeg_caption_toe(projectmap, platform, datum, permalink, caption):
    """Oogst een online caption naar de lokale tekstbank.

    - Caption NL leeg -> vullen.
    - Altijd bewaren onder 'Eerdere captions' (zonder dubbelingen).
    Geeft True terug als er iets veranderd is.
    """
    caption = (caption or "").strip()
    if not caption:
        return False
    data = lees(projectmap) or leeg()
    veranderd = False
    if not data["velden"].get("Caption NL", "").strip():
        data["velden"]["Caption NL"] = caption
        veranderd = True
    bestaand = {norm(e["tekst"]) for e in data["eerder"]}
    if norm(caption) not in bestaand:
        data["eerder"].append({"kop": f"{platform} · {datum} · {permalink}", "tekst": caption})
        veranderd = True
    if veranderd:
        schrijf(projectmap, data)
    return veranderd
