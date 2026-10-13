"""Alleen lezen: welke werken hebben (nog) geen post, per merk en platform. Schrijft data/_dump_ongepromoot.json"""
import os, sys, json
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import app as A
from core import config
with A.app.test_request_context():
    per_key = {p["key"]: p for p in A.online()["posts"]}
    lpw = A.links_per_werk()
    gedaan = config.load_json(A.PUBLICEER_PATH, {})
    uit = []
    for w in sorted(A.werken(), key=lambda w: (w["merk"], w["jaar"] or "9999", w["mapnaam"].lower())):
        if w["los"]:
            continue
        posts = [per_key[k] for k in lpw.get(w["pid"], []) if k in per_key]
        v = (w["tekst"] or {}).get("velden", {})
        uit.append({"merk": w["merk"], "map": w["mapnaam"], "jaar": w["jaar"],
                    "status": (w["yml"].get("caption_review") or "").strip(),
                    "ig": sum(1 for p in posts if p["platform"] == "ig"),
                    "fb": sum(1 for p in posts if p["platform"] == "fb"),
                    "accounts": sorted({p["account"] for p in posts}),
                    "gedaan": sum(1 for p in posts if p["key"] in gedaan),
                    "en": bool(v.get("Caption EN", "").strip()),
                    "beelden": sum(1 for m in w["media"] if m["type"] == "img"),
                    "videos": sum(1 for m in w["media"] if m["type"] != "img")})
json.dump(uit, open(os.path.join(config.DATA_DIR, "_dump_ongepromoot.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("werken", len(uit), "gedaan-posts", len(gedaan), "van", sum(r["ig"] + r["fb"] for r in uit))
for r in uit:
    if r["ig"] == 0 or r["fb"] == 0:
        print(f'{r["merk"]:8} | {r["map"][:45]:45} | ig {r["ig"]} fb {r["fb"]} | {r["status"] or "open":9} | en {"j" if r["en"] else "n"} | img {r["beelden"]} vid {r["videos"]} | {",".join(r["accounts"])}')
