"""Alleen lezen: staan in _To Promote precies de werken die in de Planning-tab staan?"""
import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
c = A.app.test_client()
with A.app.test_request_context():
    ws = [w for w in A.werken(herscan=True) if not w["los"]]
    tp = {w["pid"]: w for w in ws if os.sep + "_To Promote" + os.sep in w["pad"]}
    from core import config
    plan = config.load_json(A.PLAN_PATH, {})
    wm = {w["pid"]: w for w in ws}
    in_planning = {p for p, it in plan.items() if it.get("klaar") and not it.get("niet") and it.get("doelen")
                   and any(d in {e[0] for e in A._eigen_doelen(wm[p])} for d in it["doelen"]) if p in wm}
print("in _To Promote:", len(tp), "| in Planning-tab:", len(in_planning))
print("in _To Promote maar NIET in planning:", [tp[p]["mapnaam"] for p in tp if p not in in_planning])
print("in planning maar NIET in _To Promote:", [wm[p]["mapnaam"] + " (" + wm[p]["pad"] + ")" for p in in_planning if p not in tp])
for root in (r"C:\Users\jarno\OneDrive\_Studio JarnoBurger\_To Promote", r"C:\Users\jarno\OneDrive\_Lichtjes Dome\_To Promote"):
    print(root, "->", sorted(os.listdir(root))[:3], "... totaal", len(os.listdir(root)))
    print("   niet-werk mappen/bestanden:", [n for n in os.listdir(root) if not any(w["pad"].endswith(os.sep + n) for w in tp.values())])
