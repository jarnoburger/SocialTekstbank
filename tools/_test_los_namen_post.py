"""Test POST /los/namen op een 'later'-item met getypte naam; besluitbestand wordt daarna hersteld."""
import os, sys, shutil, re
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config
P = A.LOS_BESLUIT_PATH
shutil.copy(P, P + ".testbak")
try:
    c = A.app.test_client()
    h = c.get("/los/namen").data.decode("utf-8")
    keys = re.findall(r'name="key" value="([^"]+)"', h)
    idx = {k: re.search(r'name="idx_' + re.escape(k) + r'" value="(\d+)"', h).group(1) for k in keys}
    bes = config.load_json(P, {})
    later = next(k for k in keys if bes.get(k.replace("&#39;", "'").replace("&amp;", "&"), {}).get("actie") == "later")
    form = {"key": keys}
    for k in keys:
        form["idx_" + k] = idx[k]
        form["naam_" + idx[k]] = ""
        form["actie_" + idx[k]] = bes.get(k, {}).get("actie", "nieuw") if bes.get(k, {}).get("actie") != "werk" else "nieuw"
    form["naam_" + idx[later]] = "2099 Testwerk"   # select blijft op 'later'
    r = c.post("/los/namen", data=form)
    na = config.load_json(P, {})
    print("status", r.status_code, "| later-item nu:", na[later]["actie"], na[later].get("naam"))
    veranderd = [k for k in keys if k != later and {a: bes.get(k, {}).get(a) for a in ("actie", "pid", "naam")} != {a: na.get(k, {}).get(a) for a in ("actie", "pid", "naam")}]
    print("andere items onbedoeld veranderd:", len(veranderd), veranderd[:3])
finally:
    shutil.copy(P + ".testbak", P)
    os.remove(P + ".testbak")
    print("besluitbestand hersteld")
