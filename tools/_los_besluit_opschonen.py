"""Haalt uitgevoerde besluiten (bestand bestaat niet meer in _Los) uit los_besluit.json -> los_besluit_uitgevoerd.json."""
import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
with A.app.test_request_context():
    wm = A.werk_map()
    bes = config.load_json(A.LOS_BESLUIT_PATH, {})
    P2 = os.path.join(config.DATA_DIR, "los_besluit_uitgevoerd.json")
    klaar = config.load_json(P2, {})
    blijf = {}
    for k, b in bes.items():
        los_pid, rel = k.split("|", 1)
        lw = wm.get(los_pid)
        if lw and os.path.exists(os.path.join(lw["pad"], rel)):
            blijf[k] = b
        else:
            klaar[k] = b
    config.save_json(A.LOS_BESLUIT_PATH, blijf)
    config.save_json(P2, klaar)
    print("open besluiten", len(blijf), "| uitgevoerd", len(klaar))
