"""Zoekt in bestands- en mapnamen onder de _To Promote-roots (alleen namen, geen downloads).
python tools/zoek_namen.py "<regex>"
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config  # noqa: E402

rx = re.compile(sys.argv[1], re.I)
per_werk = defaultdict(list)
for r in config.load_config()["roots"]:
    for d, dirs, files in os.walk(r["pad"]):
        for n in dirs + files:
            if rx.search(n):
                rel = os.path.relpath(os.path.join(d, n), r["pad"])
                per_werk[(r["merk"], rel.split(os.sep)[0])].append(rel)
for (merk, werk), lijst in sorted(per_werk.items()):
    print(f"{merk} | {werk} | {len(lijst)} | {lijst[:4]}")
print("werken:", len(per_werk))
