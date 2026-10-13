import json, os
D = os.path.join(os.path.dirname(__file__), "..", "data")
o = json.load(open(os.path.join(D, "online.json"), encoding="utf-8"))
print("opgehaald:", o.get("opgehaald"))
per = {}
for p in o["posts"]:
    k = (p["platform"], p["account"])
    if k not in per or p["timestamp"] > per[k]["timestamp"]:
        per[k] = p
for k, p in sorted(per.items()):
    print(k, p["timestamp"], p["permalink"], (p.get("caption") or "")[:60].replace("\n", " "))
