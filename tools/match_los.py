"""Vergelijkt de bestanden in _Los met werkfoto's en online posts (dHash) en schrijft data/los_match.json
voor het scherm /los. Leest alleen; ontbrekende hashes van losse foto's worden uitgerekend (bestanden zijn lokaal).

python tools/match_los.py
"""
import os, sys, collections
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config, match as M  # noqa: E402
from PIL import Image  # noqa: E402

D = config.DATA_DIR
DREMPEL = config.load_json(os.path.join(D, "config.json"), {}).get("hash_drempel", 10)
h = config.load_json(os.path.join(D, "hashes.json"), {})
lok, onl = h.get("lokaal", {}), h.get("online", {})


def naam_size(k):
    pad, size = (k.split("|") + [""])[:2]
    return os.path.basename(pad).lower(), size


per_naam = {}
for k, v in lok.items():
    if isinstance(v, (int, float)):
        per_naam.setdefault(naam_size(k), int(v))

with A.app.test_request_context():
    ws = A.werken(herscan=True)
    huidige = {(m["naam"].lower(), str(m["size"])): (w, m) for w in ws if not w["los"] for m in w["media"]}
    werk_hashes = []
    for k, v in lok.items():
        wm_ = huidige.get(naam_size(k))
        if wm_ and isinstance(v, (int, float)):
            werk_hashes.append((int(v), *wm_))
    per_key = {p["key"]: p for p in A.online()["posts"]}
    lk = A.links()
    online_hashes = []
    for k, v in onl.items():
        if isinstance(v, (int, float)):
            online_hashes.append((int(v), k.split("#")[0], int((k.split("#") + ["0"])[1] or 0)))

    uit, tel, berekend = [], collections.Counter(), 0
    for w in ws:
        if not w["los"]:
            continue
        for m in w["media"]:
            r = {"merk": w["merk"], "los_pid": w["pid"], "rel": m["rel"], "naam": m["naam"], "type": m["type"],
                 "size": m["size"], "werk": [], "online": [], "voorstel": "", "twijfel": False}
            hv = per_naam.get((m["naam"].lower(), str(m["size"])))
            if hv is None and m["type"] == "img" and not m["cloud"]:
                try:
                    hv = M.dhash_img(Image.open(m["pad"]))
                    berekend += 1
                except Exception:
                    hv = None
            if hv is not None:
                for wv, ww, mm in werk_hashes:
                    d = M.afstand(hv, wv)
                    if d <= DREMPEL:
                        r["werk"].append({"pid": ww["pid"], "werk": ww["mapnaam"], "rel": mm["rel"], "afstand": d})
                for ov, pk, idx in online_hashes:
                    d = M.afstand(hv, ov)
                    if d <= DREMPEL:
                        p = per_key.get(pk, {})
                        thumbs = p.get("thumbs") or []
                        if isinstance(thumbs, str):
                            import re
                            thumbs = re.findall(r"https?://[^'\"\s,\]]+", thumbs)
                        pid = lk.get(pk, {}).get("pid", "")
                        r["online"].append({"post": pk, "pid": pid, "werk": A.werk_map().get(pid, {}).get("mapnaam", ""),
                                            "account": p.get("account", ""), "datum": p.get("timestamp", "")[:10],
                                            "permalink": p.get("permalink", ""),
                                            "thumb": thumbs[idx] if idx < len(thumbs) else (thumbs[0] if thumbs else ""),
                                            "afstand": d})
            if hv is not None:  # dichtstbijzijnde bekende beeld, ook boven de drempel (voor twijfelgevallen)
                best = None
                for wv, ww, mm in werk_hashes:
                    d = M.afstand(hv, wv)
                    if mm["naam"].lower() != m["naam"].lower() and (best is None or d < best["afstand"]):
                        best = {"afstand": d, "soort": "werk", "pid": ww["pid"], "werk": ww["mapnaam"], "rel": mm["rel"],
                                "cloud": mm["cloud"]}
                for ov, pk, idx in online_hashes:
                    d = M.afstand(hv, ov)
                    if best is None or d < best["afstand"]:
                        p = per_key.get(pk, {})
                        thumbs = p.get("thumbs") or []
                        if isinstance(thumbs, str):
                            import re
                            thumbs = re.findall(r"https?://[^'\"\s,\]]+", thumbs)
                        pid = lk.get(pk, {}).get("pid", "")
                        best = {"afstand": d, "soort": "online", "pid": pid, "werk": A.werk_map().get(pid, {}).get("mapnaam", ""),
                                "permalink": p.get("permalink", ""),
                                "thumb": thumbs[idx] if idx < len(thumbs) else (thumbs[0] if thumbs else "")}
                r["dichtst"] = best
            kand = [(x["afstand"], x["pid"]) for x in r["werk"]] + [(x["afstand"], x["pid"]) for x in r["online"] if x["pid"]]
            if kand:
                r["voorstel"] = min(kand)[1]
                r["twijfel"] = len({p for _, p in kand}) > 1
            r["hash"] = hv is not None
            r["soort"] = ("dubbel" if r["werk"] and min(x["afstand"] for x in r["werk"]) <= 4 else
                          "match" if kand else "video" if m["type"] != "img" else "onbekend")
            tel[r["soort"]] += 1
            uit.append(r)
    volg = {"dubbel": 0, "match": 1, "onbekend": 2, "video": 3}
    uit.sort(key=lambda r: (volg[r["soort"]], r["twijfel"], r["merk"], r["naam"].lower()))
    config.save_json(os.path.join(D, "los_match.json"), uit)
    print("bestanden", len(uit), dict(tel), "| hashes berekend:", berekend)
