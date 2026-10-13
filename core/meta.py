"""Meta Graph API: installatie (tokens) en ophalen van FB-pagina-posts en IG-media.

Alleen lezen van je eigen accounts. Geen App Review nodig zolang jij beheerder
van de Meta-app bent (ontwikkelmodus).
"""
import datetime as dt

import requests

from . import config

BASE = "https://graph.facebook.com"
TIMEOUT = 30


class MetaFout(Exception):
    pass


def _get(cfg, pad, params):
    url = pad if pad.startswith("http") else f"{BASE}/{cfg['graph_version']}/{pad.lstrip('/')}"
    r = requests.get(url, params=params, timeout=TIMEOUT)
    try:
        data = r.json()
    except ValueError:
        raise MetaFout(f"Geen geldig antwoord van Meta (HTTP {r.status_code})")
    if "error" in data:
        e = data["error"]
        raise MetaFout(f"{e.get('type', 'Fout')} ({e.get('code')}): {e.get('message')}")
    return data


def _alle_paginas(cfg, pad, params, max_items=2000):
    data = _get(cfg, pad, params)
    items = list(data.get("data", []))
    while data.get("paging", {}).get("next") and len(items) < max_items:
        data = _get(cfg, data["paging"]["next"], {})
        items.extend(data.get("data", []))
    return items


# ---------- installatie ----------

def raad_merk(naam):
    n = (naam or "").lower()
    if "licht" in n or "dome" in n:
        return "Lichtjes"
    if "jarno" in n or "studio" in n:
        return "SJB"
    return naam or "?"


def installeer(cfg, app_id, app_secret, korte_token):
    """Wisselt een kort token om naar een lang token en haalt pagina-tokens op.

    Pagina-tokens die van een lang gebruikerstoken zijn afgeleid verlopen niet
    (zolang je wachtwoord en app-rechten gelijk blijven).
    """
    cfg["app_id"], cfg["app_secret"] = app_id.strip(), app_secret.strip()
    lang = _get(cfg, "oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": cfg["app_id"],
        "client_secret": cfg["app_secret"],
        "fb_exchange_token": korte_token.strip(),
    })
    cfg["user_token_long"] = lang["access_token"]
    if lang.get("expires_in"):
        cfg["user_token_expires"] = (dt.datetime.now() + dt.timedelta(seconds=int(lang["expires_in"]))).strftime("%Y-%m-%d")
    paginas = _alle_paginas(cfg, "me/accounts", {
        "fields": "id,name,access_token,instagram_business_account{id,username}",
        "access_token": cfg["user_token_long"],
        "limit": 100,
    })
    oud = {a.get("fb_page_id"): a for a in cfg.get("accounts", [])}
    accounts = []
    for p in paginas:
        ig = p.get("instagram_business_account") or {}
        vorig = oud.get(p["id"], {})
        accounts.append({
            "merk": vorig.get("merk") or raad_merk(p.get("name")),
            "fb_page_id": p["id"],
            "fb_naam": p.get("name", ""),
            "page_token": p["access_token"],
            "ig_user_id": ig.get("id", ""),
            "ig_username": ig.get("username", ""),
            "actief": vorig.get("actief", True),
        })
    cfg["accounts"] = accounts
    config.save_config(cfg)
    return accounts


def token_check(cfg):
    """Controleert per pagina-token of het nog geldig is."""
    uit = []
    for a in cfg.get("accounts", []):
        try:
            info = _get(cfg, "debug_token", {
                "input_token": a["page_token"],
                "access_token": f"{cfg['app_id']}|{cfg['app_secret']}",
            })["data"]
            exp = info.get("expires_at", 0)
            uit.append({"account": a["fb_naam"], "geldig": info.get("is_valid", False),
                        "verloopt": "nooit" if not exp else dt.datetime.fromtimestamp(exp).strftime("%Y-%m-%d")})
        except MetaFout as e:
            uit.append({"account": a.get("fb_naam"), "geldig": False, "verloopt": str(e)})
    return uit


# ---------- ophalen ----------

FB_VELDEN = [
    "id,message,created_time,permalink_url,full_picture,status_type,"
    "attachments{media_type,media,subattachments{media,media_type}}",
    "id,message,created_time,permalink_url,full_picture",  # terugval als attachments geweigerd wordt
]
IG_VELDEN = ("id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp,"
             "children{media_type,media_url,thumbnail_url}")


def _fb_posts(cfg, acc):
    laatste_fout = None
    for velden in FB_VELDEN:
        try:
            ruw = _alle_paginas(cfg, f"{acc['fb_page_id']}/posts",
                                {"fields": velden, "access_token": acc["page_token"], "limit": 50})
            break
        except MetaFout as e:
            laatste_fout = e
    else:
        raise laatste_fout
    posts = []
    for p in ruw:
        thumbs, n = [], 0
        for att in (p.get("attachments") or {}).get("data", []):
            subs = (att.get("subattachments") or {}).get("data", [])
            for s in subs or [att]:
                src = ((s.get("media") or {}).get("image") or {}).get("src")
                n += 1
                if src:
                    thumbs.append(src)
        if not thumbs and p.get("full_picture"):
            thumbs, n = [p["full_picture"]], max(n, 1)
        posts.append({
            "key": f"fb:{p['id']}",
            "platform": "fb",
            "merk": acc["merk"],
            "account": acc["fb_naam"],
            "id": p["id"],
            "caption": p.get("message", "") or "",
            "timestamp": p.get("created_time", ""),
            "permalink": p.get("permalink_url", ""),
            "media_type": p.get("status_type", ""),
            "thumbs": thumbs[:10],
            "n_media": n,
        })
    return posts


def _ig_posts(cfg, acc):
    ruw = _alle_paginas(cfg, f"{acc['ig_user_id']}/media",
                        {"fields": IG_VELDEN, "access_token": acc["page_token"], "limit": 50})
    posts = []
    for m in ruw:
        kids = (m.get("children") or {}).get("data", [])
        bron = kids or [m]
        thumbs = [k.get("thumbnail_url") or k.get("media_url") for k in bron]
        posts.append({
            "key": f"ig:{m['id']}",
            "platform": "ig",
            "merk": acc["merk"],
            "account": "@" + acc["ig_username"],
            "id": m["id"],
            "caption": m.get("caption", "") or "",
            "timestamp": m.get("timestamp", ""),
            "permalink": m.get("permalink", ""),
            "media_type": m.get("media_product_type") or m.get("media_type", ""),
            "thumbs": [t for t in thumbs if t][:10],
            "n_media": len(bron),
        })
    return posts


def haal_alles(cfg):
    """Haalt alle posts op van alle actieve accounts -> schrijft data/online.json."""
    posts, fouten = [], []
    for acc in cfg.get("accounts", []):
        if not acc.get("actief", True):
            continue
        try:
            posts += _fb_posts(cfg, acc)
        except MetaFout as e:
            fouten.append(f"FB {acc.get('fb_naam')}: {e}")
        if acc.get("ig_user_id"):
            try:
                posts += _ig_posts(cfg, acc)
            except MetaFout as e:
                fouten.append(f"IG @{acc.get('ig_username')}: {e}")
    posts.sort(key=lambda p: p["timestamp"], reverse=True)
    data = {"opgehaald": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "posts": posts, "fouten": fouten}
    config.save_json(config.ONLINE_PATH, data)
    return data
