"""Eenmalig (Jarno 04-10-2026): Max Mahieu uit Credits (Lilian) en Crosslinks-notitie (Lowlands) halen."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import textfile
B = r"C:\Users\jarno\OneDrive\_Studio JarnoBurger\_To Promote"
EDITS = [
    ("2024 Lilian Kreutzberger", "Credits", "naast Max Mahieu, Nils van Lingen", "naast Nils van Lingen"),
    ("1998-2008 Lowlands", "Crosslinks", "Jarno Burger en Max Mahieu genoemd als technische ondersteuning",
     "Jarno Burger genoemd als technische ondersteuning"),
]
for m, veld, oud, nieuw in EDITS:
    p = os.path.join(B, m)
    d = textfile.lees(p)
    t = d["velden"].get(veld, "")
    if t.count(oud) != 1:
        print("NIET GEVONDEN:", m, veld); continue
    d["velden"][veld] = t.replace(oud, nieuw)
    textfile.schrijf(p, d)
    print("ok:", m, veld)
