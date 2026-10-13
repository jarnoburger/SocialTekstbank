"""Exporteert per post(groep) de context voor een Claude-caption-ronde -> data/caption_context.json.

python tools/caption_context.py                  # alleen groepen zonder Claude-voorstel
python tools/caption_context.py --feedback       # alleen groepen met feedback van Jarno (herschrijfronde)
python tools/caption_context.py --alle           # alles
  opties: --merk SJB|Lichtjes  --limiet 20  --gid g:ig:123 (meerdere mag)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import captions as capt, config, textfile  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--feedback", action="store_true")
ap.add_argument("--alle", action="store_true")
ap.add_argument("--merk", default="")
ap.add_argument("--limiet", type=int, default=0)
ap.add_argument("--gid", action="append", default=[])
args = ap.parse_args()

uit = []
for r in A.caption_rijen():
    g, w, it = r["g"], r["w"], r["it"]
    if args.gid and g["gid"] not in args.gid:
        continue
    if args.merk and g["merk"] != args.merk:
        continue
    if not args.gid and not args.alle:
        if args.feedback and not r["feedback"].strip():
            continue
        if not args.feedback and (r["heeft_claude"] or r["status"] == "overslaan"):
            continue
    t = (w["tekst"] if w else None) or textfile.leeg()
    v = t["velden"]
    _, alts, twijfel = A._alt_teksten(v.get("Beeldbeschrijving", ""))
    plinks = {p["permalink"] for p in g["posts"]}
    uit.append({
        "gid": g["gid"], "merk": g["merk"], "accounts": g["accounts"], "soort": g["soort"],
        "datum": g["start"][:10],
        "posts": [{"platform": p["platform"], "permalink": p["permalink"], "type": p.get("media_type", ""),
                   "caption": p["caption"].strip()} for p in g["posts"]],
        "werk": None if not w else {
            "mapnaam": w["mapnaam"], "jaar": w["jaar"],
            "opdrachtgever": w["yml"].get("opdrachtgever", ""),
            "review": w["yml"].get("review", ""), "review_notitie": w["yml"].get("review_notitie", ""),
            "velden": {k: v[k] for k in ("Titel", "Jaar en plek", "Kort", "Lang", "Credits", "Hashtags", "Caption NL", "Caption EN")
                       if v.get(k, "").strip()},
            "beeld_alinea": A._alt_teksten(v.get("Beeldbeschrijving", ""))[0],
            "twijfel": twijfel,
        },
        "beelden_post": [a for b, a in alts if any(pl in b for pl in plinks)],
        "crosslinks": capt.crosslinks(v.get("Crosslinks", "")),
        "feedback": r["feedback"],
        "vorig_voorstel": {k: it.get("claude", {}).get(k, "") for k in ("nl", "en")} if r["heeft_claude"] else None,
        "beste": it.get("beste") if r["heeft_beste"] else None,
    })
    if args.limiet and len(uit) >= args.limiet:
        break

pad = os.path.join(config.DATA_DIR, "caption_context.json")
with open(pad, "w", encoding="utf-8") as f:
    json.dump(uit, f, ensure_ascii=False, indent=1)
print(len(uit), "postgroepen ->", pad)
