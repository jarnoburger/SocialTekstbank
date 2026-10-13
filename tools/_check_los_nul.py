"""Alleen lezen: welke hashes-sleutels geven afstand <=10 voor de losse foto's (eigen bestand uitgesloten)?"""
import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config, match as M
from PIL import Image
hs = config.load_json(os.path.join(config.DATA_DIR, "hashes.json"), {})
with A.app.test_request_context():
    for w in A.werken(herscan=True):
        if not w["los"]:
            continue
        for m in w["media"]:
            if m["type"] != "img":
                continue
            dh = M.dhash_img(Image.open(m["pad"]))
            hits = []
            for sec in ("lokaal", "online"):
                for k, v in hs.get(sec, {}).items():
                    if not isinstance(v, (int, float)):
                        continue
                    if sec == "lokaal" and os.path.basename(k.split("|")[0]).lower() == m["naam"].lower():
                        continue  # zichzelf (oude of huidige plek)
                    d = M.afstand(dh, int(v))
                    if d <= 10:
                        hits.append((d, sec, k.split("|")[0][-90:], os.path.exists(k.split("|")[0]) if sec == "lokaal" else ""))
            if hits:
                print(m["naam"], sorted(hits)[:3])
