"""Zet Claude-voorstellen in data/captions.json (proefrun; --doe om echt te schrijven).

python tools/schrijf_captions.py data/claude_captions_ronde1.json [--doe]

Invoer: [{"gid": "g:ig:123", "nl": "...", "en": "...", "tags": ["@x"], "notitie": "..."}]
- Overschrijft alleen het Claude-deel; 'beste', status en feedback blijven staan.
- Bij een herschrijving (er stond al een voorstel) gaat 'ronde' +1 en wordt de feedback als 'verwerkt' bewaard.
- Backup van captions.json met tijdstempel vóór het schrijven.
"""
import datetime as dt
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import captions as capt, config, group  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
doe = "--doe" in sys.argv
invoer = json.load(open(sys.argv[1], encoding="utf-8"))
groepen = {g["gid"]: g for g in group.maak_groepen(config.load_json(config.ONLINE_PATH, {"posts": []})["posts"])}
per_key = {k: g for g in groepen.values() for k in g["keys"]}

data = capt.laad()
nieuw = herschreven = fout = 0
for x in invoer:
    g = groepen.get(x["gid"]) or per_key.get(x["gid"].removeprefix("g:"))
    if not g:
        print("  ? onbekende gid:", x["gid"])
        fout += 1
        continue
    it = capt.item_voor(data, g)
    it["keys"] = list(g["keys"])
    oud = it.get("claude") or {}
    ronde = (oud.get("ronde") or 0) + 1 if (oud.get("nl") or oud.get("en")) else 1
    if ronde > 1:
        herschreven += 1
        if it.get("feedback"):
            it.setdefault("feedback_historie", []).append({"ronde": ronde - 1, "feedback": it["feedback"]})
            it["feedback"] = ""
    else:
        nieuw += 1
    it["claude"] = {"nl": x.get("nl", "").strip(), "en": x.get("en", "").strip(),
                    "tags": x.get("tags") or capt.tags_uit(x.get("nl", "") + " " + x.get("en", "")),
                    "notitie": x.get("notitie", "").strip(), "datum": dt.date.today().isoformat(), "ronde": ronde}
    it["gewijzigd"] = capt.nu()
    print(f"  {'+' if ronde == 1 else '~'} {g['start'][:10]} {g['soort']:6} {it['claude']['nl'][:70]!r}")

print(f"nieuw {nieuw} · herschreven {herschreven} · onbekend {fout}")
if doe:
    if os.path.exists(capt.CAPTIONS_PATH):
        shutil.copy2(capt.CAPTIONS_PATH, capt.CAPTIONS_PATH.replace(".json", f".backup-{dt.datetime.now():%Y%m%d-%H%M%S}.json"))
    capt.bewaar(data)
    print("geschreven ->", capt.CAPTIONS_PATH)
else:
    print("(proefrun; --doe om te schrijven)")
