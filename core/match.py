"""Koppelt online posts aan lokale werken.

Signalen (goedkoop eerst, omdat ~93% van de bestanden alleen in OneDrive staat):
1. Caption staat al in de lokale tekstbank            -> zeker
2. Woorden uit map-/projectnaam komen in de caption voor -> sterk
3. Datum in een lokale bestandsnaam (YYYYMMDD) ligt binnen 3 dagen van de post
4. Beeldvergelijking (dHash) van online thumbnails met LOKAAL aanwezige foto's
   (cloud-only foto's alleen als je per werk op 'Hash dit werk' klikt)
"""
import datetime as dt
import difflib
import io
import math
import os
import re

import requests
from PIL import Image

from . import config, textfile

STOPWOORDEN = {
    # mapnaam-ruis
    "done", "todo", "final", "edit", "edits", "losse", "bestanden", "media", "video", "videos",
    "foto", "fotos", "photo", "photos", "project", "projects", "kopie", "copy", "versie", "version",
    "nieuw", "nieuwe", "oude", "old", "new", "part", "deel", "test", "tests", "testing",
    # merk-woorden (staan overal)
    "jarno", "burger", "jarnoburger", "dome", "domes", "lichtjes", "studio", "lichtjesnl",
    # algemene woorden die in captions veel voorkomen
    "the", "and", "with", "from", "this", "that", "have", "about", "into", "over", "your",
    "van", "het", "een", "voor", "met", "bij", "naar", "maar", "ook", "nog", "wat", "deze", "die",
    "build", "building", "built", "work", "works", "working", "made", "make", "making", "days",
    "time", "first", "more", "other", "some", "here", "there", "light", "lights", "licht",
    "stage", "show", "shows", "live", "setup", "full", "home", "team", "event", "events",
    "festival", "art", "arts", "kunst", "visual", "visuals", "stuff", "thing", "things", "day",
    "week", "year", "years", "night", "today", "inside", "outside", "general", "real", "realtime",
    "control", "system", "systems", "room", "design", "render", "renders", "rendering", "concept",
    "creation", "model", "models", "shader", "shaders", "screen", "screens", "camera", "sound",
    "music", "game", "games", "local", "online", "series", "image", "images", "picture", "pictures",
    "3d", "2d", "4k", "hd", "vr", "ai",
}
# Gewone Nederlandse en Engelse woorden (vooral voor woorden die uit gekoppelde captions geleerd worden)
STOPWOORDEN |= set("""
aan als alle alles andere anders beetje been beter bijna binnen binnenkort daar daarna dan dat
dacht deed denk dingen doen door echt eerst eens eigen even fijn ging gaat gaan gedaan geen gemaakt
goed graag groot grote hadden heb hebben heeft hier hoe hun iets ik ivm jaar jaren jij jou jullie
kan keer klaar komen komt kon konden kunnen laat laten leuk lijken lijkt maken mee meer mijn
moet moeten mooi mooie naar niet niets nieuwe nooit nou nu omdat onder ons onze ooit open over
paar precies samen staan staat steeds tegen toch toen tot uit vanaf veel verder vind vinden vond
voor vooral waar waren was wel welke werd werken wie wij wil wilde wilt word worden wordt zal
zelf zeker zich zien zijn zitten zo zoals zou zouden zullen draaien podium helped help
again also always another anything around back because been before being best better between
both came can cant could did does doing done dont each even every feel find going gonna good got
great had has how just know last like little long look looking lot lots love many maybe much must
need never next nice now off only our out own people please pretty quite really right said same
see should since still such sure take than thank thanks them then they think those though thought
through too took under until very want was way well went were what when where which while who why
will wish would yeah yes yet you code old days""".split())
_DATUM_RE = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?:[_\-]\d{6})?(?!\d)")


# ---------- dHash ----------

def dhash_img(img, size=8):
    img = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(img.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (1 if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else 0)
    return bits


def afstand(a, b):
    return bin(a ^ b).count("1")


class HashCache:
    def __init__(self):
        self.data = config.load_json(config.HASHES_PATH, {"lokaal": {}, "online": {}})

    def save(self):
        config.save_json(config.HASHES_PATH, self.data)

    def lokaal(self, m, forceer=False):
        """Hash van een lokaal bestand; cloud-only alleen met forceer=True."""
        if m["type"] != "img":
            return None
        sleutel = f"{m['pad']}|{m['size']}|{int(m['mtime'])}"
        if sleutel in self.data["lokaal"]:
            return self.data["lokaal"][sleutel]
        if m["cloud"] and not forceer:
            return None
        try:
            with Image.open(m["pad"]) as im:
                im.draft("RGB", (256, 256))
                h = dhash_img(im)
        except Exception:
            h = None
        self.data["lokaal"][sleutel] = h
        return h

    def online(self, url, sleutel):
        if sleutel in self.data["online"]:
            return self.data["online"][sleutel]
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            with Image.open(io.BytesIO(r.content)) as im:
                h = dhash_img(im)
        except Exception:
            h = None
        self.data["online"][sleutel] = h
        return h


# ---------- tekstsignalen ----------

# Bestandsnaam-ruis (camera's, apps, exports)
BESTAND_RUIS = {
    "img", "dsc", "dscf", "dscn", "pxl", "mvi", "mov", "vid", "gopr", "dji", "whatsapp", "image",
    "screenshot", "clipboard", "kopie", "copy", "final", "sequence", "still", "untitled", "export",
    "frame", "frames", "scherm", "schermafbeelding", "photo", "video", "picture", "snapshot",
    "jarnoburger", "insta", "instagram", "reel", "story", "edit", "edited", "versie", "small",
    "large", "thumb", "thumbnail", "preview", "output", "input", "temp", "test", "comp", "render",
    "renders", "beauty", "layer", "kopievan",
}
# Gewicht per bron van een trefwoord
BRON_GEWICHT = {"naam": 1.0, "extra": 1.0, "tekst": 0.6, "bestand": 0.4}
_WOORD_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9']{3,}")
_JAAR_RE = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)")


def _woorden(tekst):
    return {w.lower() for w in _WOORD_RE.findall(tekst or "")}


def trefwoorden(werk):
    """{woord: bron-gewicht}. Bronnen: map/naam, yml 'trefwoorden', _tekst.md, bestandsnamen."""
    uit = {}

    def zet(woorden, bron):
        g = BRON_GEWICHT[bron]
        for w in woorden:
            if w in STOPWOORDEN or w.isdigit():
                continue
            if bron == "bestand" and (w in BESTAND_RUIS or re.search(r"\d", w)):
                continue
            if g > uit.get(w, 0):
                uit[w] = g

    bron = f"{werk['mapnaam']} {werk['naam']}"
    naam = _woorden(bron)
    # korte codes met een cijfer, zoals G2, S7 (geen jaartallen)
    naam |= {w.lower() for w in re.findall(r"\b[A-Za-z0-9]{2,3}\b", bron)
             if re.search(r"\d", w) and re.search(r"[A-Za-z]", w)}
    zet(naam, "naam")
    extra = werk.get("yml", {}).get("trefwoorden", "")
    zet({x.strip().lower() for x in extra.split(",") if x.strip()}, "extra")
    t = werk.get("tekst")
    if t:
        tekst = " ".join(list(t["velden"].values()) + [e["tekst"] for e in t["eerder"]])
        zet(_woorden(tekst), "tekst")
    bestandswoorden = set()
    for m in werk["media"][:400]:
        stam = os.path.splitext(m["naam"])[0].replace("_", " ").replace("-", " ")
        bestandswoorden |= _woorden(stam)
    zet(bestandswoorden, "bestand")
    return uit


def jaren_van_werk(werk):
    jaren = [int(j) for j in _JAAR_RE.findall(f"{werk['mapnaam']} {werk.get('jaar', '')}")]
    return (min(jaren), max(jaren)) if jaren else None


def datums_in_bestanden(werk):
    uit = set()
    for m in werk["media"]:
        for j, mnd, d in _DATUM_RE.findall(m["naam"]):
            try:
                uit.add(dt.date(int(j), int(mnd), int(d)))
            except ValueError:
                pass
    return uit


def post_datum(post):
    try:
        return dt.datetime.fromisoformat(post["timestamp"][:19]).date()
    except (ValueError, KeyError):
        return None


# ---------- hoofdroutine ----------

def _woord_gewicht(df_x, n_werken):
    """Zeldzaam woord (1 werk) ~10 punten, woord in veel werken -> bijna 0."""
    if n_werken <= 1:
        return 6
    return 10 * math.log((n_werken + 1) / (df_x + 0.5)) / math.log(n_werken + 1)


def _treft(woord, tokens, tekst):
    if woord in tokens:
        return True
    if len(woord) >= 6:  # begin van een langer woord (reindier -> reindiertjes)
        return re.search(rf"\b{re.escape(woord)}", tekst) is not None
    return False


def _fuzzy(woord, tokens):
    """Tikfouten: 'nickeloedeon' ~ 'nickelodeon'. Alleen lange woorden, snelle voorselectie."""
    if len(woord) < 5:
        return None
    for t in tokens:
        if len(t) >= 5 and t[:2] == woord[:2] and abs(len(t) - len(woord)) <= 2 and t != woord:
            if difflib.SequenceMatcher(None, woord, t).ratio() >= 0.86:
                return t
    return None


def bereken(werken, groepen, hashes=None, drempel=10, online_hashen=False):
    """Geeft {gid: [(score, pid, redenen), ...]} terug, beste eerst."""
    index = []
    for w in werken:
        captions = set()
        if w["tekst"]:
            for k in ("Caption NL", "Caption EN"):
                if w["tekst"]["velden"].get(k):
                    captions.add(textfile.norm(w["tekst"]["velden"][k]))
            captions |= {textfile.norm(e["tekst"]) for e in w["tekst"]["eerder"]}
        lokale_hashes = []
        if hashes and online_hashen:
            for m in w["media"]:
                h = hashes.lokaal(m)
                if h is not None:
                    lokale_hashes.append(h)
        index.append((w, trefwoorden(w), datums_in_bestanden(w), captions, lokale_hashes, jaren_van_werk(w)))
    df = {}
    for _, woorden, *_ in index:
        for x in woorden:
            df[x] = df.get(x, 0) + 1
    n_werken = len(index)

    resultaat = {}
    for g in groepen:
        caps = [textfile.norm(c) for c in g["captions"]]
        alle_tekst = " ".join(caps)
        tokens = set(re.findall(r"[a-zà-ÿ0-9']+", alle_tekst))
        lange_tokens = [t for t in tokens if len(t) >= 5]
        cap_jaren = {int(j) for j in _JAAR_RE.findall(alle_tekst)}
        datums = {d for d in (post_datum(p) for p in g["posts"]) if d}
        g_hashes = []
        if hashes and online_hashen:
            for p in g["posts"]:
                for i, url in enumerate(p["thumbs"][:4]):
                    h = hashes.online(url, f"{p['key']}#{i}")
                    if h is not None:
                        g_hashes.append(h)
        kandidaten = []
        tekst_compact = re.sub(r"[^a-z0-9à-ÿ]", "", alle_tekst)
        for w, woorden, w_datums, w_caps, lh, w_jaren in index:
            score, redenen = 0.0, []
            w_compact = re.sub(r"[^a-z0-9à-ÿ]", "", re.sub(r"^[\d\-– ]{4,}", "", w["mapnaam"].lower()))
            if any(c in w_caps for c in caps):
                score += 100
                redenen.append("caption staat al lokaal")
            punten, gevonden = 0.0, []
            if alle_tekst:
                for x, bron_g in woorden.items():
                    if _treft(x, tokens, alle_tekst):
                        wg = _woord_gewicht(df[x], n_werken)
                        if bron_g == 1.0:  # naam van het werk of eigen trefwoord: altijd sterk
                            wg = max(wg, 7)
                        punten += bron_g * wg
                        gevonden.append(x)
                    elif bron_g == 1.0:
                        f = _fuzzy(x, lange_tokens)
                        if f:
                            punten += 0.8 * max(_woord_gewicht(df[x], n_werken), 7)
                            gevonden.append(f"{x}≈{f}")
            # naam aan elkaar geschreven: '2 Days Art Dome' ~ '2daysart dome', 'Pink Floyd' ~ '#pinkfloyd'
            if w_compact and len(w_compact) >= 6 and w_compact in tekst_compact:
                punten += 12
                gevonden.append(f"naam “{w['naam']}”")
            if punten >= 3:
                score += punten
                redenen.append("woord: " + ", ".join(sorted(gevonden, key=len)[:4]))
            if datums and w_datums and any(abs((a - b).days) <= 3 for a in datums for b in w_datums):
                score += 8
                redenen.append("datum in bestandsnaam")
            if lh and g_hashes:
                hits = sum(1 for a in g_hashes if any(afstand(a, b) <= drempel for b in lh))
                if hits:
                    score += min(100, 25 * hits)
                    redenen.append(f"{hits} beeld(en) gelijk")
            if score > 0 and cap_jaren and w_jaren and any(w_jaren[0] - 1 <= j <= w_jaren[1] + 1 for j in cap_jaren):
                score += 4
                redenen.append("jaartal klopt")
            if score >= 6:
                if w["merk"] == g["merk"]:
                    score += 2
                kandidaten.append((round(score), w["pid"], redenen))
        kandidaten.sort(key=lambda k: -k[0])
        resultaat[g["gid"]] = kandidaten[:3]
    return resultaat


# ---------- jaartal-voorstellen ----------

_BESTAND_DATUM_RE = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)[-_]?(0[1-9]|1[0-2])[-_]?([0-2]\d|3[01])(?!\d)")
# Datums die de overdracht/export tonen, niet wanneer het werk gemaakt is
_OVERDRACHT_RE = re.compile(r"^(whatsapp|img-\d{8}-wa|\d{1,3}_20\d\d_|jarnoburger-|screenshot|schermafbeelding)", re.I)


def jaar_voorstellen(werken, groepen, suggesties, links):
    """Per werk zonder jaartal vooraan in de mapnaam: bewijs voor een jaartal.

    zeker  = caption-jaartal van een gekoppelde/sterk voorgestelde post, of bestaand yml-jaar
    camera = datum in camera-bestandsnaam (20190812_..., PXL_..., IMG_2019...)
    uiterlijk = WhatsApp/export/screenshot-datum: het werk is NIET later dan dit
    """
    per_gid = {g["gid"]: g for g in groepen}
    per_key = {k: g for g in groepen for k in g["keys"]}
    uit = []
    for w in werken:
        if w["los"] or _JAAR_RE.match(w["mapnaam"]):
            continue
        zeker, camera, uiterlijk, bronnen = set(), set(), set(), []
        gids = {per_key[k]["gid"] for k, v in links.items() if v["pid"] == w["pid"] and k in per_key}
        gids |= {gid for gid, kand in suggesties.items() if kand and kand[0][1] == w["pid"] and kand[0][0] >= 12}
        for gid in gids:
            for c in per_gid[gid]["captions"]:
                for j in _JAAR_RE.findall(c):
                    zeker.add(int(j))
                    bronnen.append(f"caption “{c[:40]}”")
        if w.get("jaar") and "aanname" not in w["jaar"]:
            for j in _JAAR_RE.findall(w["jaar"]):
                zeker.add(int(j))
                bronnen.append(f"_project.yml: {w['jaar']}")
        for m in w["media"]:
            mt = _BESTAND_DATUM_RE.search(m["naam"])
            if not mt:
                continue
            if re.search(r"3ds max|autodesk|maya 20|version|v20\d\d", m["naam"], re.I):
                continue  # softwareversie, geen datum
            if _OVERDRACHT_RE.match(m["naam"]):
                uiterlijk.add(int(mt.group(1)))
            else:
                camera.add(int(mt.group(1)))
                if len(bronnen) < 6:
                    bronnen.append(f"bestand {m['naam'][:30]}")
        if zeker:
            basis, zekerheid = zeker, "hoog"
        elif camera:
            basis, zekerheid = camera, "middel"
        else:
            basis, zekerheid = set(), "laag"
        voorstel = "" if not basis else (str(min(basis)) if min(basis) == max(basis) else f"{min(basis)}-{max(basis)}")
        uit.append({"werk": w, "voorstel": voorstel, "zekerheid": zekerheid if basis else "",
                    "uiterlijk": min(uiterlijk) if uiterlijk else None, "bronnen": bronnen[:4]})
    return uit
