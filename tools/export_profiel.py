# Alleen lezen: verzamelt per werk jaar, merk, Kort, Credits, opdrachtgever en Pers -> data\profiel_bron.json
import os, re, json, sys
ROOTS = {"SJB": r"C:\Users\jarno\OneDrive\_Studio JarnoBurger\_To Promote",
         "Lichtjes": r"C:\Users\jarno\OneDrive\_Lichtjes Dome\_To Promote"}
def secties(txt):
    out, cur = {}, None
    for line in txt.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m: cur = m.group(1).strip(); out[cur] = []; continue
        if cur: out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}
def yml(p):
    d = {}
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            m = re.match(r"^(\w+):\s*(.*)$", line)
            if m: d[m.group(1)] = m.group(2).strip().strip('"')
    return d
res = []
for merk, root in ROOTS.items():
    for naam in sorted(os.listdir(root)):
        p = os.path.join(root, naam)
        t = os.path.join(p, "_tekst.md")
        if not os.path.isdir(p) or not os.path.exists(t): continue
        s = secties(open(t, encoding="utf-8", errors="replace").read())
        y = yml(os.path.join(p, "_project.yml"))
        res.append({"merk": merk, "werk": naam, "jaar": y.get("jaar", ""),
                    "opdrachtgever": y.get("opdrachtgever", ""),
                    "trefwoorden": y.get("trefwoorden", ""),
                    "kort": s.get("Kort", "")[:300], "beeld": s.get("Beeldbeschrijving", "").split("\n\n")[0][:420], "jaarplek": s.get("Jaar en plek", "")[:200],
                    "credits": s.get("Credits", "")[:300], "pers": s.get("Pers", "")})
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "profiel_bron.json")
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(res), "werken;", sum(1 for r in res if r["pers"]), "met pers ->", out)

