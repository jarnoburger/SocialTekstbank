"""Zet 'Opdrachtgever: X' bovenaan het veld Credits (_tekst.md) voor elk werk met opdrachtgever in _project.yml.
Slaat over als de opdrachtgever al in Credits staat.

python tools/sync_credits.py [--doe]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import textfile  # noqa: E402

DOE = "--doe" in sys.argv
n = 0
for w in A.werken(herscan=True):
    og = (w["yml"].get("opdrachtgever") or "").strip()
    if w["los"] or not og:
        continue
    d = w["tekst"] or textfile.leeg()
    c = d["velden"].get("Credits", "")
    kern = og.split("(")[0].strip().lower().replace("-", "").replace(" ", "")
    if kern and kern in c.lower().replace("-", "").replace(" ", ""):
        continue
    d["velden"]["Credits"] = (f"Opdrachtgever: {og}." + ("\n" + c if c.strip() else "")).strip()
    n += 1
    print(f"{w['mapnaam']:40} + Opdrachtgever: {og}")
    if DOE:
        textfile.schrijf(w["pad"], d)
print(n, "werken", "" if DOE else "(proefrun; schrijven met --doe)")
