"""Droge test (alleen GET): /plannen en /planning."""
import os, sys, collections
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import app as A
c = A.app.test_client()
with A.app.test_request_context():
    ws = A._plan_werken()
    per_key = {p["key"]: p for p in A.online()["posts"]}
    lpw = A.links_per_werk()
    tel = collections.Counter()
    for w in ws:
        g = A._gepost_per_doel(w["pid"], per_key, lpw)
        e = [d for d, *_ in A._eigen_doelen(w)]
        tel[(w["merk"], "nergens" if not any(g[d] for d in e) else "1 van 2")] += 1
    print("in Plannen:", len(ws), dict(tel))
    alle = [w for w in A.werken() if not w["los"]]
    weg = [w for w in alle if w["pid"] not in {x["pid"] for x in ws}]
    print("weggelaten (al op beide):", len(weg))
r = c.get("/plannen")
loc = r.headers.get("Location")
print("plannen", r.status_code, loc, c.get(loc).status_code)
print("weggelaten werk ->", c.get(f"/plannen/{weg[0]['pid']}").status_code)
print("planning", c.get("/planning").status_code)
