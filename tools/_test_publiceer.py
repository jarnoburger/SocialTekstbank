import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import app as A
c = A.app.test_client()
r = c.get("/publiceer")
print("start", r.status_code, r.headers.get("Location"))
with A.app.test_request_context():
    for s in A._stappen_tel():
        print(s["id"], s["werken"], "werken", s["posts"], "posts", s["open"], "open")
    ws = A._publiceer_werken("sjb-ig")
for st in ("sjb-ig", "sjb-fb", "lichtjes-ig", "lichtjes-fb"):
    r = c.get(f"/publiceer?stap={st}", follow_redirects=True)
    h = r.data.decode("utf-8")
    print(st, r.status_code, "Open post" in h, "Kopieer tekst" in h)
with A.app.test_request_context():
    last = A._publiceer_werken("sjb-ig")[-1]["pid"]
h = c.get(f"/publiceer/sjb-ig/{last}").data.decode("utf-8")
print("laatste sjb-ig toont 'Naar volgende stap':", "Naar volgende stap" in h)
