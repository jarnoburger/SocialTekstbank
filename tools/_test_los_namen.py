"""Droge test (alleen GET): /los/namen."""
import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
c = A.app.test_client()
r = c.get("/los/namen")
h = r.data.decode("utf-8")
print("status", r.status_code, "| kaarten", h.count('class="ln-kaart'), "| 'lijkt wat op'", h.count("lijkt wat op"),
      "| Drone-voorstel", h.count('value="2021 Drone"'), "| video's", h.count("<video class"))
print("los", c.get("/los").status_code)
