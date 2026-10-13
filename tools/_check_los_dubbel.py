"""Alleen lezen: extra dubbel-check voor wat er nog in _Los staat.
1) exact gelijk (zelfde grootte + sha1) aan een bestand in een werkmap (lokaal); cloud-only: alleen grootte+naam
2) onderling dubbel (sha1, of dHash <= 10 voor foto's)
3) foto's: dHash-afstand tot dichtstbijzijnde werkfoto / online beeld (ook boven de drempel, ter info)
4) zelfde grootte als een online post-video kan niet (API geeft geen grootte) -> niet gecheckt"""
import os, sys, hashlib, collections, json
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config, match as M
from PIL import Image


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


hs = config.load_json(os.path.join(config.DATA_DIR, "hashes.json"), {})
lok = [int(v) for v in hs.get("lokaal", {}).values() if isinstance(v, (int, float))]
onl = [int(v) for v in hs.get("online", {}).values() if isinstance(v, (int, float))]
with A.app.test_request_context():
    ws = A.werken(herscan=True)
    los = [(w, m) for w in ws if w["los"] for m in w["media"]]
    per_size = collections.defaultdict(list)
    for w in ws:
        if not w["los"]:
            for m in w["media"]:
                per_size[m["size"]].append((w, m))
    rap, sha_los, dh_los = [], {}, {}
    for w, m in los:
        r = {"bestand": m["naam"], "merk": w["merk"], "type": m["type"], "exact": [], "zelfde_grootte": [], "dhash_min": None}
        s1 = sha1(m["pad"])
        sha_los.setdefault(s1, []).append(m["naam"])
        for ww, mm in per_size.get(m["size"], []):
            if mm["cloud"]:
                r["zelfde_grootte"].append(f"{ww['mapnaam']}/{mm['rel']} (cloud)")
            elif sha1(mm["pad"]) == s1:
                r["exact"].append(f"{ww['mapnaam']}/{mm['rel']}")
            else:
                r["zelfde_grootte"].append(f"{ww['mapnaam']}/{mm['rel']}")
        if m["type"] == "img":
            try:
                dh = M.dhash_img(Image.open(m["pad"]))
                dh_los[m["naam"]] = dh
                r["dhash_min"] = min([M.afstand(dh, x) for x in lok + onl] or [99])
            except Exception as e:
                r["dhash_min"] = f"fout: {e}"
        rap.append(r)
    onderling_sha = [v for v in sha_los.values() if len(v) > 1]
    namen = list(dh_los)
    onderling_dh = [(a, b, M.afstand(dh_los[a], dh_los[b])) for i, a in enumerate(namen) for b in namen[i + 1:]
                    if M.afstand(dh_los[a], dh_los[b]) <= 10]
    config.save_json(os.path.join(config.DATA_DIR, "_check_los_dubbel.json"),
                     {"rapport": rap, "onderling_sha": onderling_sha, "onderling_dhash": onderling_dh})
    print("bestanden in _Los:", len(rap), collections.Counter(r["type"] for r in rap))
    print("EXACT gelijk aan werkbestand:", [(r["bestand"], r["exact"]) for r in rap if r["exact"]])
    print("zelfde grootte (mogelijk gelijk):", [(r["bestand"], r["zelfde_grootte"]) for r in rap if r["zelfde_grootte"] and not r["exact"]])
    print("onderling exact gelijk:", onderling_sha)
    print("onderling bijna gelijk (foto):", onderling_dh)
    fot = [r for r in rap if r["type"] == "img" and isinstance(r["dhash_min"], int)]
    print("foto's: kleinste afstand tot iets bekends:", sorted(r["dhash_min"] for r in fot))
    print("bijna-matches 11-16 (twijfel):", [(r["bestand"], r["dhash_min"]) for r in fot if 11 <= r["dhash_min"] <= 16])
