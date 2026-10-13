"""Groepeert online posts: alleen IG+FB-crossposts worden samengevoegd, verder is alles plat.

Een IG-post en een FB-post vormen een tweeling als ze van hetzelfde merk zijn en
- binnen CROSSPOST_MIN minuten geplaatst zijn met dezelfde caption (of allebei zonder caption), of
- exact dezelfde caption hebben (niet leeg) binnen TWEELING_DAGEN.
Elke post heeft hoogstens één tweeling (dichtstbijzijnde in tijd).
"""
import datetime as dt

from . import textfile

CROSSPOST_MIN = 10
TWEELING_DAGEN = 14


def _ts(p):
    try:
        return dt.datetime.fromisoformat(p["timestamp"][:19])
    except (ValueError, KeyError):
        return dt.datetime.min


def _is_tweeling(a, b):
    if a["merk"] != b["merk"] or a["platform"] == b["platform"]:
        return None
    ca, cb = textfile.norm(a["caption"]), textfile.norm(b["caption"])
    gat = abs(_ts(a) - _ts(b))
    if ca == cb and gat <= dt.timedelta(minutes=CROSSPOST_MIN):
        return gat
    if ca and ca == cb and len(ca) >= 8 and gat <= dt.timedelta(days=TWEELING_DAGEN):
        return gat
    return None


def maak_groepen(posts):
    posts = sorted(posts, key=_ts)
    ig = [p for p in posts if p["platform"] == "ig"]
    fb = [p for p in posts if p["platform"] != "ig"]
    # kandidaat-paren, dichtstbijzijnde eerst; elke post max één tweeling
    paren = []
    for a in ig:
        for b in fb:
            gat = _is_tweeling(a, b)
            if gat is not None:
                paren.append((gat, a["key"], b["key"]))
    paren.sort()
    partner = {}
    for _, ka, kb in paren:
        if ka not in partner and kb not in partner:
            partner[ka], partner[kb] = kb, ka

    per_key = {p["key"]: p for p in posts}
    gezien, groepen = set(), []
    for p in posts:
        if p["key"] in gezien:
            continue
        leden = [p] + ([per_key[partner[p["key"]]]] if p["key"] in partner else [])
        leden.sort(key=_ts)
        gezien.update(x["key"] for x in leden)
        captions, uniek = [], set()
        for x in leden:
            c = x["caption"].strip()
            if c and textfile.norm(c) not in uniek:
                uniek.add(textfile.norm(c))
                captions.append(c)
        groepen.append({
            "gid": "g:" + leden[0]["key"],
            "posts": leden,
            "keys": [x["key"] for x in leden],
            "merk": leden[0]["merk"],
            "start": leden[0]["timestamp"],
            "eind": leden[-1]["timestamp"],
            "platforms": sorted({x["platform"] for x in leden}),
            "accounts": sorted({x["account"] for x in leden}),
            "captions": captions,
            "n_zonder": sum(1 for x in leden if not x["caption"].strip()),
            "thumbs": [t for x in leden for t in x["thumbs"][:2]][:8],
            "soort": "IG+FB" if len(leden) == 2 else leden[0]["platform"].upper(),
        })
    groepen.sort(key=lambda g: g["start"], reverse=True)
    return groepen
