"""Verhuist de '- bron: alt'-regels in de Beeldbeschrijving mee met uitgevoerde verplaatsingen
(data/verplaats_uitgevoerd.json), zodat de volgorde in Review weer klopt. Proefrun standaard; --doe schrijft.
Een regel wordt alleen verhuisd als hij nog bij het bronwerk staat (idempotent)."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config, textfile

DOE = "--doe" in sys.argv
U = config.load_json(os.path.join(config.DATA_DIR, "verplaats_uitgevoerd.json"), {})
per_pid = {w["pid"]: w for w in A.werken() if not w["los"]}
per_key = {p["key"]: p for p in A.online()["posts"]}


def kenmerk(iid):
    if iid.startswith("post:"):
        p = per_key.get(iid[5:]) or {}
        pl = p.get("permalink") or ""
        m = re.search(r"/(?:p|reel|tv)/([^/?]+)", pl) or re.search(r"posts/(\d+)", pl) or re.search(r"videos/(\d+)", pl)
        return m.group(1) if m else None
    return "lokaal " + iid.split(":", 2)[2]


def bb(w):
    d = textfile.lees(w["pad"]) or textfile.leeg()
    return d, d["velden"].get("Beeldbeschrijving", "")


for iid, r in sorted(U.items(), key=lambda x: x[1].get("uitgevoerd", "")):
    van, naar = per_pid.get(r["van"]), per_pid.get(r["naar"])
    k = kenmerk(iid)
    if not (van and naar and k):
        print("overgeslagen:", iid); continue
    dv, tv = bb(van)
    regels = [l for l in tv.splitlines() if l.lstrip().startswith("- ") and k in l]
    if not regels:
        continue
    dn, tn = bb(naar)
    nieuw_v = "\n".join(l for l in tv.splitlines() if l not in regels)
    ln = tn.splitlines()
    idx = max((i for i, l in enumerate(ln) if l.lstrip().startswith("- ")), default=None)
    toe = [f"{l}  _(uit {van['mapnaam']})_" for l in regels]
    if idx is None:
        ln += ["", "Beelden:"] + toe
    else:
        ln[idx + 1:idx + 1] = toe
    print(f"{van['mapnaam']} -> {naar['mapnaam']}: {len(regels)} regel(s)")
    if DOE:
        dv["velden"]["Beeldbeschrijving"] = nieuw_v
        textfile.schrijf(van["pad"], dv)
        dn, _ = bb(naar)
        dn["velden"]["Beeldbeschrijving"] = "\n".join(ln)
        textfile.schrijf(naar["pad"], dn)
print("DOE" if DOE else "PROEFRUN")
