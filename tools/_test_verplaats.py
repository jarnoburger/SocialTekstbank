"""Droge test van de verplaats-markering: schrijft naar een tijdelijk bestand, raakt _tekst.md/yml niet aan."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app
tmp = os.path.join(tempfile.gettempdir(), "verplaats_test.json")
if os.path.exists(tmp):
    os.remove(tmp)
app.VERPLAATS_PATH = tmp
app.textfile.schrijf = lambda *a, **k: None
app.local.zet_yml = lambda *a, **k: None
c = app.app.test_client()
pid = "1c820f716f"  # 1998-2008 Lowlands
w = app.werk_map()[pid]
doel = [x for x in app.werken() if x["mapnaam"] == "Led Mapping"][0]
label = app._werk_label(doel)
r = c.post(f"/review/{pid}", data={"actie": "", "notitie": w["yml"].get("review_notitie", ""),
                                    "verpl::post:ig:TEST": label, "verpl::lokaal:x:y.jpg": "Nieuw Testwerk"})
print("POST", r.status_code, json.dumps(json.load(open(tmp, encoding="utf-8")), ensure_ascii=False)[:400])
r = c.post(f"/review/{pid}", data={"actie": "", "notitie": w["yml"].get("review_notitie", ""),
                                    "verpl::post:ig:TEST": "", "verpl::lokaal:x:y.jpg": "Nieuw Testwerk"})
print("WIS", r.status_code, list(json.load(open(tmp, encoding="utf-8")).keys()))
print("lijst", c.get("/review/verplaats").status_code)
