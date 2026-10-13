"""Dump mediabestanden per werk (naam, grootte, type, cloud) - alleen lezen."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app

uit = {}
for w in app.werken():
    uit[w["pid"]] = {"map": w["mapnaam"], "merk": w["merk"], "pad": w["pad"], "los": w["los"],
                     "media": [{k: m.get(k) for k in m if k in ("naam", "rel", "pad", "size", "grootte", "type", "cloud")}
                               for m in w["media"]],
                     "media_keys": sorted(w["media"][0].keys()) if w["media"] else []}
p = os.path.join(app.config.DATA_DIR, "_dump_media.json")
json.dump(uit, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("werken:", len(uit), "media:", sum(len(v["media"]) for v in uit.values()))
