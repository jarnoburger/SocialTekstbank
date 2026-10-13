import os, sys, re
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import app as A
with A.app.test_request_context():
    rijen = A._publiceer_rijen()
gezien = set()
ig = {r["w"]["pid"]: r["tekst"] for r in rijen if r["p"]["platform"] == "ig"}
for r in rijen:
    if r["p"]["platform"] != "fb" or r["w"]["pid"] in gezien:
        continue
    v = (r["w"]["tekst"] or {}).get("velden", {})
    hs = re.findall(r"@[\w.]+", v.get("Caption NL", ""))
    if hs:
        gezien.add(r["w"]["pid"])
        for h in hs:
            i = v["Caption NL"].find(h)
            ctx = v["Caption NL"][max(0, i - 25): i + len(h) + 5]
            j = r["tekst"].find(ctx[:20])
            print(f'{r["w"]["mapnaam"][:30]:30} {h:28} -> {r["tekst"][j:j+len(ctx)+15]!r}')
