"""Eenmalige export van fase 2 (rij per kanaal) voor Honey stap 11b.

Gebruikt de logica van de oude app zelf (_planning_lijst, _post_tekst, _post_beelden),
zodat de export precies is wat het Posten-scherm nu toont.

Uitvoer: E:\\Projects\\Honey\\data\\import\\social_export_<datum>.json
Starten:  python tools\\export_voor_honey.py
"""
import datetime as dt
import json
import os
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as stb  # noqa: E402  (de oude app; start geen server bij importeren)
from core import textfile  # noqa: E402

UIT_MAP = r"E:\Projects\Honey\data\import"


def beeld_info(b, src_map):
    """Zet een beeld uit _post_beelden om naar echte bestandspaden (geen url's).
    src_map: {batch/map/bestand: beeld uit de manifesten} -> lokaal + permalink (voor alt-teksten)."""
    info = {"naam": b["naam"], "type": b["type"], "nieuw": b.get("nieuw", False),
            "preview": None, "origineel_rel": None, "alt": b.get("alt", ""),
            "lokaal": "", "permalink": ""}
    url = b["url"]
    if url.startswith("/beeld/"):
        batch, map_, bestand = unquote(url[len("/beeld/"):]).split("/", 2)
        info["preview"] = os.path.join(stb.BEELDEN_DIR, batch, map_, bestand)
        bron = src_map.get(batch + "/" + map_ + "/" + bestand, {})
        info["lokaal"] = bron.get("lokaal") or ""
        info["permalink"] = bron.get("permalink") or ""
    orig = b.get("origineel") or ""
    if orig.startswith("/origineel/"):
        info["origineel_rel"] = unquote(orig.split("/", 3)[3].split("?")[0])
    return info


def main():
    wm = stb.werk_map()                      # scan van de _To Promote/_Promoted-mappen
    plan = stb.config.load_json(stb.PLAN_PATH, {})
    naam_map = stb._naam_map()
    src_map = {b["src"]: b for lijst in stb.beelden_index().values() for b in lijst}
    uit = {"gemaakt": dt.datetime.now().isoformat(timespec="seconds"),
           "fb_namen": naam_map,             # @handle -> naam op FB (uit alle werken + fb_namen.json)
           "kanalen": [], "werken": {}}

    with stb.app.test_request_context():     # url_for werkt alleen binnen een request
        for doel, naam, platform, account in stb.DOELEN:
            volg, gepost = stb._planning_lijst(doel)
            uit["kanalen"].append({"doel": doel, "naam": naam, "platform": platform,
                                   "account": account, "volgorde": volg, "gepost": gepost})
            for pid in volg:
                w = wm[pid]
                if pid not in uit["werken"]:
                    v = (w["tekst"] or textfile.leeg())["velden"]
                    uit["werken"][pid] = {
                        "pad": w["pad"], "mapnaam": w["mapnaam"], "naam": w["naam"],
                        "titel": v.get("Titel", "").strip(), "merk": w["merk"], "jaar": w["jaar"],
                        "doelen": plan.get(pid, {}).get("doelen", []),
                        "gekozen_beelden": plan.get(pid, {}).get("beelden") or [],
                        "beelden": [beeld_info(b, src_map) for b in stb._post_beelden(w)],
                        "tekst_per_doel": {},
                    }
                uit["werken"][pid]["tekst_per_doel"][doel] = stb._post_tekst(w, doel, naam_map)

    os.makedirs(UIT_MAP, exist_ok=True)
    pad = os.path.join(UIT_MAP, "social_export_" + dt.date.today().isoformat() + ".json")
    with open(pad, "w", encoding="utf-8") as f:
        json.dump(uit, f, ensure_ascii=False, indent=2)
    for k in uit["kanalen"]:
        print(f'{k["naam"]:15} {len(k["volgorde"]):3} in rij, {len(k["gepost"]):3} gepost')
    print(len(uit["werken"]), "werken ->", pad)


if __name__ == "__main__":
    main()
