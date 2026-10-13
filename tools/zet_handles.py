"""Zet @handles in captions/credits volgens data/handles_20261004.json + noteert gekozen handles in Crosslinks.
Proefrun standaard; --doe om te schrijven. Backup van gewijzigde _tekst.md in data/tekst-backup-handles-*.zip."""
import sys, os, json, re, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import local, textfile, config

DOE = "--doe" in sys.argv
EDITS = json.load(open(os.path.join(config.DATA_DIR, "handles_20261004.json"), encoding="utf-8"))
GEKOZEN = {  # verliezer -> winnaar (keuze Jarno 04-10-2026)
    "liefs.lies_": "liefs.lies", "krollermuller": "krollermullermuseum", "carrera": "carrera.official",
    "reindier__": "reindierworld", "studiophilipvermeulen": "philipvermeulen_3000",
    "extrema.be": "extremaoutdoor", "fanta": "fantaeurope", "mottolinolivigno": "mottolinobikepark"}
RX = r"(?<![\w.])@([A-Za-z0-9_.]*[A-Za-z0-9_])"

werken = {w["mapnaam"]: w for w in local.scan(config.load_config()["roots"]) if not w["los"]}
per_map = {}
for e in EDITS:
    per_map.setdefault(e["map"], []).append(e)
for m, w in werken.items():
    cl = (w["tekst"] or textfile.leeg())["velden"].get("Crosslinks", "")
    if any(h.lower() in GEKOZEN for h in re.findall(RX, cl)):
        per_map.setdefault(m, [])

log, fouten = [], []
stamp = time.strftime("%Y%m%d-%H%M%S")
zp = os.path.join(config.DATA_DIR, f"tekst-backup-handles-{stamp}.zip")
zf = zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) if DOE else None
for m, edits in sorted(per_map.items()):
    w = werken.get(m)
    if not w:
        fouten.append(f"werk niet gevonden: {m}"); continue
    if (w["yml"].get("caption_review") or "").strip() == "overslaan":
        fouten.append(f"overgeslagen (niet posten): {m}"); continue
    data = textfile.lees(w["pad"])
    if not data:
        fouten.append(f"geen _tekst.md: {m}"); continue
    v = data["velden"]; wijz = []
    for e in edits:
        t = v.get(e["veld"], "")
        if t.count(e["oud"]) != 1:
            fouten.append(f"{m} [{e['veld']}] tekst niet (eenmalig) gevonden: {e['oud'][:60]}"); continue
        v[e["veld"]] = t.replace(e["oud"], e["nieuw"]); wijz.append((e["veld"], e["oud"], e["nieuw"]))
    cl = v.get("Crosslinks", "")
    los = sorted({h.lower() for h in re.findall(RX, cl) if h.lower() in GEKOZEN})
    if los and "Gekozen IG-handle" not in cl:
        regel = "Gekozen IG-handle (Jarno 04-10-2026): " + ", ".join(f"@{GEKOZEN[h]} (niet @{h})" for h in los) + "."
        v["Crosslinks"] = regel + "\n\n" + cl; wijz.append(("Crosslinks", "", regel))
    if wijz:
        log.append({"map": m, "wijz": wijz})
        if DOE:
            zf.write(textfile.pad_voor(w["pad"]), arcname=f"{w['merk']}/{m}/_tekst.md")
            textfile.schrijf(w["pad"], data)
if zf:
    zf.close()
json.dump({"doe": DOE, "log": log, "fouten": fouten},
          open(os.path.join(config.DATA_DIR, f"handles-log-{stamp}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DOE" if DOE else "PROEFRUN", "| werken:", len(log), "| wijzigingen:", sum(len(l["wijz"]) for l in log))
for f in fouten:
    print(" -", f)
