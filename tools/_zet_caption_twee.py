"""Zet Caption EN + Hashtags voor Videotechniek en 2026 Majda Vidakovic (n.a.v. Jarno 06-10). Toont eerst de huidige tekst.
python tools/_zet_caption_twee.py [--doe]"""
import os, sys, datetime as dt
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import textfile
NIEUW = {
    # Jarno's eigen teksten; alleen spelling (Majda, losse 't.') gecorrigeerd
    "Videotechniek": (
        "Video tech: software and setups for video walls and live visuals.",
        None),
    "2026 Majda Vidakovic": (
        "Towers made by Majda Vidaković. I am helping her out a lot.",
        None),
}
DOE = "--doe" in sys.argv
with A.app.test_request_context():
    for w in A.werken(herscan=True):
        if w["los"] or w["mapnaam"] not in NIEUW:
            continue
        t = textfile.lees(w["pad"]) or textfile.leeg()
        oud = t["velden"].get("Caption EN", "").strip()
        print(f"== {w['mapnaam']}\nHUIDIG: {oud[:300]!r}\nNIEUW:  {NIEUW[w['mapnaam']][0][:300]!r}")
        if DOE:
            if oud and textfile.norm(oud) != textfile.norm(NIEUW[w["mapnaam"]][0]):
                t["eerder"].append({"kop": f"vorige Caption EN · {dt.date.today().isoformat()}", "tekst": oud})
            t["velden"]["Caption EN"] = NIEUW[w["mapnaam"]][0]
            if NIEUW[w["mapnaam"]][1]:
                t["velden"]["Hashtags"] = NIEUW[w["mapnaam"]][1]
            print("   hashtags:", t["velden"].get("Hashtags", ""))
            textfile.schrijf(w["pad"], t)
            print("   geschreven")
