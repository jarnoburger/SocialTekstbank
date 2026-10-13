"""Alleen lezen: wat weten we al over de bestanden in _Los (beschrijvingen, hashes, matches)?"""
import os, sys, json, glob, collections
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
D = config.DATA_DIR
with A.app.test_request_context():
    ws = A.werken(herscan=True)
    los = [w for w in ws if w["los"]]
    namen = {m["naam"]: (w["merk"], m) for w in los for m in w["media"]}
    print("los-bestanden:", len(namen))
    # 1. komen de namen voor in data-bestanden?
    for f in sorted(glob.glob(os.path.join(D, "*.json")) + glob.glob(os.path.join(D, "beelden", "*", "manifest.json"))):
        if "backup" in f or "log" in os.path.basename(f):
            continue
        t = open(f, encoding="utf-8").read()
        n = sum(1 for nm in namen if nm in t)
        if n:
            print(f"  {os.path.relpath(f, D):40} noemt {n} los-bestanden")
    # 2. hashes.json structuur
    h = config.load_json(os.path.join(D, "hashes.json"), {})
    print("hashes.json type", type(h).__name__, "n", len(h))
    if isinstance(h, dict):
        k0 = next(iter(h)); print("  voorbeeld sleutel", k0[:120], "->", str(h[k0])[:160])
        los_keys = [k for k in h if "_Los" in k or any(nm in k for nm in list(namen)[:400])]
        print("  sleutels met _Los:", len(los_keys))
    # 3. _tekst.md in _Los?
    for w in los:
        print(w["merk"], "_tekst.md in _Los:", os.path.exists(os.path.join(w["pad"], "_tekst.md")), "| tekst-velden:", list((w["tekst"] or {}).get("velden", {}).keys())[:6])
    # 4. match-module: is er een functie voor beeld-vergelijk?
    import core.match as M
    print("match-functies:", [n for n in dir(M) if not n.startswith("__")][:40])
