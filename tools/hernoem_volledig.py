"""Hernoemt werkmappen en neemt pid + pad mee in ALLE data-bestanden (ook nieuw_materiaal/nieuw_besluit/concepten).

python tools/hernoem_volledig.py            -> proefrun
python tools/hernoem_volledig.py --doe      -> uitvoeren
"""
import glob, json, os, sys, time, datetime as dt
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config, local  # noqa: E402

LIJST = [("SJB", "2008 Videotechniek", "Videotechniek"),
         ("SJB", "2026 Madja", "2026 Majda Vidakovic")]
DOE = "--doe" in sys.argv
D = config.DATA_DIR
EXTRA = ["nieuw_materiaal.json", "nieuw_besluit.json", "nieuw_concepten.json", "los_besluit.json",
         "los_besluit_uitgevoerd.json", "los_match.json", "promoted-auto-log.json"]

with A.app.test_request_context():
    ws = A.werken(herscan=True)
    for merk, oud, nieuw in LIJST:
        w = next((x for x in ws if not x["los"] and x["merk"] == merk and x["mapnaam"] == oud), None)
        if not w:
            print("niet gevonden:", oud); continue
        doel = os.path.join(os.path.dirname(w["pad"]), nieuw)
        print(f"{oud}  ->  {nieuw}   ({w['pad']})", "BESTAAT AL" if os.path.exists(doel) else "")
        if not DOE or os.path.exists(doel):
            continue
        for poging in range(3):
            try:
                os.rename(w["pad"], doel); break
            except OSError:
                if poging == 2:
                    raise
                time.sleep(5)
        oud_pid, nieuw_pid = w["pid"], local.pid_voor(doel)
        lk = A.links()
        for v in lk.values():
            if v.get("pid") == oud_pid:
                v["pid"], v["pad"] = nieuw_pid, doel
        config.save_json(config.LINKS_PATH, lk)
        bestanden = [os.path.join(D, f) for f in A.PID_BESTANDEN + EXTRA if f != "links.json"]
        bestanden += glob.glob(os.path.join(D, "beelden", "*", "manifest.json"))
        sleutel_oud, sleutel_nieuw = f"{merk}|{oud}", f"{merk}|{nieuw}"
        for f in bestanden:
            if not os.path.exists(f):
                continue
            t = open(f, encoding="utf-8").read()
            t2 = (t.replace(oud_pid, nieuw_pid).replace(json.dumps(w["pad"])[1:-1], json.dumps(doel)[1:-1])
                  .replace(json.dumps(sleutel_oud)[1:-1], json.dumps(sleutel_nieuw)[1:-1])
                  .replace(f'"werk": "{oud}"', f'"werk": "{nieuw}"'))
            if t2 != t:
                json.loads(t2)
                open(f, "w", encoding="utf-8").write(t2)
                print("   bijgewerkt:", os.path.basename(f))
        log = config.load_json(os.path.join(D, "hernoem-volledig-log.json"), [])
        log.append({"op": dt.datetime.now().isoformat(timespec="seconds"), "van": w["pad"], "naar": doel,
                    "pid_oud": oud_pid, "pid_nieuw": nieuw_pid})
        config.save_json(os.path.join(D, "hernoem-volledig-log.json"), log)
        print("   ok, pid", oud_pid, "->", nieuw_pid)
if not DOE:
    print("Proefrun. Uitvoeren met --doe")
