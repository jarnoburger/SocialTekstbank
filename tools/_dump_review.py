"""Dump van reviewstatus + relevante velden per werk (alleen lezen)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app
from core import textfile

uit = []
for w in app.werken():
    if w["los"]:
        continue
    y = w["yml"]
    v = (w["tekst"] or textfile.leeg())["velden"]
    pad_t = textfile.pad_voor(w["pad"])
    uit.append({
        "map": w["mapnaam"], "pid": w["pid"], "merk": w["merk"], "jaar": w["jaar"],
        "review": (y.get("review") or "").strip(), "review_notitie": (y.get("review_notitie") or "").strip(),
        "caption_review": (y.get("caption_review") or "").strip(),
        "opdrachtgever": y.get("opdrachtgever", ""), "trefwoorden": y.get("trefwoorden", ""),
        "mtime_tekst": os.path.getmtime(pad_t) if os.path.exists(pad_t) else 0,
        "Beeldbeschrijving": v.get("Beeldbeschrijving", ""), "Credits": v.get("Credits", ""),
        "Crosslinks": v.get("Crosslinks", ""), "Caption NL": v.get("Caption NL", ""), "Caption EN": v.get("Caption EN", ""),
        "Hashtags": v.get("Hashtags", ""), "Kort": v.get("Kort", ""),
        "n_media": len(w["media"]), "n_posts": len(app.links_per_werk().get(w["pid"], [])),
    })
p = os.path.join(app.config.DATA_DIR, "_dump_review.json")
json.dump(uit, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("werken:", len(uit), "| met review:", sum(1 for u in uit if u["review"] or u["review_notitie"]), "->", p)
