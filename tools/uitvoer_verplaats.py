"""Voert data/verplaats.json uit (markeringen uit Review). Proefrun standaard; --doe om uit te voeren.
post:<key>        -> post herkoppelen in links.json (hele post) + beelden in manifest naar het doelwerk
lokaal:<pid>:<rel> -> bestand verplaatsen (os.rename, downloadt niets) + manifest
Nieuw werk -> map aanmaken in de merkmap. Uitgevoerde markeringen gaan naar data/verplaats_uitgevoerd.json."""
import datetime as dt, json, os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config, local  # noqa: E402

DOE = "--doe" in sys.argv
NU = dt.datetime.now().isoformat(timespec="seconds")
ROOTS = {r["merk"]: r["pad"] for r in config.load_config()["roots"]}
VP = os.path.join(config.DATA_DIR, "verplaats.json")
UIT = os.path.join(config.DATA_DIR, "verplaats_uitgevoerd.json")
BD = os.path.join(config.DATA_DIR, "beelden")
V = config.load_json(VP, {})
per_pid = {w["pid"]: w for w in A.werken() if not w["los"]}
links = A.links()
MAN = {}
for b in os.listdir(BD):
    p = os.path.join(BD, b, "manifest.json")
    if os.path.exists(p):
        MAN[p] = config.load_json(p, [])


def rename(van, naar):
    for poging in range(3):
        try:
            os.rename(van, naar); return
        except OSError:
            if poging == 2: raise
            time.sleep(15)


def vrij(pad):
    stam, ext = os.path.splitext(pad); i = 2
    while os.path.exists(pad):
        pad = f"{stam} ({i}){ext}"; i += 1
    return pad


def manifest_verhuis(van_pid, naar_pid, naar_map, merk, past):
    """Verplaatst beelden (past(b) True) van het manifest-item van van_pid naar dat van naar_pid (zelfde batch)."""
    n = 0
    for p, lijst in MAN.items():
        batch = os.path.dirname(p)
        for x in [x for x in lijst if x.get("pid") == van_pid]:
            mee = [b for b in x.get("beelden", []) if past(b)]
            if not mee:
                continue
            # bestaand item van het doelwerk in ELKE batch zoeken (anders verdringt een nieuw item het oude in Review)
            doel, doel_batch = None, batch
            for q, l2 in MAN.items():
                for y in l2:
                    if y.get("pid") == naar_pid and not y.get("samengevoegd_in"):
                        doel, doel_batch = y, os.path.dirname(q)
            if not doel:
                doel = {"pid": naar_pid, "merk": merk, "mapnaam": naar_map, "map": f"vp_{naar_pid}",
                        "notitie": f"aangemaakt door verplaatsen ({NU[:10]})", "beelden": []}
                if DOE: lijst.append(doel)
            for b in mee:
                src = os.path.join(batch, x["map"], b["bestand"])
                nb = dict(b)
                dst = vrij(os.path.join(doel_batch, doel["map"], b["bestand"]))
                nb["bestand"] = os.path.basename(dst)
                if DOE:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if os.path.exists(src): shutil.copy2(src, dst)
                    x["beelden"].remove(b); doel["beelden"].append(nb)
                n += 1
    return n


log, fouten, klaar = [], [], []
for iid, r in sorted(V.items()):
    van = per_pid.get(r["van"])
    if not van:
        fouten.append(f"{iid}: bronwerk bestaat niet meer ({r['van_map']})"); continue
    if r.get("nieuw"):
        naar_pad = os.path.join(ROOTS[r["merk"]], r["naar_map"]); naar_pid = local.pid_voor(naar_pad); naar_map = r["naar_map"]
        if DOE and not os.path.isdir(naar_pad):
            os.makedirs(naar_pad); local.zet_yml(naar_pad, "notitie", f"Nieuw werk via verplaatsen uit '{van['mapnaam']}' ({NU[:10]})")
    else:
        naar = per_pid.get(r["naar"])
        if not naar:
            fouten.append(f"{iid}: doelwerk bestaat niet meer ({r['naar_map']})"); continue
        naar_pad, naar_pid, naar_map = naar["pad"], naar["pid"], naar["mapnaam"]
    if iid.startswith("post:"):
        key = iid[5:]
        if key not in links:
            fouten.append(f"{iid}: post niet in links.json"); continue
        if DOE:
            links[key] = {**links[key], "pid": naar_pid, "pad": naar_pad, "op": NU[:10], "verplaatst_van": van["pid"]}
        nb = manifest_verhuis(van["pid"], naar_pid, naar_map, r["merk"], lambda b, k=key: b.get("post") == k)
        log.append(f"post {key}: {van['mapnaam']} -> {naar_map} ({nb} beeld(en))")
    else:
        rel = iid.split(":", 2)[2]
        src = os.path.join(van["pad"], rel)
        if not os.path.exists(src):
            fouten.append(f"{iid}: bestand niet gevonden: {src}"); continue
        dst = vrij(os.path.join(naar_pad, os.path.basename(rel)))
        if DOE:
            rename(src, dst)
        nb = manifest_verhuis(van["pid"], naar_pid, naar_map, r["merk"], lambda b, rr=rel: (b.get("lokaal") or "") == rr)
        log.append(f"bestand {rel}: {van['mapnaam']} -> {naar_map}\\{os.path.basename(dst)} ({nb} beeld(en) in manifest)")
    klaar.append(iid)

if DOE:
    shutil.copy2(config.LINKS_PATH, config.LINKS_PATH.replace(".json", f".backup-verplaats-{time.strftime('%Y%m%d-%H%M%S')}.json"))
    config.save_json(config.LINKS_PATH, links)
    for p, lijst in MAN.items():
        config.save_json(p, lijst)
    uit = config.load_json(UIT, {})
    for iid in klaar:
        uit[iid] = {**V.pop(iid), "uitgevoerd": NU}
    config.save_json(UIT, uit); config.save_json(VP, V)
    betrokken = {r for iid in klaar for r in (uit[iid]["van"], uit[iid]["naar"])}
    for w in A.werken(herscan=True):
        if w["pid"] in betrokken or w["mapnaam"] in {uit[i]["naar_map"] for i in klaar}:
            A.schrijf_social_json(w)
print("DOE" if DOE else "PROEFRUN", "| uitgevoerd:", len(klaar))
for l in log: print(" ", l)
for f in fouten: print(" -", f)
