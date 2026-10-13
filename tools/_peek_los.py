import os, sys
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
with A.app.test_request_context():
    lpw = A.links_per_werk()
    for w in A.werken(herscan=True):
        if w["los"]:
            print(w["merk"], w["pad"], "| media", len(w["media"]), "| lokaal", w["n_lokaal"], "| gekoppelde posts", len(lpw.get(w["pid"], [])))
