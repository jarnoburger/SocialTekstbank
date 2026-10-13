"""Alleen lezen: stand van plan.json / planning.json t.o.v. werken in _To Promote."""
import os, sys, collections
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
with A.app.test_request_context():
    ws = [w for w in A.werken(herscan=True) if not w["los"]]
    plan = config.load_json(A.PLAN_PATH, {})
    pl = config.load_json(A.PLANNING_PATH, {})
    tp = [w for w in ws if "_To Promote" in w["pad"]]
    tel = collections.Counter()
    for w in tp:
        it = plan.get(w["pid"])
        if not it:
            s = "niet beoordeeld"
        elif not it.get("klaar"):
            s = "opgeslagen, niet klaar"
        elif it.get("niet"):
            s = "klaar: niet posten"
        elif it.get("doelen"):
            s = "klaar: gepland " + "+".join(it["doelen"])
        else:
            s = "klaar: geen vinkjes"
        tel[s] += 1
        if s in ("niet beoordeeld", "opgeslagen, niet klaar"):
            print("  ", s, "|", w["merk"], w["mapnaam"])
    for k, v in sorted(tel.items()):
        print(f"{v:3}  {k}")
    print("plan.json items", len(plan), "waarvan pid onbekend", sum(1 for p in plan if p not in {w['pid'] for w in ws}))
    print("planning:", {d: len(b.get("volgorde", [])) for d, b in pl.items()})
