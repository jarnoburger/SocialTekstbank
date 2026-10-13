"""Hernoemt meerdere werken in één keer (koppelingen + beeldmanifesten verhuizen mee).

python tools/hernoem_batch.py            -> proefrun
python tools/hernoem_batch.py --doe      -> uitvoeren
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config  # noqa: E402

DOE = "--doe" in sys.argv

# (merk, huidige mapnaam, nieuwe mapnaam, jaar voor _project.yml of None)
LIJST = [
    ("Lichtjes", "2006 2 Days Art Dome", "2006 TodaysArt Dome", None),
    ("Lichtjes", "2006-2023 Play", "2005 Play Festival Museumplein", "2005"),
    ("SJB", "2017 KraakPandje", "2002 KraakPandje", "2002"),
    ("SJB", "2017 Carrera", "2017 Carwaii", None),
    ("SJB", "2014 Carwai", "2014 Carwaii", None),
    ("SJB", "2016 Tress", "2016 Tre (3 Italia)", None),
    ("SJB", "2016 Motolino", "2016 Mottolino", None),
    ("SJB", "2017 Monnini", "2017 Monini", None),
    ("SJB", "2017 Hotwheels", "2017 Hot Wheels", None),
    ("SJB", "2014 Majda", "2014 Mayda", None),
    ("SJB", "2020 SchoneBakkes", "2020 Schone Bakkes", None),
    ("SJB", "2025 Lilian Kreuzberger", "2025 Lilian Kreutzberger", None),
    ("SJB", "Mechantronics", "Mechatronics", None),
    ("SJB", "Sound Symthesis", "Sound Synthesis", None),
]

ws = A.werken(herscan=True)
per_naam = {(w["merk"], w["mapnaam"]): w for w in ws}
plan, fouten = [], []
for merk, oud, nieuw, jaar in LIJST:
    w = per_naam.get((merk, oud))
    if not w:
        fouten.append(f"niet gevonden: {merk} / {oud}")
        continue
    if os.path.exists(os.path.join(os.path.dirname(w["pad"]), nieuw)):
        fouten.append(f"bestaat al: {merk} / {nieuw}")
        continue
    plan.append((w, nieuw, jaar))
    print(f"[{merk:8}] {oud:28} -> {nieuw}" + (f"  (jaar {jaar})" if jaar else ""))
print("FOUTEN:", fouten or "geen")
if not DOE:
    print("Proefrun. Uitvoeren met --doe")
    sys.exit(0)

manifests = [os.path.join(config.DATA_DIR, "beelden", d, "manifest.json")
             for d in os.listdir(os.path.join(config.DATA_DIR, "beelden"))
             if os.path.exists(os.path.join(config.DATA_DIR, "beelden", d, "manifest.json"))]
mdata = {m: config.load_json(m, []) for m in manifests}
log = []
for w, nieuw, jaar in plan:
    for poging in range(3):
        try:
            nieuw_pid = A.hernoem_werk(w, nieuw, jaar)
            break
        except OSError as e:
            if poging == 2:
                print("FOUT", w["mapnaam"], e)
                log.append({"oud": w["mapnaam"], "nieuw": nieuw, "ok": False, "fout": str(e)})
                nieuw_pid = None
            else:
                time.sleep(15)  # OneDrive-lock
    if not nieuw_pid:
        continue
    for lijst in mdata.values():
        for x in lijst:
            if x.get("pid") == w["pid"]:
                x["pid"], x["mapnaam"] = nieuw_pid, nieuw
    log.append({"oud": w["mapnaam"], "nieuw": nieuw, "pid_oud": w["pid"], "pid_nieuw": nieuw_pid, "ok": True})
    print("ok:", w["mapnaam"], "->", nieuw)
for m, lijst in mdata.items():
    config.save_json(m, lijst)
config.save_json(os.path.join(config.DATA_DIR, "hernoem-batch-log.json"), log)
print(f"Klaar: {sum(1 for x in log if x['ok'])} ok, {sum(1 for x in log if not x['ok'])} fouten.")
