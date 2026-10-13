"""Alleen lezen: welke data-bestanden bevatten pids (om bij verplaatsen mee te nemen)."""
import json, os, glob
D = os.path.join(os.path.dirname(__file__), "..", "data")
cfg = os.path.join(os.path.dirname(__file__), "..", "config.json")
if os.path.exists(cfg):
    c = json.load(open(cfg, encoding="utf-8"))
    print("config.json roots:", c.get("roots"))
links = json.load(open(os.path.join(D, "links.json"), encoding="utf-8"))
pids = {v["pid"] for v in links.values()}
for f in sorted(glob.glob(os.path.join(D, "*.json"))):
    if "backup" in f or os.path.basename(f).startswith("_"):
        continue
    try:
        t = open(f, encoding="utf-8").read()
    except Exception as e:
        print("??", f, e); continue
    n = sum(1 for p in pids if p in t)
    if n:
        print(f"{os.path.basename(f):35} {len(t)//1024:6} KB  bevat {n} pids")
for m in glob.glob(os.path.join(D, "beelden", "*", "manifest.json")):
    print("manifest", m)
