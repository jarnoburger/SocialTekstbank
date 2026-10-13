"""Caption-vergelijker: per online post(groep) de bestaande caption naast een voorstel van Claude
en een 'beste versie' die Jarno samen met Claude maakt.

Opslag: data/captions.json
    {gid: {"keys": [post_key, ...],
           "claude": {"nl": "", "en": "", "tags": ["@x"], "notitie": "", "datum": "", "ronde": 1},
           "beste": {"nl": "", "en": ""},
           "status": "" | "concept" | "klaar" | "overslaan",
           "feedback": "",          # opmerking van Jarno voor de volgende Claude-ronde
           "gewijzigd": "2026-10-04 13:00"}}

gid = "g:" + eerste post_key van de groep (IG+FB-tweeling = één groep, zie core/group.py).
Als de groepering verschuift, vindt opzoeken via elke post_key in "keys" het item terug.
"""
import datetime as dt
import os
import re

from . import config

CAPTIONS_PATH = os.path.join(config.DATA_DIR, "captions.json")
STATUSSEN = ("concept", "klaar", "overslaan")


def laad():
    return config.load_json(CAPTIONS_PATH, {})


def bewaar(data):
    config.save_json(CAPTIONS_PATH, data)


def zoek(data, groep):
    """Item voor een groep (op gid, anders via een van de post-keys)."""
    if groep["gid"] in data:
        return data[groep["gid"]]
    for gid, item in data.items():
        if set(item.get("keys", [])) & set(groep["keys"]):
            return item
    return None


def item_voor(data, groep):
    """Bestaand item of een nieuw (nog niet opgeslagen) item."""
    it = zoek(data, groep)
    if it is None:
        it = {"keys": list(groep["keys"]), "claude": {}, "beste": {"nl": "", "en": ""},
              "status": "", "feedback": "", "gewijzigd": ""}
        data[groep["gid"]] = it
    it.setdefault("claude", {})
    it.setdefault("beste", {"nl": "", "en": ""})
    return it


def nu():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------- crosslinks uit _tekst.md ----------

_IG = re.compile(r"(?<![\w/])@([A-Za-z0-9_.]*[A-Za-z0-9_])")
_URL = re.compile(r"https?://[^\s<>()]+[^\s<>().,;:]")


def crosslinks(tekst):
    """Regels '- Rol: Partij · web · @ig · zekerheid hoog · notitie' -> [{rol, partij, web, ig, zekerheid, regel}].
    Stopt bij 'Te checken:' / 'Bronnen:'."""
    uit = []
    for regel in (tekst or "").splitlines():
        r = regel.strip()
        low = r.lower()
        if low.startswith(("te checken", "bronnen", "_")):
            break
        if not r.startswith("- ") or " · " not in r:
            continue
        delen = [d.strip() for d in r[2:].split(" · ")]
        kop = delen[0]
        rol, partij = (kop.split(": ", 1) if ": " in kop else ("", kop))
        igs = [m.group(1) for d in delen[1:] for m in _IG.finditer(d)
               if " op tiktok" not in d.lower() and " op x" not in d.lower()]
        web = next((m.group(0) for d in delen[1:] for m in _URL.finditer(d)), "")
        zek = next((d.split("zekerheid", 1)[1].strip() for d in delen if d.lower().startswith("zekerheid")), "")
        uit.append({"rol": rol.strip(), "partij": partij.strip(), "web": web,
                    "ig": ["@" + h for h in igs], "zekerheid": zek, "regel": r[2:]})
    return uit


def tags_uit(tekst):
    """Alle @handles in een tekst (in volgorde, uniek)."""
    gezien, uit = set(), []
    for m in _IG.finditer(tekst or ""):
        h = "@" + m.group(1)
        if h.lower() not in gezien:
            gezien.add(h.lower())
            uit.append(h)
    return uit
