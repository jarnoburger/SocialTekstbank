"""Lokale scanner: vindt werken (projectmappen) en hun media in de _To Promote-mappen.

Regels voor wat een 'werk' is:
- een map met _project.yml (bestaande portfolio-kaart) is een werk;
- 'containermappen' (Done, ToDo, _ToDo, 1) worden doorzocht; elke submap daarin is een werk;
- losse media direct in een containermap vormen samen één pseudo-werk "Losse bestanden".

Cloud-only bestanden (OneDrive 'alleen online') worden herkend en NIET geopend,
zodat de scan niets downloadt.
"""
import hashlib
import os
import re
import sys

from . import textfile

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".jfif"}
VID_EXT = {".mp4", ".mov", ".avi", ".m4v", ".mkv", ".wmv", ".mpg", ".mpeg", ".flv", ".webm", ".3gpp", ".vob"}
SKIP_DIRS = {".git", ".github", "lib", "libs", "node_modules", "library", "obj", "bin",
             "__pycache__", "packages", "temp", "build", "_to_delete"}
CONTAINERS = {"done", "_done", "todo", "_todo", "to do", "_los", "los"}


def is_container(naam):
    """Verzamelbakken: Done/ToDo/_Los en genummerde mappen (1, 2, 3 ...) zijn nooit zelf een werk."""
    n = naam.strip().lower()
    return n in CONTAINERS or n.isdigit()
MAX_DIEPTE = 4
MAX_MEDIA = 800

# Windows-bestandsattributen voor OneDrive-placeholders
_ATTR_OFFLINE = 0x1000
_ATTR_RECALL_ON_OPEN = 0x40000
_ATTR_RECALL_ON_DATA_ACCESS = 0x400000
_CLOUD_MASK = _ATTR_OFFLINE | _ATTR_RECALL_ON_OPEN | _ATTR_RECALL_ON_DATA_ACCESS


def is_cloud(st):
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & _CLOUD_MASK)


def pid_voor(pad):
    return hashlib.sha1(os.path.normcase(os.path.abspath(pad)).encode("utf-8")).hexdigest()[:10]


def lees_yml(pad):
    """Simpele 'sleutel: waarde'-parser voor _project.yml (zelfde formaat als portfolio.py)."""
    out = {}
    try:
        with open(pad, "r", encoding="utf-8-sig") as f:
            for regel in f:
                regel = regel.rstrip("\n")
                if not regel.strip() or regel.lstrip().startswith("#") or ":" not in regel:
                    continue
                k, v = regel.split(":", 1)
                out[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return out


_JAAR_RE = re.compile(r"^((?:19|20)\d{2}(?:[-–](?:19|20)?\d{2})?)")
_JAAR_PREFIX_RE = re.compile(r"^(?:19|20)\d{2}(?:[-–](?:(?:19|20)?\d{2}))*\s+")


def jaar_uit(naam, yml):
    """Mapnaam is leidend; yml-jaar alleen als de map geen jaartal heeft."""
    m = _JAAR_RE.match(naam)
    if m:
        return m.group(1)
    return yml.get("jaar", "")


PROMOTIE_WAARDEN = ["gepromoot", "te promoten", "deels", "niet promoten"]


def promotie_status(yml):
    """Normaliseert het yml-veld 'promotie' naar een van PROMOTIE_WAARDEN (of '')."""
    p = (yml.get("promotie") or "").lower()
    if "niet promoten" in p:
        return "niet promoten"
    if "deels" in p:
        return "deels"
    if "nog" in p or "te promoten" in p or "todo" in p:
        return "te promoten"
    if "gepromoot" in p:
        return "gepromoot"
    return ""


def naam_zonder_jaar(mapnaam):
    return _JAAR_PREFIX_RE.sub("", mapnaam).strip() or mapnaam


def media_type(naam):
    ext = os.path.splitext(naam)[1].lower()
    if ext in IMG_EXT:
        return "img"
    if ext in VID_EXT:
        return "vid"
    return None


def _media_in(projectmap):
    """Alle media onder een projectmap (begrensde diepte, codemappen overgeslagen)."""
    items = []
    stack = [(projectmap, 0)]
    while stack and len(items) < MAX_MEDIA:
        d, diepte = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in sorted(entries, key=lambda x: x.name.lower()):
            try:
                if e.is_dir(follow_symlinks=False):
                    if diepte < MAX_DIEPTE and e.name.lower() not in SKIP_DIRS and not e.name.startswith("."):
                        stack.append((e.path, diepte + 1))
                    continue
                t = media_type(e.name)
                if not t:
                    continue
                st = e.stat(follow_symlinks=False)
                items.append({
                    "naam": e.name,
                    "rel": os.path.relpath(e.path, projectmap).replace("\\", "/"),
                    "pad": e.path,
                    "type": t,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "cloud": is_cloud(st),
                })
            except OSError:
                continue
    items.sort(key=lambda m: m["rel"].lower())
    return items


def _werk(pad, merk, root, los_bestanden=None, naam=None):
    yml_pad = os.path.join(pad, "_project.yml")
    yml = lees_yml(yml_pad) if os.path.exists(yml_pad) else {}
    mapnaam = os.path.basename(pad)
    media = los_bestanden if los_bestanden is not None else _media_in(pad)
    tekst = textfile.lees(pad) if los_bestanden is None else _lees_los(pad)
    rel = os.path.relpath(pad, root).replace("\\", "/")
    fase = rel.split("/")[0] if rel != "." else ""
    pid = pid_voor(pad) if los_bestanden is None else pid_voor(pad + "|los")
    return {
        "pid": pid,
        "merk": merk,
        "pad": pad,
        "rel": rel,
        "fase": fase,
        "promotie": promotie_status(yml),
        "naam": naam or naam_zonder_jaar(mapnaam),
        "mapnaam": mapnaam,
        "jaar": jaar_uit(mapnaam, yml),
        "yml": yml,
        "los": los_bestanden is not None,
        "media": media,
        "n_img": sum(1 for m in media if m["type"] == "img"),
        "n_vid": sum(1 for m in media if m["type"] == "vid"),
        "n_lokaal": sum(1 for m in media if not m["cloud"]),
        "tekst": tekst,
        "status": textfile.status(tekst, len(media)),
    }


def _lees_los(containerpad):
    # Losse bestanden in een containermap delen één _tekst.md in die containermap.
    return textfile.lees(containerpad)


def scan(roots):
    werken = []
    for root_cfg in roots:
        root, merk = root_cfg["pad"], root_cfg["merk"]
        if not os.path.isdir(root):
            continue
        _scan_container(root, merk, root, werken)
    werken.sort(key=lambda w: (w["merk"], w["los"], w["jaar"] or "9999", w["naam"].lower()))
    return werken


def _scan_container(d, merk, root, werken):
    try:
        entries = sorted(os.scandir(d), key=lambda x: x.name.lower())
    except OSError:
        return
    losse = []
    for e in entries:
        try:
            if e.is_dir(follow_symlinks=False):
                if e.name.startswith(".") or e.name.lower() in SKIP_DIRS:
                    continue
                if is_container(e.name):
                    _scan_container(e.path, merk, root, werken)
                    continue
                w = _werk(e.path, merk, root)
                if w["media"] or w["yml"] or w["tekst"]:
                    werken.append(w)
            else:
                t = media_type(e.name)
                if t:
                    st = e.stat(follow_symlinks=False)
                    losse.append({"naam": e.name, "rel": e.name, "pad": e.path, "type": t,
                                  "size": st.st_size, "mtime": st.st_mtime, "cloud": is_cloud(st)})
        except OSError:
            continue
    if losse:
        rel = os.path.relpath(d, root).replace("\\", "/")
        werken.append(_werk(d, merk, root, los_bestanden=losse,
                            naam=f"Losse bestanden ({rel})"))


def in_roots(pad, roots):
    p = os.path.normcase(os.path.abspath(pad))
    for r in roots:
        rp = os.path.normcase(os.path.abspath(r["pad"]))
        if p == rp or p.startswith(rp + os.sep):
            return True
    return False


IS_WINDOWS = sys.platform.startswith("win")


def zet_yml(projectmap, sleutel, waarde):
    """Zet één regel 'sleutel: waarde' in _project.yml (maakt het bestand aan als het ontbreekt).
    Overige regels en commentaar blijven ongemoeid."""
    pad = os.path.join(projectmap, "_project.yml")
    regels = []
    if os.path.exists(pad):
        with open(pad, "r", encoding="utf-8-sig") as f:
            regels = f.read().splitlines()
    nieuw = f"{sleutel}: {waarde}".rstrip()
    for i, r in enumerate(regels):
        if not r.lstrip().startswith("#") and r.split(":", 1)[0].strip() == sleutel:
            regels[i] = nieuw
            break
    else:
        if sleutel == "trefwoorden":
            regels.append("# trefwoorden: extra zoekwoorden voor SocialTekstbank (komma's)")
        regels.append(nieuw)
    tmp = pad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(regels) + "\n")
    os.replace(tmp, pad)


_ONGELDIG = set('\\/:*?"<>|')


def hernoem_map(pad, nieuwe_naam):
    """Hernoemt een projectmap binnen dezelfde bovenliggende map. Geeft het nieuwe pad terug."""
    nieuwe_naam = " ".join(nieuwe_naam.split())
    if not nieuwe_naam or any(c in _ONGELDIG for c in nieuwe_naam) or nieuwe_naam in (".", ".."):
        raise ValueError(f"Ongeldige mapnaam: {nieuwe_naam!r}")
    nieuw = os.path.join(os.path.dirname(pad), nieuwe_naam)
    if os.path.normcase(nieuw) == os.path.normcase(pad):
        if nieuw != pad:  # alleen hoofdletters anders (Windows): via tussenstap
            tmp = pad + "__tmp_hernoem"
            os.rename(pad, tmp)
            os.rename(tmp, nieuw)
        return nieuw
    if os.path.exists(nieuw):
        raise ValueError(f"Er bestaat al een map '{nieuwe_naam}'")
    os.rename(pad, nieuw)
    return nieuw
