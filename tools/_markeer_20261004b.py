"""Eenmalig: verplaats-markeringen volgens keuzes Jarno 04-10-2026 20:27 (via chat i.p.v. Review)."""
import sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
from core import config

NU = dt.datetime.now().isoformat(timespec="seconds")
per_naam = {w["mapnaam"]: w for w in A.werken() if not w["los"]}
posts = A.online()["posts"]
links = A.links()


def post_key(stukje):
    ks = [p["key"] for p in posts if stukje in (p.get("permalink") or "")]
    ks = [k for k in ks if k in links]
    if len(ks) != 1:
        raise SystemExit(f"post niet eenduidig: {stukje} -> {ks}")
    return ks[0]


KEUZES = [  # (item, van, naar)
    (("post", "DNxK4UE0Hrl"), "1998-2008 Lowlands", "2024 Lilian Kreutzberger"),
    (("post", "122136364694927556"), "2022 Grid Statue", "2023-2025 Begraafplaats"),
    (("post", "DMI8WXjtHy1"), "2023-2025 Houtwerk", "2023-2025 Begraafplaats"),
    (("lokaal", "Photos/IMG_9992 2.tif"), "2014 Mayda", "2022 Me at Work in General"),
]
V = config.load_json(A.VERPLAATS_PATH, {})
for (soort, ref), van_n, naar_n in KEUZES:
    van, naar = per_naam[van_n], per_naam[naar_n]
    if soort == "post":
        k = post_key(ref)
        if links[k]["pid"] not in (van["pid"], naar["pid"]):
            raise SystemExit(f"{k} hangt niet aan {van_n} maar aan {links[k]['pid']}")
        iid = "post:" + k
    else:
        iid = f"lokaal:{van['pid']}:{ref}"
    V[iid] = {"van": van["pid"], "van_map": van_n, "naar": naar["pid"], "naar_map": naar_n,
              "nieuw": False, "merk": naar["merk"], "op": NU, "bron": "chat"}
    print(iid, ":", van_n, "->", naar_n)
config.save_json(A.VERPLAATS_PATH, V)
