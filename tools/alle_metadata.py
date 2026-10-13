"""Leest naam, wijzig- en aanmaakdatum en grootte van alle bestanden in de roots (alleen metadata, geen download)."""
import datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
uit = []
for r in config.load_config()["roots"]:
    for d, dirs, files in os.walk(r["pad"]):
        dirs[:] = [x for x in dirs if x.lower() not in {".git", "lib", "node_modules", "library", "obj", "bin"}]
        for f in files:
            if f.lower() == "desktop.ini":
                continue
            p = os.path.join(d, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            rel = os.path.relpath(p, r["pad"])
            uit.append("\t".join([r["merk"], rel, dt.date.fromtimestamp(st.st_mtime).isoformat(),
                                  dt.date.fromtimestamp(st.st_ctime).isoformat(), str(st.st_size)]))
with open(os.path.join(config.DATA_DIR, "allebestanden.tsv"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(uit))
print("regels", len(uit))
