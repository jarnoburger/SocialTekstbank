"""Droge test (alleen GET): nieuwe Publiceer (/posten) en menu."""
import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
c = A.app.test_client()
for d in ("ig-sjb", "fb-sjb", "ig-lichtjes", "fb-lichtjes"):
    r = c.get(f"/posten?doel={d}")
    loc = r.headers.get("Location", "")
    h = c.get(loc).data.decode("utf-8") if loc else ""
    print(d, r.status_code, loc[:50], "| kopieer" in h and "", "Kopieer tekst" in h, "alt-tekst" in h, "origineel" in h, h.count('class="ps-beeld"'))
with A.app.test_request_context():
    for d in ("ig-sjb", "fb-sjb"):
        v, g = A._planning_lijst(d)
        print(d, "gepland", len(v), "gepost", len(g))
        w = A.werk_map()[v[0]]
        bs = A._post_beelden(w)
        print("  eerste:", w["mapnaam"], "beelden", len(bs), "met alt", sum(1 for b in bs if b["alt"]), "met origineel", sum(1 for b in bs if b["origineel"]))
        if bs and bs[0]["origineel"]:
            print("  origineel status", c.get(bs[0]["origineel"]).status_code)
for u in ("/", "/plannen", "/planning", "/publiceer", "/lokaal", "/captions"):
    print(u, c.get(u).status_code)
