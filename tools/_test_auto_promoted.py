"""Rondje-test: één werk via de echte functie naar _Promoted en weer terug. Controleert pid/koppelingen."""
import os, sys, json
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
with A.app.test_request_context():
    ws = A.werken(herscan=True)
    w = next(w for w in ws if not w["los"] and w["mapnaam"] == "2008 Badkamer")
    lk0 = json.dumps(config.load_json(config.LINKS_PATH, {}), sort_keys=True)
    plan0 = json.dumps(config.load_json(A.PLAN_PATH, {}), sort_keys=True)
    print("start", w["pad"], w["pid"])
    p1 = A._verhuis_werk(w, True)
    w1 = A.werk_map()[p1]
    print("na heen", w1["pad"], p1, "in plan.json:", p1 in config.load_json(A.PLAN_PATH, {}))
    p2 = A._verhuis_werk(w1, False)
    w2 = A.werk_map()[p2]
    print("na terug", w2["pad"], p2, "pid gelijk:", p2 == w["pid"])
    print("links ongewijzigd:", json.dumps(config.load_json(config.LINKS_PATH, {}), sort_keys=True) == lk0)
    print("plan ongewijzigd:", json.dumps(config.load_json(A.PLAN_PATH, {}), sort_keys=True) == plan0)
    print("beelden in index:", len(A.beelden_index().get(p2) or []))
