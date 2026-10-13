"""Zet los-besluiten 'nieuw: Amare' om naar 'werk: 2022 Amare' (keuze Jarno 06-10)."""
import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
with A.app.test_request_context():
    doel = next(w for w in A.werken(herscan=True) if not w["los"] and w["mapnaam"] == "2022 Amare")
    bes = config.load_json(A.LOS_BESLUIT_PATH, {})
    n = 0
    for k, b in bes.items():
        if b.get("actie") == "nieuw" and (b.get("naam") or "").strip().lower() == "amare":
            b.update(actie="werk", pid=doel["pid"], naam="", was_naam="Amare")
            n += 1
    config.save_json(A.LOS_BESLUIT_PATH, bes)
    print(n, "->", doel["pad"])
