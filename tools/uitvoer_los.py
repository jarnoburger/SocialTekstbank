"""Voert de besluiten uit het scherm /los uit (data/los_besluit.json). Niets wordt gewist.

  werk   -> bestand naar de werkmap (bij naambotsing: _los1, _los2 ...)
  nieuw  -> nieuwe werkmap in <merk>\\_To Promote\\<naam> en bestand erin
  dubbel -> <_Los>\\_to_delete\\dubbel\\
  weg    -> <_Los>\\_to_delete\\niet-nodig\\
  later  -> blijft staan

python tools/uitvoer_los.py        -> proefrun
python tools/uitvoer_los.py --doe  -> uitvoeren
"""
import os, sys, time, collections, datetime as dt
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config  # noqa: E402

DOE = "--doe" in sys.argv
bes = config.load_json(A.LOS_BESLUIT_PATH, {})
ROOTS = {"SJB": r"C:\Users\jarno\OneDrive\_Studio JarnoBurger\_To Promote",
         "Lichtjes": r"C:\Users\jarno\OneDrive\_Lichtjes Dome\_To Promote"}


def vrij(pad):
    if not os.path.exists(pad):
        return pad
    stam, ext = os.path.splitext(pad)
    n = 1
    while os.path.exists(f"{stam}_los{n}{ext}"):
        n += 1
    return f"{stam}_los{n}{ext}"


with A.app.test_request_context():
    wm = A.werk_map()
    plan, tel, fouten = [], collections.Counter(), []
    for sleutel, b in bes.items():
        los_pid, rel = sleutel.split("|", 1)
        lw = wm.get(los_pid)
        if not lw:
            fouten.append(f"los-map onbekend: {sleutel}"); continue
        bron = os.path.join(lw["pad"], rel)
        if not os.path.exists(bron):
            fouten.append(f"bestaat niet (al verplaatst?): {bron}"); continue
        a = b["actie"]
        if a == "nieuw" and "--zonder-nieuw" in sys.argv:
            tel["nieuw (wacht)"] += 1; continue
        if a == "later":
            tel["later (blijft)"] += 1; continue
        if a == "werk":
            w = wm.get(b["pid"])
            if not w:
                fouten.append(f"werk onbekend voor {rel}"); continue
            doel = os.path.join(w["pad"], os.path.basename(rel)); wat = w["mapnaam"]
        elif a == "nieuw":
            if not b.get("naam"):
                fouten.append(f"geen naam voor nieuw werk: {rel}"); continue
            doel = os.path.join(ROOTS[b["merk"]], b["naam"], os.path.basename(rel)); wat = "NIEUW " + b["naam"]
        elif a in ("dubbel", "weg"):
            sub = "dubbel" if a == "dubbel" else "niet-nodig"
            doel = os.path.join(lw["pad"], "_to_delete", sub, os.path.basename(rel)); wat = "_to_delete/" + sub
        else:
            continue
        plan.append((bron, doel, a, wat))
        tel[a] += 1
    per_doel = collections.Counter(w for *_, w in plan)
    for w, n in sorted(per_doel.items()):
        print(f"{n:4}  -> {w}")
    print("\nTotaal:", dict(tel), "| fouten:", fouten or "geen")
    if not DOE:
        print("Proefrun. Uitvoeren met --doe"); sys.exit(0)
    log = []
    for bron, doel, a, wat in plan:
        doel = vrij(doel)
        os.makedirs(os.path.dirname(doel), exist_ok=True)
        for poging in range(3):
            try:
                os.rename(bron, doel); log.append({"van": bron, "naar": doel, "actie": a, "ok": True}); break
            except OSError as e:
                if poging == 2:
                    log.append({"van": bron, "naar": doel, "actie": a, "ok": False, "fout": str(e)})
                time.sleep(3)
    stempel = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    config.save_json(os.path.join(config.DATA_DIR, f"los-uitvoer-log-{stempel}.json"), log)
    # nieuw materiaal per werkmap bijhouden (voor 'Nieuwe post'): {werkmap-pad: [bestandsnaam, ...]}
    NM = os.path.join(config.DATA_DIR, "nieuw_materiaal.json")
    nm = config.load_json(NM, {})
    for x in log:
        if x["ok"] and x["actie"] in ("werk", "nieuw"):
            lijst = nm.setdefault(os.path.dirname(x["naar"]), [])
            if os.path.basename(x["naar"]) not in lijst:
                lijst.append(os.path.basename(x["naar"]))
    config.save_json(NM, nm)
    print(f"Klaar: {sum(1 for x in log if x['ok'])} ok, {sum(1 for x in log if not x['ok'])} fouten. Daarna: herscan + match_los.py")
