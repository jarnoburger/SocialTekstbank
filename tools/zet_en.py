"""Zet Caption EN = vertaling van Jarno's laatste Caption NL (data/en_vertaling_20261004.json).
Alleen als de NL sinds de vertaling niet meer veranderd is. Proefrun standaard; --doe schrijft (met backup)."""
import sys, os, json, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import local, textfile, config
DOE = "--doe" in sys.argv
V = json.load(open(os.path.join(config.DATA_DIR, "en_vertaling_20261004.json"), encoding="utf-8"))
n = lambda s: " ".join((s or "").split())
werken = {w["mapnaam"]: w for w in local.scan(config.load_config()["roots"]) if not w["los"]}
stamp = time.strftime("%Y%m%d-%H%M%S"); ok, fout = [], []
zf = zipfile.ZipFile(os.path.join(config.DATA_DIR, f"tekst-backup-en-{stamp}.zip"), "w") if DOE else None
for m, v in sorted(V.items()):
    w = werken.get(m)
    if not w:
        fout.append(f"niet gevonden: {m}"); continue
    d = textfile.lees(w["pad"])
    if n(d["velden"].get("Caption NL")) != n(v["nl"]):
        fout.append(f"NL intussen gewijzigd, overgeslagen: {m}"); continue
    if n(d["velden"].get("Caption EN")) == n(v["en"]):
        continue
    ok.append(m)
    if DOE:
        zf.write(textfile.pad_voor(w["pad"]), arcname=f"{w['merk']}/{m}/_tekst.md")
        d["velden"]["Caption EN"] = v["en"]
        textfile.schrijf(w["pad"], d)
if zf: zf.close()
print("DOE" if DOE else "PROEFRUN", "| EN bijgewerkt:", len(ok))
for f in fout: print(" -", f)
