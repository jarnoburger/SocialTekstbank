"""Posts herkoppelen naar een ander werk (zelfde logica als /koppel), optioneel nieuw werk aanmaken.

python tools/herkoppel.py data/herkoppel.json [--doe]
JSON: {"nieuw": [{"merk": "SJB", "mapnaam": "2003 Jeff Mills", "jaar": "2003"}],
       "koppel": [{"key": "ig:...", "merk": "SJB", "mapnaam": "2022 Voronoi Boom"}]}
Log: data/herkoppel-log-<tijd>.json. Niets wordt verwijderd; de oude caption blijft in Eerdere captions van het oude werk.
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config, local, textfile  # noqa: E402

DOE = "--doe" in sys.argv
taak = json.load(open(sys.argv[1], encoding="utf-8"))
ROOTS = {r["merk"]: r["pad"] for r in config.load_config()["roots"]}

for n in taak.get("nieuw", []):
    pad = os.path.join(ROOTS[n["merk"]], n["mapnaam"])
    if os.path.exists(pad):
        print("bestaat al:", pad)
        continue
    print("NIEUW werk:", pad)
    if DOE:
        os.makedirs(pad)
        d = textfile.leeg()
        d["velden"]["Titel"] = local.naam_zonder_jaar(n["mapnaam"])
        textfile.schrijf(pad, d)
        if n.get("jaar"):
            local.zet_yml(pad, "jaar", n["jaar"])

per = {(w["merk"], w["mapnaam"]): w for w in A.werken(herscan=True) if not w.get("los")}
lk = A.links()
wm = A.werk_map()
posts = {p["key"]: p for p in A.online()["posts"]}
vandaag = dt.datetime.now().strftime("%Y-%m-%d")
log, geraakt = [], set()
for t in taak["koppel"]:
    w = per.get((t["merk"], t["mapnaam"]))
    if not w and not DOE and any(n["mapnaam"] == t["mapnaam"] for n in taak.get("nieuw", [])):
        print(f"  {t['key']:45} -> {t['mapnaam']} (nieuw)")
        continue
    if not w:
        print("DOEL NIET GEVONDEN:", t["mapnaam"])
        continue
    oud = lk.get(t["key"], {}).get("pid")
    oudnaam = wm.get(oud, {}).get("mapnaam", "-")
    print(f"  {t['key']:45} {oudnaam} -> {w['mapnaam']}")
    log.append({"key": t["key"], "van": oud, "van_naam": oudnaam, "naar": w["pid"], "naar_naam": w["mapnaam"]})
    if DOE:
        lk[t["key"]] = {"pid": w["pid"], "pad": w["pad"], "op": vandaag}
        p = posts.get(t["key"])
        if p and p["caption"].strip():
            textfile.voeg_caption_toe(w["pad"], p["platform"], p["timestamp"][:10], p["permalink"], p["caption"])
        geraakt.update({oud, w["pid"]})
if DOE:
    config.save_json(config.LINKS_PATH, lk)
    wm = A.werk_map()
    for pid in geraakt:
        if pid in wm:
            A.schrijf_social_json(wm[pid])
    f = os.path.join(os.path.dirname(config.LINKS_PATH), f"herkoppel-log-{dt.datetime.now():%Y%m%d-%H%M%S}.json")
    json.dump(log, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("geschreven; log:", f)
else:
    print("Proefrun. Schrijven met --doe")
