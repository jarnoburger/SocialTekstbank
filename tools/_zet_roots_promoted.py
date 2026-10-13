"""Voegt de _Promoted-mappen toe aan roots in data/config.json (tokens blijven ongemoeid, niets wordt geprint behalve roots)."""
import json, os, shutil
P = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")
shutil.copy(P, P + ".voor-promoted.bak")
c = json.load(open(P, encoding="utf-8"))
nieuw = [{"merk": "SJB", "pad": r"C:\Users\jarno\OneDrive\_Studio JarnoBurger\_Promoted"},
         {"merk": "Lichtjes", "pad": r"C:\Users\jarno\OneDrive\_Lichtjes Dome\_Promoted"}]
bestaand = {os.path.normcase(r["pad"]) for r in c.get("roots", [])}
for r in nieuw:
    if os.path.normcase(r["pad"]) not in bestaand:
        c.setdefault("roots", []).append(r)
json.dump(c, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(c["roots"])
