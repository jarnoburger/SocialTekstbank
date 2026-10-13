import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
with A.app.test_request_context():
    bes = config.load_json(A.NM_BESLUIT_PATH, {})
    alle = A._nm_werken()
    for w, b, c in alle:
        x = bes.get(A._nm_sleutel(w), {})
        print(f'{w["merk"]:8} {w["mapnaam"][:32]:32} {x.get("besluit","OPEN"):5} {",".join(x.get("doelen", []))} | map: {"Promoted" if "_Promoted" in w["pad"] else "To Promote"}')
    print("totaal", len(alle), "beslist", sum(1 for w, b, c in alle if A._nm_sleutel(w) in bes))
