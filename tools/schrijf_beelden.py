"""Schrijft beeldbeschrijvingen (JSON: [{pid, mapnaam, beeldbeschrijving}]) naar _tekst.md.
Bestaande Beeldbeschrijving wordt NIET overschreven (tenzij --overschrijf).
python tools/schrijf_beelden.py data/beelden_batch1.json [--doe] [--overschrijf]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STB_GEEN_BROWSER", "1")
import app as A  # noqa: E402
from core import textfile  # noqa: E402
bron = sys.argv[1]; DOE = "--doe" in sys.argv; OVER = "--overschrijf" in sys.argv
wm = A.werk_map()
for item in json.load(open(bron, encoding="utf-8")):
    w = wm.get(item["pid"]) or next((x for x in wm.values() if x["mapnaam"] == item["mapnaam"]), None)
    if not w:
        print("NIET GEVONDEN", item["mapnaam"]); continue
    data = textfile.lees(w["pad"]) or textfile.leeg()
    if data["velden"].get("Beeldbeschrijving", "").strip() and not OVER:
        print("overgeslagen (al gevuld):", w["mapnaam"]); continue
    data["velden"]["Beeldbeschrijving"] = item["beeldbeschrijving"]
    if DOE:
        textfile.schrijf(w["pad"], data)
    print(("geschreven: " if DOE else "proef: ") + w["mapnaam"])
