"""Voegt FB-profielen van samenwerkers toe aan Crosslinks (bovenaan). Proefrun standaard; --doe schrijft (met backup)."""
import sys, os, json, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import local, textfile, config
DOE = "--doe" in sys.argv
PERSONEN = {  # naam -> FB (Jarno 04-10-2026). Geen IG-handle bekend.
    "Clement": "https://www.facebook.com/clemcore",
    "Rob Martens": "https://www.facebook.com/rob.pimander",
    "Jelle Mens": "https://www.facebook.com/jelle.mens.9",
    "Folkert Smitstra": "https://www.facebook.com/folkert.smitstra",
    "Lilian Kreutzberger": "https://www.facebook.com/lilian.kreutzberger",
}
PER_WERK = {
    "2002 Photonic Visuals": ["Clement"],
    "2006 TodaysArt": ["Rob Martens"],
    "2018-2021 Reindier": ["Jelle Mens", "Folkert Smitstra"],
    "2024 Lilian Kreutzberger": ["Lilian Kreutzberger"],
    "2025 Studio Vodka": ["Lilian Kreutzberger"],
}
EXTRA = {"2006 Pink Floyd": "Aike Dirkzwager: NIET taggen (Jarno 04-10-2026)."}
werken = {w["mapnaam"]: w for w in local.scan(config.load_config()["roots"]) if not w["los"]}
stamp = time.strftime("%Y%m%d-%H%M%S"); log, fouten = [], []
zf = zipfile.ZipFile(os.path.join(config.DATA_DIR, f"tekst-backup-fb-{stamp}.zip"), "w") if DOE else None
for m in sorted(set(PER_WERK) | set(EXTRA)):
    w = werken.get(m)
    if not w:
        fouten.append(f"niet gevonden: {m}"); continue
    data = textfile.lees(w["pad"]) or textfile.leeg()
    cl = data["velden"].get("Crosslinks", "")
    regels = [f"FB-tag (Jarno 04-10-2026): {n} · {PERSONEN[n]}" for n in PER_WERK.get(m, []) if PERSONEN[n] not in cl]
    if m in EXTRA and EXTRA[m] not in cl:
        regels.append(EXTRA[m])
    if not regels:
        continue
    data["velden"]["Crosslinks"] = "\n".join(regels) + "\n\n" + cl
    log.append({"map": m, "regels": regels})
    if DOE:
        zf.write(textfile.pad_voor(w["pad"]), arcname=f"{w['merk']}/{m}/_tekst.md")
        textfile.schrijf(w["pad"], data)
if zf: zf.close()
json.dump(PERSONEN, open(os.path.join(config.DATA_DIR, "personen_fb.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1) if DOE else None
print("DOE" if DOE else "PROEFRUN", "| werken:", len(log))
for l in log: print(" ", l["map"], "->", "; ".join(l["regels"]))
for f in fouten: print(" -", f)
