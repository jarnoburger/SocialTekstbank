"""Eenmalig: Done/ToDo-mappen opheffen. Status gaat naar _project.yml (promotie: gepromoot | te promoten).

python tools/flatten_status.py         -> proefrun
python tools/flatten_status.py --doe   -> uitvoeren (os.rename, geen downloads)
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config, local  # noqa: E402

DOE = "--doe" in sys.argv
cfg = config.load_config()
acties, fouten = [], []


def status_voor(container_naam):
    return "gepromoot" if "done" in container_naam.lower() else "te promoten"


def verzamel(root, d, status):
    for e in sorted(os.scandir(d), key=lambda x: x.name.lower()):
        if e.name.lower() == "desktop.ini" or e.name == "_project.yml":
            continue
        if e.is_dir():
            if e.name.lower() in ("_los", "los"):
                for f in os.scandir(e.path):
                    if f.is_file() and f.name.lower() != "desktop.ini":
                        acties.append(("los", f.path, os.path.join(root, "_Los", f.name), None))
                    elif f.is_dir():
                        acties.append(("werk", f.path, os.path.join(root, f.name), status))
            elif local.is_container(e.name):
                verzamel(root, e.path, status)
            else:
                acties.append(("werk", e.path, os.path.join(root, e.name), status))
        elif e.is_file():
            acties.append(("los", e.path, os.path.join(root, "_Los", e.name), None))


containers = []
for r in cfg["roots"]:
    root = r["pad"]
    for e in os.scandir(root):
        if e.is_dir() and local.is_container(e.name) and e.name.lower() not in ("_los", "los"):
            containers.append(e.path)
            verzamel(root, e.path, status_voor(e.name))

# botsingen
gezien = set()
for i, (soort, van, naar, st) in enumerate(acties):
    k = os.path.normcase(naar)
    if k in gezien or (os.path.exists(naar) and os.path.normcase(van) != k):
        if soort == "los":
            stam, ext = os.path.splitext(naar)
            naar = f"{stam} (2){ext}"
            acties[i] = (soort, van, naar, st)
            k = os.path.normcase(naar)
        else:
            fouten.append(f"bestaat al / dubbel: {naar}")
    gezien.add(k)

kort = lambda p: p.split("OneDrive")[-1]
for soort, van, naar, st in acties:
    if soort == "werk":
        print(f"  [{st:11}] {kort(van)}  ->  {kort(naar)}")
print(f"\nwerken: {sum(1 for a in acties if a[0]=='werk')} · losse bestanden naar _Los: {sum(1 for a in acties if a[0]=='los')}")
print("containers die leeg achterblijven:", [kort(c) for c in containers])
print("FOUTEN:", fouten or "geen")
if not DOE:
    print("\nProefrun: niets veranderd. Uitvoeren met --doe")
    sys.exit(0)
if fouten:
    sys.exit("Gestopt vanwege fouten.")

shutil.copy(config.LINKS_PATH, config.LINKS_PATH.replace(".json", ".backup-flatten.json"))
links = config.load_json(config.LINKS_PATH, {})
log = []
for soort, van, naar, st in acties:
    try:
        if soort == "werk" and st and not os.path.basename(van).startswith("_"):
            if not local.promotie_status(local.lees_yml(os.path.join(van, "_project.yml"))):
                local.zet_yml(van, "promotie", st)
        os.makedirs(os.path.dirname(naar), exist_ok=True)
        os.rename(van, naar)
        if soort == "werk":
            oud_pid, nieuw_pid = local.pid_voor(van), local.pid_voor(naar)
            for v in links.values():
                if v["pid"] == oud_pid:
                    v["pid"], v["pad"] = nieuw_pid, naar
        log.append({"soort": soort, "van": van, "naar": naar, "ok": True})
    except OSError as e:
        log.append({"soort": soort, "van": van, "naar": naar, "ok": False, "fout": str(e)})
        print("FOUT", kort(van), e)
config.save_json(config.LINKS_PATH, links)
config.save_json(os.path.join(config.DATA_DIR, "flatten-log.json"), log)
print(f"Klaar: {sum(1 for x in log if x['ok'])} ok, {sum(1 for x in log if not x['ok'])} fouten.")
