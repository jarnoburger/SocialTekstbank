"""Zet yml-sleutels en/of voegt tekst toe aan velden van _tekst.md, per werk.

python tools/zet_velden.py data/zet.json [--doe]
JSON: [{"merk": "SJB", "mapnaam": "...", "yml": {"opdrachtgever": "..."},
        "prepend": {"Credits": "regel"}, "append": {"Crosslinks": "tekst"}}]
Prepend/append wordt overgeslagen als de tekst er al in staat.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import local, textfile  # noqa: E402

DOE = "--doe" in sys.argv
taken = json.load(open(sys.argv[1], encoding="utf-8"))
per = {(w["merk"], w["mapnaam"]): w for w in A.werken(herscan=True)}
for t in taken:
    w = per.get((t["merk"], t["mapnaam"]))
    if not w:
        print("NIET GEVONDEN:", t["mapnaam"])
        continue
    d = w["tekst"] or textfile.leeg()
    wijz = []
    for veld, regel in t.get("prepend", {}).items():
        oud = d["velden"].get(veld, "")
        if textfile.norm(regel) not in textfile.norm(oud):
            d["velden"][veld] = (regel + "\n" + oud).strip()
            wijz.append(f"{veld}+")
    for veld, regel in t.get("append", {}).items():
        oud = d["velden"].get(veld, "")
        if textfile.norm(regel) not in textfile.norm(oud):
            d["velden"][veld] = (oud.rstrip() + "\n\n" + regel).strip()
            wijz.append(f"+{veld}")
    for k, v in t.get("yml", {}).items():
        if w["yml"].get(k) != v:
            wijz.append(f"yml:{k}")
            if DOE:
                local.zet_yml(w["pad"], k, v)
    if DOE and any(not x.startswith("yml:") for x in wijz):
        textfile.schrijf(w["pad"], d)
    print(f"{w['mapnaam']:32} {', '.join(wijz) or 'niets te doen'}")
if not DOE:
    print("Proefrun. Schrijven met --doe")
