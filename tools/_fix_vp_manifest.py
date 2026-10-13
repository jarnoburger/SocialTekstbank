"""Herstel: manifest-items 'vp_<pid>' (door uitvoer_verplaats aangemaakt) samenvoegen met het bestaande
item van hetzelfde werk in een andere batch. Beeldbestanden worden gekopieerd. Proefrun; --doe schrijft."""
import sys, os, json, shutil, glob, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
DOE = "--doe" in sys.argv
BD = os.path.join(config.DATA_DIR, "beelden")
MAN = {p: config.load_json(p, []) for p in sorted(glob.glob(os.path.join(BD, "*", "manifest.json")))}
if DOE:
    for p in MAN:
        shutil.copy2(p, p.replace(".json", f".backup-{time.strftime('%Y%m%d-%H%M%S')}.json"))
for p, lijst in MAN.items():
    for vp in [x for x in lijst if str(x.get("map", "")).startswith("vp_")]:
        doel = None
        for q, l2 in MAN.items():
            for y in l2:
                if y is not vp and y.get("pid") == vp["pid"] and not str(y.get("map", "")).startswith("vp_") \
                        and not y.get("samengevoegd_in"):
                    doel = (q, y)
        if not doel:
            print("geen bestaand item, laat staan:", vp["mapnaam"]); continue
        q, y = doel
        for b in vp["beelden"]:
            src = os.path.join(os.path.dirname(p), vp["map"], b["bestand"])
            dst = os.path.join(os.path.dirname(q), y["map"], b["bestand"])
            stam, ext = os.path.splitext(dst); i = 2
            while os.path.exists(dst):
                dst = f"{stam}_{i}{ext}"; i += 1
            nb = dict(b, bestand=os.path.basename(dst))
            if DOE:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst); y["beelden"].append(nb)
        print(f"{vp['mapnaam']}: {len(vp['beelden'])} beeld(en) {os.path.basename(os.path.dirname(p))}/{vp['map']} -> "
              f"{os.path.basename(os.path.dirname(q))}/{y['map']}")
        if DOE:
            lijst.remove(vp)
if DOE:
    for p, lijst in MAN.items():
        config.save_json(p, lijst)
print("DOE" if DOE else "PROEFRUN")
