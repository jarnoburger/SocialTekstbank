"""Controleert alle koppelingen en zorgt dat elke caption in _tekst.md van het werk staat.
Ververst ook _social.json per werk. Idempotent: dubbele captions worden niet opnieuw toegevoegd.

python tools/oogst_captions.py          -> proefrun (telt alleen)
python tools/oogst_captions.py --doe    -> schrijven
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STB_GEEN_BROWSER", "1")
import app as A  # noqa: E402
from core import textfile  # noqa: E402

DOE = "--doe" in sys.argv
wm = A.werk_map()
lk = A.links()
posts = {p["key"]: p for p in A.online()["posts"]}

stats = dict(koppelingen=len(lk), met_caption=0, al_aanwezig=0, toegevoegd=0, zonder_caption=0,
             post_onbekend=0, werk_onbekend=0)
per_werk = {}
for key, v in lk.items():
    w = wm.get(v["pid"])
    p = posts.get(key)
    if not w:
        stats["werk_onbekend"] += 1
        continue
    if not p:
        stats["post_onbekend"] += 1
        continue
    per_werk.setdefault(w["pid"], []).append(p)
    if not p["caption"].strip():
        stats["zonder_caption"] += 1
        continue
    stats["met_caption"] += 1
    data = textfile.lees(w["pad"]) or textfile.leeg()
    bekend = {textfile.norm(e["tekst"]) for e in data["eerder"]}
    if textfile.norm(p["caption"]) in bekend:
        stats["al_aanwezig"] += 1
        continue
    stats["toegevoegd"] += 1
    if DOE:
        textfile.voeg_caption_toe(w["pad"], p["platform"], p["timestamp"][:10], p["permalink"], p["caption"])

if DOE:
    for pid in per_werk:
        A.schrijf_social_json(wm[pid])

# overzicht per werk
werken_met = sum(1 for pid, ps in per_werk.items() if any(x["caption"].strip() for x in ps))
alleen_zonder = [wm[pid]["mapnaam"] for pid, ps in per_werk.items() if not any(x["caption"].strip() for x in ps)]
print(stats)
print("werken met gekoppelde posts:", len(per_werk), "| waarvan met minstens 1 caption:", werken_met)
print("werken waarvan alle gekoppelde posts GEEN caption hebben:", len(alleen_zonder))
for n in sorted(alleen_zonder):
    print("  -", n)
print("werken zonder enige koppeling:", sum(1 for w in wm.values() if not w["los"] and w["pid"] not in per_werk))
print("geschreven" if DOE else "proefrun: niets geschreven")
