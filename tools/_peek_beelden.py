import os, sys, json
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
with A.app.test_request_context():
    ws = A._plan_werken()
    bidx = A.beelden_index()
    w = ws[3]
    print(w["mapnaam"])
    for b in (bidx.get(w["pid"]) or [])[:3]:
        print("manifest:", json.dumps(b, ensure_ascii=False)[:300])
    v = w["tekst"]["velden"]
    al, alts, tw = A._alt_teksten(v.get("Beeldbeschrijving", ""))
    for bron, alt in alts[:3]:
        print("alt:", bron[:120], "=>", alt[:80])
    print("Jaar en plek:", v.get("Jaar en plek", "")[:120])
    print("Crosslinks:", v.get("Crosslinks", "")[:400])
    print("velden:", list(v.keys()))
    print("media[0]:", w["media"][0] if w["media"] else None)
