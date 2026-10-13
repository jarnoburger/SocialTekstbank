"""Droge test (alleen GET): /nieuw + Publiceer blijft werken."""
import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
c = A.app.test_client()
with A.app.test_request_context():
    ws = A._nm_werken()
print("werken met nieuw materiaal:", len(ws), "| zonder concept:", [w["mapnaam"] for w, b, cc in ws if not cc])
r = c.get("/nieuw"); print("nieuw", r.status_code, r.headers.get("Location"))
fout = []
for w, b, cc in ws:
    rr = c.get("/nieuw/" + A._nm_sleutel(w))
    h = rr.data.decode("utf-8")
    if rr.status_code != 200 or "Advies Claude" not in h:
        fout.append((w["mapnaam"], rr.status_code))
print("pagina's met fout:", fout)
print("posten", c.get("/posten").status_code, "| planning", c.get("/planning").status_code, "| plannen", c.get("/plannen").status_code)
