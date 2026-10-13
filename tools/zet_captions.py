"""Zet Caption NL+EN uit een JSON {map: {oud_nl, nl, en}} en zet caption_review terug op open.
Alleen als de huidige NL nog gelijk is aan oud_nl. Proefrun standaard; --doe schrijft (met backup).
Gebruik: python tools/zet_captions.py data/<bestand>.json [--doe]"""
import sys, os, json, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import local, textfile, config
args = [a for a in sys.argv[1:] if not a.startswith("--")]
DOE = "--doe" in sys.argv
V = json.load(open(args[0], encoding="utf-8"))
n = lambda s: " ".join((s or "").split())
werken = {w["mapnaam"]: w for w in local.scan(config.load_config()["roots"]) if not w["los"]}
zf = zipfile.ZipFile(os.path.join(config.DATA_DIR, f"tekst-backup-captions-{time.strftime('%Y%m%d-%H%M%S')}.zip"), "w") if DOE else None
ok, fout = [], []
for m, v in V.items():
    w = werken.get(m)
    if not w: fout.append(f"niet gevonden: {m}"); continue
    d = textfile.lees(w["pad"])
    if n(d["velden"].get("Caption NL")) != n(v["oud_nl"]): fout.append(f"NL intussen gewijzigd: {m}"); continue
    ok.append(m)
    if DOE:
        zf.write(textfile.pad_voor(w["pad"]), arcname=f"{w['merk']}/{m}/_tekst.md")
        d["velden"]["Caption NL"], d["velden"]["Caption EN"] = v["nl"], v["en"]
        textfile.schrijf(w["pad"], d)
        local.zet_yml(w["pad"], "caption_review", "")
if zf: zf.close()
print("DOE" if DOE else "PROEFRUN", "| captions:", len(ok), ok)
for f in fout: print(" -", f)
