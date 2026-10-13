import json, collections, os
D = os.path.join(os.path.dirname(__file__), "..", "data")
o = json.load(open(os.path.join(D, "online.json"), encoding="utf-8"))
print(type(o), list(o.keys())[:10] if isinstance(o, dict) else "")
posts = o["posts"]
print(len(posts))
p = posts[0]
print({k: (str(v)[:80]) for k, v in p.items()})
c = collections.Counter((p.get("platform"), p.get("account")) for p in posts)
print(c)
fb = next((p for p in posts if p.get("platform") == "fb"), None)
print({k: (str(v)[:80]) for k, v in (fb or {}).items()})
