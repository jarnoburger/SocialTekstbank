"""Alleen lezen: controle na verplaatsen naar _Promoted."""
import os, sys, collections
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
with A.app.test_request_context():
    ws = A.werken(herscan=True)
    wm = {w["pid"]: w for w in ws}
    print("werken totaal", len(ws), collections.Counter(("_Promoted" in w["pad"], w["merk"]) for w in ws if not w["los"]))
    lk = config.load_json(config.LINKS_PATH, {})
    kapot = [k for k, v in lk.items() if v["pid"] not in wm]
    print("koppelingen", len(lk), "kapot", len(kapot), kapot[:5])
    bidx = A.beelden_index()
    prom = [w for w in ws if "_Promoted" in w["pad"]]
    print("promoted met beelden in index", sum(1 for w in prom if bidx.get(w["pid"])), "van", len(prom))
    print("in Plannen", len(A._plan_werken()))
