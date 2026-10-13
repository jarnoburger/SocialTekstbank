"""Exporteert per werk alle bekende context naar data/context_alle.json (voor online research).

python tools/export_context.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config, textfile  # noqa: E402

per_key = {p["key"]: p for p in A.online()["posts"]}
lpw = A.links_per_werk()
uit = []
for w in A.werken(herscan=True):
    if w["los"]:
        continue
    t = w["tekst"] or textfile.leeg()
    captions = []
    for k in lpw.get(w["pid"], []):
        p = per_key.get(k)
        if p and p["caption"].strip():
            captions.append({"platform": p["platform"], "datum": p["timestamp"][:10], "caption": p["caption"].strip()})
    for e in t["eerder"]:
        if not any(textfile.norm(e["tekst"]) == textfile.norm(c["caption"]) for c in captions):
            captions.append({"platform": "eerder", "datum": e["kop"], "caption": e["tekst"]})
    submappen = sorted({m["rel"].split("/")[0].split("\\")[0] for m in w["media"] if "/" in m["rel"] or "\\" in m["rel"]})
    uit.append({
        "pid": w["pid"], "merk": w["merk"], "mapnaam": w["mapnaam"], "jaar": w["jaar"],
        "yml": {k: v for k, v in w["yml"].items() if k in ("discipline", "rol", "notitie", "trefwoorden", "promotie", "opdrachtgever", "factuurbron", "jaar")},
        "velden": {k: v for k, v in t["velden"].items() if v.strip()},
        "captions": captions[:8],
        "submappen": submappen[:15],
        "bestandsnamen": [m["naam"] for m in w["media"][:25]],
        "n_img": w["n_img"], "n_vid": w["n_vid"],
    })
pad = os.path.join(config.DATA_DIR, "context_alle.json")
with open(pad, "w", encoding="utf-8") as f:
    json.dump(uit, f, ensure_ascii=False, indent=1)
print(len(uit), "werken ->", pad)
