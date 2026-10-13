"""Alleen lezen: stand van los_besluit.json voor de resterende _Los-items."""
import os, sys, collections, json
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
lijst = A._los_lijst()
bes = config.load_json(A.LOS_BESLUIT_PATH, {})
print("bestand gewijzigd:", __import__("datetime").datetime.fromtimestamp(os.path.getmtime(A.LOS_BESLUIT_PATH)))
tel = collections.Counter()
recent = 0
for r in lijst:
    b = bes.get(A._los_sleutel(r))
    stam = os.path.splitext(r["naam"])[0]
    if not b:
        s = "GEEN besluit"
    elif b["actie"] == "nieuw":
        s = "nieuw, naam = bestandsnaam" if b.get("naam") == stam else "nieuw, eigen naam"
    else:
        s = b["actie"]
    tel[s] += 1
    if b and b.get("op", "") >= "2026-10-06T13:55":
        recent += 1
for k, v in tel.most_common():
    print(f"{v:3}  {k}")
print("na 13:55 opgeslagen:", recent)
namen = collections.Counter(b.get("naam") for b in bes.values() if b.get("actie") == "nieuw" and b.get("naam"))
print("namen:", namen.most_common(40))
werk = collections.Counter(A.werk_map().get(b.get("pid"), {}).get("mapnaam", b.get("pid")) for b in bes.values() if b.get("actie") == "werk")
print("naar werk:", werk.most_common())
