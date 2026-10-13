import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402

pids = {w["pid"] for w in A.werken(herscan=True)}
lk = A.links()
wees = [k for k, v in lk.items() if v["pid"] not in pids]
print("links:", len(lk), "wees:", len(wees), wees[:5])
