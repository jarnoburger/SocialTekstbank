"""Eenmalig: verzamelbakken (1-5) platslaan, dubbele samenvoegen, namen/jaartallen normaliseren.

Gebruik:  python tools/herstructureer.py          -> proefrun (verandert niets)
          python tools/herstructureer.py --doe    -> uitvoeren
Alles via os.rename op hetzelfde volume: OneDrive downloadt niets. Log in data/herstructureer-log.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config, group, local, match, naming  # noqa: E402

DOE = "--doe" in sys.argv
cfg = config.load_config()
werken = local.scan(cfg["roots"])
roots = {r["merk"]: r["pad"] for r in cfg["roots"]}
links = config.load_json(config.LINKS_PATH, {})
groepen = group.maak_groepen(config.load_json(config.ONLINE_PATH, {"posts": []})["posts"])
sugg = match.bereken(werken, groepen)
jaren = {v["werk"]["pid"]: v["voorstel"] for v in match.jaar_voorstellen(werken, groepen, sugg, links)
         if v["zekerheid"] in ("hoog", "middel") and v["voorstel"]}

# Dubbele: rel (onder _To Promote) -> (rel van hoofdwerk, submapnaam)
SAMENVOEGEN = {
    "Done/4/Done/Pink FLoyd": ("Done/2011-2022 Pink Floyd", "Pink Floyd extra"),
    "Done/2/Done/Reindier": ("Done/2018-2021 Reindier", "Reindier extra"),
    "Done/4/Reindier Hoepel": ("Done/2018-2021 Reindier", "Hoepel extra"),
    "Done/4/Reindier Stage": ("Done/2018-2021 Reindier", "Stage extra"),
    "Done/3/Reindier Tentacle": ("Done/2018-2021 Reindier", "Tentacle extra"),
    "Done/4/Done/mayda": ("Done/Majda", "Mayda"),
    "Done/4/Photos Mayda": ("Done/Majda", "Photos"),
    "Done/3/Done/Fiber": ("Done/2020-2021 Fiber", "Fiber extra"),
    "Done/5/_DOne/State X": ("Done/2002-2008 State X", "State X extra"),
    "Done/5/_DOne/PCB": ("Done/4/PCB", "PCB extra"),            # 4/PCB wordt zelf '2021 PCB'
    "Done/4/Done/3D Printing": ("Done/5/3D Printer", "3D Printing"),  # wordt '2021 3D Printer'
}
NAAM_OVERRIDE = {"Done/3/_Judocus": "Judocus"}

YML_SJABLOON = """# _project.yml - portfolio-metadata (aangemaakt door SocialTekstbank; vrij te bewerken)
# Formaat: 'sleutel: waarde' per regel; lijsten komma-gescheiden; leeg = onbekend.
naam: {naam}
# type: project | wereld | cnc | machine | act
type: project
jaar: {jaar}
# discipline: VJ, INST, 3D, MAKE, THEA, 360 (komma's)
discipline:
rol:
opdrachtgever:
# doelen: S=subsidie L=lening T=sollicitatie F=festival (komma's)
doelen:
# status: done | todo | wip
status: {status}
# promotie: Instagram: gepromoot (map Done) | nog te promoten (map ToDo) | deels
promotie:
beste_beelden:
duplicaat_van:
notitie: {notitie}
"""


def in_bak(rel):
    delen = rel.split("/")
    return len(delen) > 2 and delen[0] == "Done" and local.is_container(delen[1])


acties, fouten = [], []
per_rel = {(w["merk"], w["rel"]): w for w in werken}
eind_pad = {}  # (merk, rel) -> nieuw pad (voor samenvoeg-doelen)


def doel_naam(w):
    basis = NAAM_OVERRIDE.get(w["rel"], w["mapnaam"]).lstrip("_")
    j = "" if naming.splits(basis)[0] else jaren.get(w["pid"], "")
    return naming.voorstel(basis, j)


# 1. hoofdwerken en bak-werken een eindnaam geven
for w in werken:
    if w["los"] or (w["rel"] in SAMENVOEGEN):
        continue
    root = roots[w["merk"]]
    nieuw_naam = doel_naam(w)
    if in_bak(w["rel"]):
        nieuw_pad = os.path.join(root, "Done", nieuw_naam)
        soort = "verplaats"
    else:
        nieuw_pad = os.path.join(os.path.dirname(w["pad"]), nieuw_naam)
        soort = "hernoem" if nieuw_pad != w["pad"] else "yml"
    eind_pad[(w["merk"], w["rel"])] = nieuw_pad
    acties.append({"soort": soort, "merk": w["merk"], "van": w["pad"], "naar": nieuw_pad,
                   "pid": w["pid"], "naam": naming.splits(nieuw_naam)[1],
                   "jaar": naming.splits(nieuw_naam)[0], "status": "todo" if "ToDo" in w["rel"] else "done",
                   "had_yml": bool(w["yml"])})

# 2. dubbele als submap in het hoofdwerk
for rel, (doel_rel, sub) in SAMENVOEGEN.items():
    w = per_rel.get(("SJB", rel))
    if not w:
        fouten.append(f"niet gevonden: {rel}")
        continue
    doel = eind_pad.get(("SJB", doel_rel))
    if not doel:
        fouten.append(f"doel niet gevonden: {doel_rel}")
        continue
    acties.append({"soort": "samenvoegen", "merk": "SJB", "van": w["pad"], "naar": os.path.join(doel, sub),
                   "pid": w["pid"]})

# 3. losse bestanden uit de bakken naar Done/_Los
for w in werken:
    if w["los"] and w["merk"] == "SJB" and in_bak(w["rel"] + "/x") and w["rel"] != "Done/_Los":
        los_dir = os.path.join(roots["SJB"], "Done", "_Los")
        for m in w["media"]:
            acties.append({"soort": "los", "merk": "SJB", "van": m["pad"], "naar": os.path.join(los_dir, m["naam"])})

# botsingen
doelen = {}
for a in acties:
    if a["soort"] == "yml":
        continue
    k = os.path.normcase(a["naar"])
    if k in doelen:
        if a["soort"] == "los":
            stam, ext = os.path.splitext(a["naar"])
            a["naar"] = f"{stam} (2){ext}"
        else:
            fouten.append(f"twee keer hetzelfde doel: {a['naar']}")
    elif os.path.exists(a["naar"]) and os.path.normcase(a["naar"]) != os.path.normcase(a["van"]):
        if a["soort"] == "los":
            stam, ext = os.path.splitext(a["naar"])
            a["naar"] = f"{stam} (uit bak){ext}"
        else:
            fouten.append(f"bestaat al: {a['naar']}")
    doelen[os.path.normcase(a["naar"])] = a

kort = lambda p: p.split("_To Promote")[-1]
for s in ("hernoem", "verplaats", "samenvoegen"):
    rij = [a for a in acties if a["soort"] == s]
    print(f"\n=== {s.upper()} ({len(rij)})")
    for a in rij:
        print(f"  {a['merk']:8} {kort(a['van'])}  ->  {kort(a['naar'])}")
print(f"\n=== LOSSE BESTANDEN naar Done/_Los: {sum(1 for a in acties if a['soort']=='los')}")
print(f"=== alleen yml bijwerken: {sum(1 for a in acties if a['soort']=='yml')}")
print("=== FOUTEN:", fouten or "geen")

if not DOE:
    print("\nProefrun: er is niets veranderd. Uitvoeren met --doe")
    sys.exit(0)
if fouten:
    print("Gestopt vanwege fouten.")
    sys.exit(1)

# ---------- uitvoeren ----------
import shutil  # noqa: E402

shutil.copy(config.LINKS_PATH, config.LINKS_PATH.replace(".json", ".backup-herstructureer.json"))
log = []
# volgorde: eerst hoofdwerken hernoemen/verplaatsen, dan samenvoegen (doelen bestaan dan), dan losse bestanden
for soort in ("hernoem", "verplaats", "samenvoegen", "los"):
    for a in [a for a in acties if a["soort"] == soort]:
        try:
            os.makedirs(os.path.dirname(a["naar"]), exist_ok=True)
            if os.path.normcase(a["van"]) == os.path.normcase(a["naar"]) and a["van"] != a["naar"]:
                tmp = a["van"] + "__tmp"
                os.rename(a["van"], tmp)
                os.rename(tmp, a["naar"])
            else:
                os.rename(a["van"], a["naar"])
            log.append({**a, "ok": True})
        except OSError as e:
            log.append({**a, "ok": False, "fout": str(e)})
            print("FOUT", kort(a["van"]), e)

# yml bijwerken / aanmaken voor alle werken met een eindnaam
for a in acties:
    if a["soort"] not in ("hernoem", "verplaats", "yml"):
        continue
    pad = a["naar"] if os.path.isdir(a["naar"]) else a["van"]
    yml = os.path.join(pad, "_project.yml")
    if os.path.exists(yml):
        local.zet_yml(pad, "naam", a["naam"])
        oud = local.lees_yml(yml).get("jaar", "")
        if a["jaar"] and (not oud or "aanname" in oud or oud.strip() == "div."):
            local.zet_yml(pad, "jaar", a["jaar"])
    else:
        with open(yml, "w", encoding="utf-8") as f:
            f.write(YML_SJABLOON.format(naam=a["naam"], jaar=a["jaar"], status=a["status"],
                                        notitie="uit verzamelbak (herstructurering 03-10-2026)"
                                        if a["soort"] == "verplaats" else ""))

# koppelingen meeverhuizen
nieuw_pid = {a["pid"]: local.pid_voor(a["naar"]) for a in acties if a["soort"] in ("hernoem", "verplaats")}
pad_van = {a["pid"]: a["naar"] for a in acties if a["soort"] in ("hernoem", "verplaats")}
n = 0
for v in links.values():
    if v["pid"] in nieuw_pid:
        v["pid"], v["pad"] = nieuw_pid[v["pid"]], pad_van[v["pid"]]
        n += 1
config.save_json(config.LINKS_PATH, links)
config.save_json(os.path.join(config.DATA_DIR, "herstructureer-log.json"), log)
print(f"\nKlaar. {sum(1 for x in log if x['ok'])} verplaatst/hernoemd, {sum(1 for x in log if not x['ok'])} fouten, "
      f"{n} koppelingen bijgewerkt. Log: data/herstructureer-log.json")
