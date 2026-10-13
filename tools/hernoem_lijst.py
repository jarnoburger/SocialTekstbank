"""Hernoemt werken volgens een JSON-lijst (koppelingen + beeldmanifesten verhuizen mee).
Zelfde werking als hernoem_batch.py, maar de lijst komt uit een bestand.

python tools/hernoem_lijst.py data/hernoem.json          -> proefrun
python tools/hernoem_lijst.py data/hernoem.json --doe    -> uitvoeren
JSON: [["SJB", "huidige mapnaam", "nieuwe mapnaam", "jaar of null"], ...]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config  # noqa: E402

DOE = "--doe" in sys.argv
LIJST = json.load(open(sys.argv[1], encoding="utf-8"))

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
    print(f"[{merk:8}] {oud:40} -> {nieuw}" + (f"  (jaar {jaar})" if jaar else ""))
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
    nieuw_pid = None
    for poging in range(3):
        try:
            nieuw_pid = A.hernoem_werk(w, nieuw, jaar)
            break
        except OSError as e:
            if poging == 2:
                print("FOUT", w["mapnaam"], e)
                log.append({"oud": w["mapnaam"], "nieuw": nieuw, "ok": False, "fout": str(e)})
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
logpad = os.path.join(config.DATA_DIR, "hernoem-lijst-log-" + time.strftime("%Y%m%d-%H%M%S") + ".json")
config.save_json(logpad, log)
print(f"Klaar: {sum(1 for x in log if x['ok'])} ok, {sum(1 for x in log if not x['ok'])} fouten. Log: {logpad}")
