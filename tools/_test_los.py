"""Droge test (alleen GET): /los."""
import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
c = A.app.test_client()
r = c.get("/los"); print("los", r.status_code, r.headers.get("Location"))
lijst = A._los_lijst()
for i in (0, 1, 40, 70, 150, len(lijst) - 1):
    rr = c.get(f"/los/{i}")
    h = rr.data.decode("utf-8")
    print(i, rr.status_code, lijst[i]["soort"], lijst[i]["naam"][:30], "| voorstel geselecteerd:", "← voorstel" in h and "selected" in h,
          "| bestand", c.get(f"/origineel/{lijst[i]['los_pid']}/{lijst[i]['rel']}").status_code)
