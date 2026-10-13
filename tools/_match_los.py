"""Alleen lezen: vergelijk losse beelden (_Los) met beelden in werkmappen en met online posts via dHash.
Schrijft data/_match_los.json en print een samenvatting."""
import os, sys, json, collections
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config, match as M
D = config.DATA_DIR
DREMPEL = config.load_json(os.path.join(D, "config.json"), {}).get("hash_drempel", 10)
h = config.load_json(os.path.join(D, "hashes.json"), {})
print("hashes secties:", {k: len(v) for k, v in h.items()})
lok = h.get("lokaal", {})
onl = next((v for k, v in h.items() if k != "lokaal"), {})

def sleutel_info(k):
    pad, size, *_ = k.split("|") + ["", ""]
    return os.path.basename(pad).lower(), size, pad

# index: (naam,size) -> hash, en pad -> hash
per_naam = {}
for k, v in lok.items():
    n, s, p = sleutel_info(k)
    per_naam.setdefault((n, s), v)

with A.app.test_request_context():
    ws = A.werken(herscan=True)
    los_media = [(w["merk"], m) for w in ws if w["los"] for m in w["media"] if m["type"] == "img"]
    werk_van_pad = {}
    for w in ws:
        if w["los"]:
            continue
        for m in w["media"]:
            werk_van_pad[os.path.normcase(m["pad"])] = w
    # lokale hashes van werkbeelden (op naam+size teruggezocht naar huidige plek)
    werk_hashes = []
    huidige = {(os.path.basename(m["pad"]).lower(), str(m["size"])): w for w in ws if not w["los"] for m in w["media"]}
    for k, v in lok.items():
        n, s, p = sleutel_info(k)
        w = huidige.get((n, s))
        if w and isinstance(v, (int, float)):
            werk_hashes.append((v, w, n))
    per_key = {p["key"]: p for p in A.online()["posts"]}
    lk = A.links()
    wm = A.werk_map()
    online_hashes = []
    for k, v in onl.items():
        postkey = k.split("|")[0].split("#")[0]
        vals = v if isinstance(v, list) else [v]
        for x in vals:
            if isinstance(x, (int, float)):
                online_hashes.append((int(x), postkey))
    print("werk-hashes", len(werk_hashes), "online-hashes", len(online_hashes))

    uit, tel = [], collections.Counter()
    for merk, m in los_media:
        hv = per_naam.get((m["naam"].lower(), str(m["size"])))
        hv = hv if isinstance(hv, (int, float)) else None
        rij = {"merk": merk, "bestand": m["naam"], "hash": hv is not None, "werk": [], "online": []}
        if hv is not None:
            for wv, w, n in werk_hashes:
                d = M.afstand(int(hv), int(wv))
                if d <= DREMPEL:
                    rij["werk"].append({"werk": w["mapnaam"], "bestand": n, "afstand": d})
            for ov, pk in online_hashes:
                d = M.afstand(int(hv), ov)
                if d <= DREMPEL:
                    p = per_key.get(pk, {})
                    wk = wm.get(lk.get(pk, {}).get("pid"), {}).get("mapnaam", "?")
                    rij["online"].append({"post": pk, "account": p.get("account"), "datum": p.get("timestamp", "")[:10],
                                          "werk": wk, "afstand": d})
        s = ("geen hash" if hv is None else "zelfde als werkfoto" if rij["werk"] else
             "staat al online" if rij["online"] else "geen match")
        tel[(merk, s)] += 1
        uit.append(rij)
    config.save_json(os.path.join(D, "_match_los.json"), uit)
    for k, v in sorted(tel.items()):
        print(f"{v:4}  {k[0]:8} {k[1]}")
    werken_tel = collections.Counter()
    for r in uit:
        for x in {y["werk"] for y in r["werk"]} | {y["werk"] for y in r["online"]}:
            werken_tel[x] += 1
    print("werken waar losse foto's op lijken:", werken_tel.most_common(30))
    # per los-bestand één voorstel: werkfoto-match wint, anders online-match (kleinste afstand)
    voorstel = collections.Counter()
    for r in uit:
        kand = [(x["afstand"], x["werk"]) for x in r["werk"]] + [(x["afstand"], x["werk"]) for x in r["online"]]
        werken_r = {w for _, w in kand}
        r["voorstel"] = min(kand)[1] if kand else ""
        r["twijfel"] = len(werken_r) > 1
        if kand:
            voorstel[(r["voorstel"], "twijfel" if r["twijfel"] else "eenduidig")] += 1
    config.save_json(os.path.join(D, "_match_los.json"), uit)
    print("eenduidig:", sum(v for k, v in voorstel.items() if k[1] == "eenduidig"),
          "| meerdere werken mogelijk:", sum(v for k, v in voorstel.items() if k[1] == "twijfel"))
