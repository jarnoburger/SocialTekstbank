"""Zet de 5 exact-dubbele video's (sha1 gelijk aan werkbestand) op 'dubbel' in los_besluit.json."""
import os, sys, datetime as dt
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
rap = config.load_json(os.path.join(config.DATA_DIR, "_check_los_dubbel.json"), {})["rapport"]
exact = {r["bestand"]: r["exact"][0] for r in rap if r["exact"]}
with A.app.test_request_context():
    bes = config.load_json(A.LOS_BESLUIT_PATH, {})
    n = 0
    for w in A.werken(herscan=True):
        if not w["los"]:
            continue
        for m in w["media"]:
            if m["naam"] in exact:
                k = f"{w['pid']}|{m['rel']}"
                oud = bes.get(k, {})
                bes[k] = {"actie": "dubbel", "pid": "", "naam": "", "merk": w["merk"], "bestand": m["naam"],
                          "dubbel_van": exact[m["naam"]], "was": oud.get("actie"),
                          "op": dt.datetime.now().isoformat(timespec="seconds")}
                n += 1
                print("dubbel:", m["naam"], "->", exact[m["naam"]], "(was:", oud.get("actie"), ")")
    config.save_json(A.LOS_BESLUIT_PATH, bes)
    print(n, "gezet")
