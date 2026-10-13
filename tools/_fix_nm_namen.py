"""nieuw_materiaal.json: sleutels (werkmap-paden) bijwerken na hernoemen/verplaatsen; toont stand nieuw_besluit."""
import os, sys, json
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
HERNOEMD = {"2008 videotechniek": "Videotechniek", "2026 madja": "2026 Majda Vidakovic"}
with A.app.test_request_context():
    ws = [w for w in A.werken(herscan=True) if not w["los"]]
    nm = config.load_json(A.NM_PATH, {})
    nieuw = {}
    for pad, best in nm.items():
        naam = HERNOEMD.get(os.path.basename(pad).lower(), os.path.basename(pad))
        w = next((x for x in ws if x["mapnaam"].lower() == naam.lower()), None)
        nieuw[w["pad"] if w else pad] = best
        if w and w["pad"] != pad:
            print("sleutel:", pad, "->", w["pad"])
    config.save_json(A.NM_PATH, nieuw)
    print("besluiten:", json.dumps(config.load_json(A.NM_BESLUIT_PATH, {}), ensure_ascii=False, indent=0)[:1500])
