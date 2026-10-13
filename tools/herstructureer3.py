"""Herstructurering 3 (04-10-2026 avond): samenvoegen volgens /dubbel-besluiten. Gebaseerd op herstructureer2.py.

python tools/herstructureer3.py         -> proefrun
python tools/herstructureer3.py --doe   -> uitvoeren

Samenvoegen = bronmap wordt submap van de doelmap. Teksten van de bron gaan naar de _tekst.md van het doel
(velden die leeg zijn worden gevuld, eerdere captions toegevoegd, de Beeldbeschrijving wordt aangevuld);
de oude _tekst.md/_project.yml/_social.json in de submap krijgen de naam *.samengevoegd.* (niets wordt verwijderd).
"""
import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config, local, textfile  # noqa: E402

DOE = "--doe" in sys.argv
VANDAAG = dt.date.today().strftime("%d-%m-%Y")
URBANFX = "Opdrachtgever: Urban-FX (Milaan)."

ROOTS = {r["merk"]: r["pad"] for r in config.load_config()["roots"]}

# Uit data/dubbel_besluit.json (Jarno, /dubbel, 04-10-2026): alleen besluit 'samen'.
def _stappen_uit_besluit():
    bes = config.load_json(os.path.join(config.DATA_DIR, "dubbel_besluit.json"), {})
    kand = {g["id"]: g for g in config.load_json(os.path.join(config.DATA_DIR, "dubbel_kandidaten.json"), [])}
    per_pid = {w["pid"]: w for w in A.werken() if not w["los"]}
    uit = []
    for gid, b in sorted(bes.items()):
        if b.get("besluit") != "samen" or gid not in kand:
            continue
        doel = per_pid.get(b["doel"])
        if not doel:
            print(f"{gid}: doel niet gevonden ({b['doel']})")
            continue
        for pid in kand[gid]["pids"]:
            if pid == doel["pid"] or pid not in per_pid:
                continue
            bron = per_pid[pid]
            uit.append(("voegsamen", {"merk": bron["merk"], "map": bron["mapnaam"], "doel_merk": doel["merk"],
                                      "doel": doel["mapnaam"], "submap": f"Uit {bron['mapnaam']}"}))
    return uit


STAPPEN = _stappen_uit_besluit()


def zoek(merk, naam):
    for w in A.werken(herscan=True):
        if w["merk"] == merk and w["mapnaam"] == naam and not w["los"]:
            return w
    return None


def rename(van, naar):
    if os.path.exists(naar):
        raise ValueError(f"bestaat al: {naar}")
    for poging in range(3):
        try:
            os.rename(van, naar)
            return
        except OSError:
            if poging == 2:
                raise
            time.sleep(15)  # OneDrive-lock


MANIFESTS = {}


def manifests():
    if not MANIFESTS:
        d = os.path.join(config.DATA_DIR, "beelden")
        for b in os.listdir(d):
            p = os.path.join(d, b, "manifest.json")
            if os.path.exists(p):
                MANIFESTS[p] = config.load_json(p, [])
    return MANIFESTS


def migreer(oud_pid, nieuw_pid, nieuw_pad, mapnaam=None, samengevoegd=False):
    lk = A.links()
    for v in lk.values():
        if v["pid"] == oud_pid:
            v["pid"], v["pad"] = nieuw_pid, nieuw_pad
    config.save_json(config.LINKS_PATH, lk)
    for lijst in manifests().values():
        for x in lijst:
            if x.get("pid") == oud_pid:
                x["pid"] = nieuw_pid
                if samengevoegd:
                    x["samengevoegd_in"] = nieuw_pid
                elif mapnaam:
                    x["mapnaam"] = mapnaam


def voeg_tekst_samen(doel_pad, bron_pad, bron_naam):
    d = textfile.lees(doel_pad) or textfile.leeg()
    b = textfile.lees(bron_pad)
    if not b:
        return
    for veld, tekst in b["velden"].items():
        if not tekst.strip():
            continue
        if veld == "Beeldbeschrijving":
            d["velden"][veld] = (d["velden"].get(veld, "").rstrip() + f"\n\nUit {bron_naam}:\n" + tekst).strip()
        elif not d["velden"].get(veld, "").strip():
            d["velden"][veld] = tekst
        elif textfile.norm(tekst) not in textfile.norm(d["velden"][veld]):
            d["velden"][veld] = d["velden"][veld].rstrip() + f"\n\n[{bron_naam}] {tekst}"
    gezien = {textfile.norm(e["tekst"]) for e in d["eerder"]}
    d["eerder"] += [e for e in b["eerder"] if textfile.norm(e["tekst"]) not in gezien]
    for k, v in b["per_bestand"].items():
        d["per_bestand"].setdefault(f"{os.path.basename(bron_pad)}/{k}", v)
    textfile.schrijf(doel_pad, d)


def stap(soort, a):
    if soort == "hernoem":
        w = zoek(a["merk"], a["map"])
        if not w:
            return f"niet gevonden: {a['map']}"
        if DOE:
            nieuw_pid = A.hernoem_werk(w, a["nieuw"])
            migreer(w["pid"], nieuw_pid, os.path.join(os.path.dirname(w["pad"]), a["nieuw"]), mapnaam=a["nieuw"])
        return f"hernoem [{a['merk']}] {a['map']} -> {a['nieuw']}"

    if soort == "verplaats":
        w = zoek(a["merk"], a["map"])
        if not w:
            return f"niet gevonden: {a['map']}"
        naar = os.path.join(ROOTS[a["naar_merk"]], a["map"])
        if DOE:
            rename(w["pad"], naar)
            migreer(w["pid"], local.pid_voor(naar), naar, mapnaam=a["map"])
        return f"verplaats {a['map']}: {a['merk']} -> {a['naar_merk']}"

    if soort == "splits":
        w = zoek(a["merk"], a["map"])
        if not w:
            return f"niet gevonden: {a['map']}"
        van = os.path.join(w["pad"], a["submap"])
        naar = os.path.join(ROOTS[a["merk"]], a["nieuw"])
        if not os.path.isdir(van):
            return f"submap ontbreekt: {van}"
        if DOE:
            rename(van, naar)
            local.zet_yml(naar, "notitie", f"Afgesplitst uit '{a['map']}' ({VANDAAG})")
        return f"splits {a['map']}\\{a['submap']} -> eigen werk '{a['nieuw']}'"

    if soort == "voegsamen":
        bron = zoek(a["merk"], a["map"])
        if not bron:
            return f"niet gevonden: {a['map']}"
        doel_pad = os.path.join(ROOTS[a["doel_merk"]], a["doel"])
        if DOE:
            doel = zoek(a["doel_merk"], a["doel"])
            if not doel:
                return f"doel niet gevonden: {a['doel']}"
            sub = os.path.join(doel_pad, a["submap"])
            rename(bron["pad"], sub)
            voeg_tekst_samen(doel_pad, sub, a["map"])
            for f in ("_tekst.md", "_project.yml", "_social.json"):
                p = os.path.join(sub, f)
                if os.path.exists(p):
                    stam, ext = os.path.splitext(f)
                    os.rename(p, os.path.join(sub, f"{stam}.samengevoegd{ext}"))
            migreer(bron["pid"], doel["pid"], doel_pad, samengevoegd=True)
            local.zet_yml(doel_pad, "notitie", (doel["yml"].get("notitie", "") +
                          f" | samengevoegd met '{a['map']}' ({a['merk']}, {VANDAAG})").strip(" |"))
        return f"voeg samen [{a['merk']}] {a['map']} -> [{a['doel_merk']}] {a['doel']}\\{a['submap']}"

    if soort == "credits":
        uit = []
        for naam in a["mappen"]:
            w = zoek(a["merk"], naam)
            if not w:
                uit.append(f"niet gevonden: {naam}")
                continue
            if DOE:
                d = w["tekst"] or textfile.leeg()
                c = d["velden"].get("Credits", "")
                if "urban-fx" not in c.lower():
                    d["velden"]["Credits"] = (a["regel"] + "\n" + c).strip()
                    textfile.schrijf(w["pad"], d)
                local.zet_yml(w["pad"], "opdrachtgever", "Urban-FX (Milaan)")
            uit.append(f"credits {naam}: {a['regel']}")
        return "\n".join(uit)


if DOE:
    import shutil
    shutil.copy2(config.LINKS_PATH, config.LINKS_PATH.replace(".json", f".backup-dubbel-{time.strftime('%Y%m%d-%H%M%S')}.json"))
for soort, args in STAPPEN:
    try:
        print(stap(soort, args))
    except Exception as e:  # stop bij de eerste fout; eerdere stappen zijn al gedaan
        print("FOUT bij", soort, args, "->", e)
        break
if DOE:
    for p, lijst in manifests().items():
        config.save_json(p, lijst)
    betrokken = {a["doel"] for _, a in STAPPEN}
    for w in A.werken(herscan=True):
        if w["mapnaam"] in betrokken:
            A.schrijf_social_json(w)
    print("Klaar.")
else:
    print("Proefrun. Uitvoeren met --doe")
