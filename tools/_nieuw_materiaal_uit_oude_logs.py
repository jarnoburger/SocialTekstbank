"""Vult data/nieuw_materiaal.json ook met de eerdere los-uitvoer-logs (bestanden die al eerder naar werken gingen)."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
NM = os.path.join(config.DATA_DIR, "nieuw_materiaal.json")
nm = config.load_json(NM, {})
for f in sorted(glob.glob(os.path.join(config.DATA_DIR, "los-uitvoer-log-*.json"))):
    for x in config.load_json(f, []):
        if x.get("ok") and x.get("actie") in ("werk", "nieuw") and os.path.exists(x["naar"]):
            lijst = nm.setdefault(os.path.dirname(x["naar"]), [])
            if os.path.basename(x["naar"]) not in lijst:
                lijst.append(os.path.basename(x["naar"]))
config.save_json(NM, nm)
print(len(nm), "werkmappen met nieuw materiaal,", sum(len(v) for v in nm.values()), "bestanden")
for k, v in sorted(nm.items()):
    print(f"{len(v):3}  {k}")
