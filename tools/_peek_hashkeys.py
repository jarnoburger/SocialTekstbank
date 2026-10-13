import json, os
D = os.path.join(os.path.dirname(__file__), "..", "data")
h = json.load(open(os.path.join(D, "hashes.json"), encoding="utf-8"))
lk = json.load(open(os.path.join(D, "links.json"), encoding="utf-8"))
ks = list(h["online"])[:4]
print(ks, [str(h["online"][k])[:60] for k in ks])
print(list(lk)[:3])
