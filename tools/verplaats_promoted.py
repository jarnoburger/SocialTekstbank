"""Verplaatst werken die op BEIDE eigen plekken gepost zijn (SJB: Insta+FB SJB, Lichtjes: Insta+FB Lichtjes)
van <merk>\\_To Promote naar <merk>\\_Promoted. pids veranderen mee in alle live data-bestanden.

python tools/verplaats_promoted.py         -> proefrun
python tools/verplaats_promoted.py --doe   -> uitvoeren (eerst backup data-zip)
"""
import glob, json, os, sys, time, zipfile, datetime as dt
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config, local  # noqa: E402

DOE = "--doe" in sys.argv
NIET_POSTEN = "--ook-niet-posten" in sys.argv  # ook werken die in Plannen op 'verder niet posten' + klaar staan
D = config.DATA_DIR
PLAN = config.load_json(os.path.join(D, "plan.json"), {})
LIVE = ["links.json", "plan.json", "planning.json", "publiceer.json", "beelden_batch1.json", "beelden_batch2.json",
        "context_alle.json", "online_research.json", "verplaats.json", "dubbel_besluit.json", "dubbel_kandidaten.json",
        "hashes.json", "personen_fb.json"]
LIVE = [os.path.join(D, f) for f in LIVE] + glob.glob(os.path.join(D, "beelden", "*", "manifest.json"))

with A.app.test_request_context():
    ws = A.werken(herscan=True)
    per_key = {p["key"]: p for p in A.online()["posts"]}
    lpw = A.links_per_werk()
    lijst = []
    for w in sorted(ws, key=lambda w: (w["merk"], w["jaar"] or "9999", w["mapnaam"].lower())):
        if w["los"] or os.sep + "_To Promote" + os.sep not in w["pad"]:
            continue
        g = A._gepost_per_doel(w["pid"], per_key, lpw)
        it = PLAN.get(w["pid"], {})
        klaar_niet = NIET_POSTEN and it.get("klaar") and it.get("niet")
        if klaar_niet or all(g[d] for d, *_ in A._eigen_doelen(w)):
            bron = w["pad"]
            # doel: zelfde relatieve plek onder _Promoted
            doel = bron.replace(os.sep + "_To Promote" + os.sep, os.sep + "_Promoted" + os.sep, 1)
            lijst.append((w, bron, doel))

fout = [(w["mapnaam"], d) for w, b, d in lijst if os.path.exists(d)]
for w, b, d in lijst:
    print(f'{w["merk"]:8} {w["mapnaam"]}')
print(f"\n{len(lijst)} werken -> _Promoted.  Bestaat al: {fout or 'geen'}")
if not DOE:
    print("Proefrun. Uitvoeren met --doe")
    sys.exit(0)

stempel = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
with zipfile.ZipFile(os.path.join(D, f"data-backup-voor-promoted-{stempel}.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    for f in LIVE:
        if os.path.exists(f):
            z.write(f, os.path.relpath(f, D))
log, vervang, pad_vervang = [], {}, {}
for w, bron, doel in lijst:
    if os.path.exists(doel):
        log.append({"map": w["mapnaam"], "ok": False, "fout": "doel bestaat al"}); continue
    os.makedirs(os.path.dirname(doel), exist_ok=True)
    for poging in range(4):
        try:
            os.rename(bron, doel)
            break
        except OSError as e:
            if poging == 3:
                log.append({"map": w["mapnaam"], "ok": False, "fout": str(e)}); doel = None
            else:
                time.sleep(10)
    if not doel:
        print("FOUT", w["mapnaam"]); continue
    nieuw_pid = local.pid_voor(doel)
    vervang[w["pid"]] = nieuw_pid
    pad_vervang[bron] = doel
    log.append({"map": w["mapnaam"], "ok": True, "van": bron, "naar": doel, "pid_oud": w["pid"], "pid_nieuw": nieuw_pid})
    print("ok:", w["mapnaam"])

# links.json: pid + pad
lk = config.load_json(config.LINKS_PATH, {})
for v in lk.values():
    if v.get("pid") in vervang:
        v["pid"] = vervang[v["pid"]]
        v["pad"] = pad_vervang.get(v.get("pad"), v.get("pad"))
config.save_json(config.LINKS_PATH, lk)
# overige live bestanden: tekstueel pid -> nieuw pid (pids zijn 10 hex-tekens, uniek), en paden
for f in LIVE:
    if not os.path.exists(f) or os.path.abspath(f) == os.path.abspath(config.LINKS_PATH):
        continue
    t = open(f, encoding="utf-8").read()
    t2 = t
    for o, n in vervang.items():
        t2 = t2.replace(o, n)
    for o, n in pad_vervang.items():
        t2 = t2.replace(json.dumps(o)[1:-1], json.dumps(n)[1:-1])
    if t2 != t:
        json.loads(t2)  # moet geldige JSON blijven
        open(f, "w", encoding="utf-8").write(t2)
        print("bijgewerkt:", os.path.basename(f))
config.save_json(os.path.join(D, f"promoted-log-{stempel}.json"), log)
print(f"Klaar: {sum(1 for x in log if x['ok'])} ok, {sum(1 for x in log if not x['ok'])} fouten.")
