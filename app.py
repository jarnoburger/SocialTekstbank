"""SocialTekstbank: lokale web-app die je werk-teksten verzamelt en je socials checkt.

Start:  python app.py   (of start.bat)  ->  http://127.0.0.1:5077
"""
import collections
import datetime as dt
import glob
import hashlib
import time
import io
import json
import os
import re
import threading
import webbrowser

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, url_for, Response)
from PIL import Image

from core import config, group, local, match, meta, textfile
from core import captions as capt

app = Flask(__name__)
app.secret_key = "socialtekstbank-lokaal"
THUMB_DIR = os.path.join(config.DATA_DIR, "thumbs")

STATE = {"werken": None, "gescand": None, "suggesties": {}, "groepen": [], "lock": threading.Lock()}


# ---------- gedeelde helpers ----------

def cfg():
    return config.load_config()


def werken(herscan=False):
    with STATE["lock"]:
        if STATE["werken"] is None or herscan:
            STATE["werken"] = local.scan(cfg()["roots"])
            STATE["gescand"] = dt.datetime.now().strftime("%H:%M")
    return STATE["werken"]


def werk_map():
    return {w["pid"]: w for w in werken()}


def online():
    return config.load_json(config.ONLINE_PATH, {"opgehaald": None, "posts": [], "fouten": []})


def zorg_voor_suggesties():
    if not STATE["groepen"] and online()["posts"]:
        _match(online_hashen=False)


def links():
    return config.load_json(config.LINKS_PATH, {})


def opruimen():
    return config.load_json(config.OPRUIMEN_PATH, {})


def links_per_werk():
    uit = {}
    for key, v in links().items():
        uit.setdefault(v["pid"], []).append(key)
    return uit


def herlaad_werk(pid):
    """Na het schrijven van _tekst.md: alleen dit werk opnieuw inlezen."""
    for i, w in enumerate(STATE["werken"] or []):
        if w["pid"] == pid:
            t = textfile.lees(w["pad"])
            w["tekst"], w["status"] = t, textfile.status(t, len(w["media"]))
            return w


def schrijf_social_json(w):
    """Spiegel van de koppelingen in de projectmap (_social.json), handig buiten de app."""
    if w["los"]:
        return
    alle = online()["posts"]
    per_key = {p["key"]: p for p in alle}
    keys = links_per_werk().get(w["pid"], [])
    data = [{k: per_key[key][k] for k in ("platform", "account", "id", "timestamp", "permalink", "caption")}
            for key in keys if key in per_key]
    pad = os.path.join(w["pad"], "_social.json")
    if data:
        with open(pad, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif os.path.exists(pad):
        with open(pad, "w", encoding="utf-8") as f:
            f.write("[]\n")


@app.context_processor
def globaal():
    return {"nu_gescand": STATE["gescand"], "merken": sorted({r["merk"] for r in cfg()["roots"]})}


@app.template_filter("datum")
def _datum(ts):
    return (ts or "")[:10]


@app.template_filter("linkify")
def _linkify(s):
    """Maakt URLs en @handles klikbaar (escaped)."""
    import re
    from markupsafe import escape, Markup
    tekst = str(escape(s or ""))
    tekst = re.sub(r"(https?://[^\s<>()]+[^\s<>().,;:])", r'<a href="\1" target="_blank" rel="noopener">\1</a>', tekst)
    # alleen Instagram-handles: na '· ', '(', ', ' of regelbegin; niet als X/TikTok erbij staat
    tekst = re.sub(r"(?m)(^|· |\(|, )@([A-Za-z0-9_.]*[A-Za-z0-9_])(?! op (?:TikTok|X\b))",
                   r'\1<a href="https://www.instagram.com/\2/" target="_blank" rel="noopener">@\2</a>', tekst)
    return Markup(tekst)


@app.template_filter("kort")
def _kort(s, n=160):
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n].rstrip() + "…"


# ---------- pagina's ----------

@app.route("/")
def overzicht():
    ws = werken()
    on = online()
    lk = links()
    gekoppeld = set(lk.keys()) | set(opruimen().keys())
    per_merk = {}
    for w in ws:
        m = per_merk.setdefault(w["merk"], {"werken": 0, "met_tekst": 0, "volledig": 0, "zonder": 0,
                                            "media": 0, "posts": 0, "zonder_caption": 0, "ongekoppeld": 0})
        m["werken"] += 1
        m["media"] += len(w["media"])
        if w["status"]["score"] == 3:
            m["volledig"] += 1
        elif w["status"]["score"] > 0:
            m["met_tekst"] += 1
        else:
            m["zonder"] += 1
    for p in on["posts"]:
        m = per_merk.setdefault(p["merk"], {"werken": 0, "met_tekst": 0, "volledig": 0, "zonder": 0,
                                            "media": 0, "posts": 0, "zonder_caption": 0, "ongekoppeld": 0})
        m["posts"] += 1
        if not p["caption"].strip():
            m["zonder_caption"] += 1
        if p["key"] not in gekoppeld:
            m["ongekoppeld"] += 1
    zorg_voor_suggesties()
    for g in STATE["groepen"]:
        m = per_merk.get(g["merk"])
        if m is not None:
            m["groepen"] = m.get("groepen", 0) + 1
            if any(k not in gekoppeld for k in g["keys"]):
                m["groepen_open"] = m.get("groepen_open", 0) + 1
    accounts = cfg().get("accounts", [])
    return render_template("overzicht.html", per_merk=per_merk, on=on, accounts=accounts,
                           n_links=len(lk))


@app.route("/lokaal")
def lokaal():
    merk = request.args.get("merk", "")
    filt = request.args.get("filter", "")
    lpw = links_per_werk()
    rijen = []
    for w in werken():
        if merk and w["merk"] != merk:
            continue
        n_posts = len(lpw.get(w["pid"], []))
        if filt == "gaten" and w["status"]["score"] == 3:
            continue
        if filt == "leeg" and w["status"]["score"] > 0:
            continue
        if filt == "te_posten" and (n_posts or w["promotie"] in ("gepromoot", "niet promoten") or w["los"]):
            continue
        if filt == "online" and not n_posts:
            continue
        if filt == "ongekoppeld" and (n_posts or w["promotie"] != "gepromoot"):
            continue
        rijen.append((w, n_posts))
    return render_template("lokaal.html", rijen=rijen, merk=merk, filt=filt)


@app.route("/werk/<pid>", methods=["GET", "POST"])
def werk(pid):
    w = werk_map().get(pid) or abort(404)
    zorg_voor_suggesties()
    if request.method == "POST":
        data = w["tekst"] or textfile.leeg()
        for naam in textfile.VELD_NAMEN:
            if f"veld_{naam}" in request.form:
                data["velden"][naam] = request.form[f"veld_{naam}"].replace("\r\n", "\n").strip()
        for m in w["media"]:
            k = f"pb_{m['rel']}"
            if k in request.form:
                tekst = request.form[k].replace("\r\n", "\n").strip()
                if tekst:
                    data["per_bestand"][m["rel"]] = tekst
                else:
                    data["per_bestand"].pop(m["rel"], None)
        textfile.schrijf(w["pad"], data)
        if "promotie" in request.form and not w["los"] and request.form["promotie"] != w["promotie"]:
            local.zet_yml(w["pad"], "promotie", request.form["promotie"])
            w["yml"]["promotie"] = request.form["promotie"]
            w["promotie"] = local.promotie_status(w["yml"])
        if "trefwoorden" in request.form and not w["los"]:
            tw = ", ".join(x.strip() for x in request.form["trefwoorden"].split(",") if x.strip())
            if tw != w["yml"].get("trefwoorden", ""):
                local.zet_yml(w["pad"], "trefwoorden", tw)
                w["yml"]["trefwoorden"] = tw
                STATE["groepen"] = []  # voorstellen opnieuw berekenen
        herlaad_werk(pid)
        flash(f"Opgeslagen in {textfile.TEKST_NAAM}")
        return redirect(url_for("werk", pid=pid, alles=request.args.get("alles", "")))

    alles = request.args.get("alles") == "1"
    media = w["media"] if alles else w["media"][:48]
    per_key = {p["key"]: p for p in online()["posts"]}
    gekoppeld = [per_key[k] for k in links_per_werk().get(pid, []) if k in per_key]
    lk = links()
    voorstellen = []
    for g in STATE["groepen"]:
        if all(k in lk for k in g["keys"]):
            continue
        for score, kpid, redenen in STATE["suggesties"].get(g["gid"], []):
            if kpid == pid:
                voorstellen.append((g, score, redenen))
    voorstellen.sort(key=lambda x: -x[1])
    tekst = w["tekst"] or textfile.leeg()
    return render_template("werk.html", w=w, media=media, alles=alles, tekst=tekst,
                           velden=textfile.VELDEN, gekoppeld=gekoppeld, voorstellen=voorstellen[:12])


def hernoem_werk(w, nieuwe_naam, jaar=None):
    """Mapnaam en/of jaar wijzigen; koppelingen (links.json) verhuizen mee. Geeft nieuw pid terug."""
    pad = w["pad"]
    if jaar is not None and jaar != w["yml"].get("jaar", ""):
        local.zet_yml(pad, "jaar", jaar)
    if nieuwe_naam and nieuwe_naam != w["mapnaam"]:
        nieuw = local.hernoem_map(pad, nieuwe_naam)
        nieuw_pid = local.pid_voor(nieuw)
        lk = links()
        for v in lk.values():
            if v["pid"] == w["pid"]:
                v["pid"], v["pad"] = nieuw_pid, nieuw
        config.save_json(config.LINKS_PATH, lk)
        return nieuw_pid
    return w["pid"]


@app.route("/werk/<pid>/hernoem", methods=["POST"])
def werk_hernoem(pid):
    w = werk_map().get(pid) or abort(404)
    if w["los"]:
        abort(400)
    try:
        nieuw_pid = hernoem_werk(w, request.form.get("mapnaam", "").strip(),
                                 request.form.get("jaar", "").strip())
    except (ValueError, OSError) as e:
        flash(f"Hernoemen mislukt: {e}", "fout")
        return redirect(url_for("werk", pid=pid))
    werken(herscan=True)
    STATE["groepen"] = []
    flash("Werk bijgewerkt")
    return redirect(url_for("werk", pid=nieuw_pid))


@app.route("/online")
def online_pagina():
    zorg_voor_suggesties()
    on = online()
    account = request.args.get("account", "")
    filt = request.args.get("filter", "")
    lk = links()
    wm = werk_map()
    weg = opruimen()
    rijen = []
    for g in STATE["groepen"]:
        if account and account not in g["accounts"]:
            continue
        is_weg = all(k in weg for k in g["keys"])
        if (filt == "opruimen") != is_weg:
            continue
        open_keys = [k for k in g["keys"] if k not in lk]
        if filt == "geen_caption" and not g["n_zonder"]:
            continue
        if filt == "ongekoppeld" and not open_keys:
            continue
        gekoppeld = []
        for k in g["keys"]:
            if k in lk and lk[k]["pid"] in wm and wm[lk[k]["pid"]] not in gekoppeld:
                gekoppeld.append(wm[lk[k]["pid"]])
        per_post = {k: wm.get(lk[k]["pid"]) if k in lk else None for k in g["keys"]}
        kand = [(sc, wm[pid], r) for sc, pid, r in STATE["suggesties"].get(g["gid"], []) if pid in wm]
        rijen.append((g, gekoppeld, kand, open_keys, per_post))
    accounts = sorted({p["account"] for p in on["posts"]})
    alle_werken = sorted(wm.values(), key=lambda w: (w["merk"], w["naam"].lower()))
    n_posts = sum(len(r[0]["keys"]) for r in rijen)
    return render_template("online.html", on=on, rijen=rijen, accounts=accounts, account=account,
                           filt=filt, alle_werken=alle_werken, n_posts=n_posts, n_weg=len(weg))


@app.route("/opruimen", methods=["POST"])
def opruimen_actie():
    keys = request.form.getlist("post_key")
    weg = opruimen()
    if request.form.get("terug"):
        for k in keys:
            weg.pop(k, None)
        flash(f"{len(keys)} post(s) teruggezet")
    else:
        for k in keys:
            weg[k] = dt.datetime.now().strftime("%Y-%m-%d")
        flash(f"{len(keys)} post(s) op de opruimlijst gezet (verwijder ze zelf online via de link)")
    config.save_json(config.OPRUIMEN_PATH, weg)
    return redirect(request.referrer or url_for("online_pagina"))


@app.route("/instellingen", methods=["GET", "POST"])
def instellingen():
    c = cfg()
    if request.method == "POST":
        c["graph_version"] = request.form.get("graph_version", c["graph_version"]).strip()
        for i, a in enumerate(c.get("accounts", [])):
            a["merk"] = request.form.get(f"merk_{i}", a["merk"]).strip()
            a["actief"] = request.form.get(f"actief_{i}") == "on"
        roots = []
        for i in range(6):
            pad = request.form.get(f"root_pad_{i}", "").strip()
            merk = request.form.get(f"root_merk_{i}", "").strip()
            if pad and merk:
                roots.append({"merk": merk, "pad": pad})
        if roots:
            c["roots"] = roots
        config.save_config(c)
        flash("Instellingen opgeslagen")
        return redirect(url_for("instellingen"))
    return render_template("instellingen.html", c=c, tokens=None)


@app.route("/instellingen/token", methods=["POST"])
def instellingen_token():
    c = cfg()
    try:
        accs = meta.installeer(c, request.form["app_id"], request.form["app_secret"], request.form["token"])
        flash(f"Gekoppeld: {len(accs)} pagina('s) gevonden. Controleer hieronder het merk per pagina.")
    except Exception as e:  # noqa: BLE001
        flash(f"Koppelen mislukt: {e}", "fout")
    return redirect(url_for("instellingen"))


@app.route("/instellingen/check")
def instellingen_check():
    c = cfg()
    return render_template("instellingen.html", c=c, tokens=meta.token_check(c))


# ---------- acties ----------

@app.route("/actie/herscan", methods=["POST"])
def actie_herscan():
    ws = werken(herscan=True)
    flash(f"Gescand: {len(ws)} werken")
    return redirect(request.referrer or url_for("overzicht"))


@app.route("/actie/ophalen", methods=["POST"])
def actie_ophalen():
    c = cfg()
    if not c.get("accounts"):
        flash("Nog geen Meta-koppeling. Doe eerst de installatie bij Instellingen.", "fout")
        return redirect(url_for("instellingen"))
    data = meta.haal_alles(c)
    for f_ in data["fouten"]:
        flash(f_, "fout")
    flash(f"Opgehaald: {len(data['posts'])} posts")
    _match(online_hashen=False)
    return redirect(request.referrer or url_for("online_pagina"))


def _match(online_hashen=False):
    hc = match.HashCache()
    STATE["groepen"] = group.maak_groepen(online()["posts"])
    STATE["suggesties"] = match.bereken(werken(), STATE["groepen"], hashes=hc,
                                        drempel=cfg()["hash_drempel"], online_hashen=online_hashen)
    hc.save()


@app.route("/actie/match", methods=["POST"])
def actie_match():
    _match(online_hashen=True)
    n = sum(1 for v in STATE["suggesties"].values() if v)
    flash(f"Matchen klaar: {n} van {len(STATE['groepen'])} posts hebben een voorstel")
    return redirect(request.referrer or url_for("online_pagina"))


@app.route("/actie/hash/<pid>", methods=["POST"])
def actie_hash_werk(pid):
    """Hash ook de cloud-only foto's van één werk (OneDrive downloadt ze dan)."""
    w = werk_map().get(pid) or abort(404)
    hc = match.HashCache()
    n = sum(1 for m in w["media"][:200] if hc.lokaal(m, forceer=True) is not None)
    hc.save()
    _match(online_hashen=True)
    flash(f"{n} foto's van dit werk vergeleken")
    return redirect(url_for("werk", pid=pid))


@app.route("/koppel", methods=["POST"])
def koppel():
    keys = request.form.getlist("post_key")
    pid = request.form.get("pid", "")
    lk = links()
    wm = werk_map()
    oude = {lk[k]["pid"] for k in keys if k in lk}
    if request.form.get("ontkoppel") or not pid:
        for k in keys:
            lk.pop(k, None)
        config.save_json(config.LINKS_PATH, lk)
        for o in oude:
            if o in wm:
                schrijf_social_json(wm[o])
        flash(f"Ontkoppeld ({len(keys)} post(s))")
        return redirect(request.referrer or url_for("online_pagina"))
    w = wm.get(pid) or abort(404)
    vandaag = dt.datetime.now().strftime("%Y-%m-%d")
    per_key = {p["key"]: p for p in online()["posts"]}
    n_cap = 0
    for k in keys:
        lk[k] = {"pid": pid, "pad": w["pad"], "op": vandaag}
        post = per_key.get(k)
        if post and post["caption"].strip():
            if textfile.voeg_caption_toe(w["pad"], post["platform"], post["timestamp"][:10],
                                         post["permalink"], post["caption"]):
                n_cap += 1
    config.save_json(config.LINKS_PATH, lk)
    herlaad_werk(pid)
    tekst = f"{len(keys)} post(s) gekoppeld aan {w['naam']}"
    tekst += f"; {n_cap} nieuwe caption(s) bewaard in {textfile.TEKST_NAAM}" if n_cap else ""
    flash(tekst)
    schrijf_social_json(w)
    for o in oude:
        if o != pid and o in wm:
            schrijf_social_json(wm[o])
    return redirect(request.referrer or url_for("online_pagina"))


@app.route("/export")
def export():
    regels = [f"# Tekstbank Studio Jarno Burger & Lichtjes",
              f"_Gegenereerd {dt.datetime.now():%Y-%m-%d %H:%M} door SocialTekstbank_", ""]
    huidig_merk = None
    for w in werken():
        if not w["tekst"] or w["status"]["score"] == 0:
            continue
        if w["merk"] != huidig_merk:
            huidig_merk = w["merk"]
            regels += [f"## {huidig_merk}", ""]
        v = w["tekst"]["velden"]
        regels.append(f"### {v.get('Titel') or w['naam']}" + (f" ({w['jaar']})" if w["jaar"] else ""))
        for naam in textfile.VELD_NAMEN[1:]:
            if v.get(naam):
                regels += [f"**{naam}:** {v[naam]}", ""]
        regels += [f"_Map: {w['rel']}_", ""]
    os.makedirs(config.EXPORT_DIR, exist_ok=True)
    pad = os.path.join(config.EXPORT_DIR, "Tekstbank.md")
    with open(pad, "w", encoding="utf-8") as f:
        f.write("\n".join(regels))
    return send_file(pad, as_attachment=True, download_name="Tekstbank.md")


# ---------- thumbnails ----------


# ---------- review: foto + Claude-tekst + huidige tekst ----------

BEELDEN_DIR = os.path.join(config.DATA_DIR, "beelden")
REVIEW_WAARDEN = ("ok", "aangepast", "fout")
_BEELD_CACHE = {"mtime": None, "idx": {}}


def beelden_index():
    """{pid: [beeld]} uit data/beelden/batch*/manifest.json (nieuwste batch wint)."""
    if not os.path.isdir(BEELDEN_DIR):
        return {}
    manifests = sorted(os.path.join(BEELDEN_DIR, d, "manifest.json") for d in os.listdir(BEELDEN_DIR)
                       if os.path.exists(os.path.join(BEELDEN_DIR, d, "manifest.json")))
    sleutel = tuple(os.path.getmtime(m) for m in manifests)
    if _BEELD_CACHE["mtime"] == sleutel:
        return _BEELD_CACHE["idx"]
    idx, later = {}, []
    for mp in manifests:
        batch = os.path.basename(os.path.dirname(mp))
        for x in config.load_json(mp, []):
            lijst = []
            for b in x.get("beelden", []):
                d = dict(b)
                d["src"] = f"{batch}/{x['map']}/{b['bestand']}"
                lijst.append(d)
            if x.get("samengevoegd_in"):
                later.append((x["pid"], lijst))  # beelden van een samengevoegd werk komen ná die van het doel
                continue
            idx[x["pid"]] = lijst
            idx.setdefault("naam:" + x["mapnaam"].lower(), lijst)
    for pid, lijst in later:
        idx[pid] = idx.get(pid, []) + lijst
    _BEELD_CACHE.update(mtime=sleutel, idx=idx)
    return idx


def _alt_teksten(beeldtekst):
    """Splitst de Beeldbeschrijving in (alinea, [(bron, alt)] in volgorde, twijfel).
    Regels per beeld: '- <bron>: <alt>' (bron = 'IG 2025-07-15 <link>' of 'lokaal <bestand>')."""
    alinea, alts, twijfel = [], [], ""
    for regel in (beeldtekst or "").splitlines():
        r = regel.strip()
        if r.startswith("- ") and ": " in r:
            bron, tekst = r[2:].split(": ", 1)
            alts.append((bron.strip(), tekst.strip()))
        elif r.lower().startswith("twijfel:"):
            twijfel = r[8:].strip()
        elif r and not r.startswith("_") and not r.lower().startswith("beelden"):
            alinea.append(r)
    return " ".join(alinea), alts, twijfel


def review_status(w):
    return (w["yml"].get("review") or "").strip()


def _review_rij(w, bidx):
    bt = (w["tekst"] or textfile.leeg())["velden"].get("Beeldbeschrijving", "")
    _, _, twijfel = _alt_teksten(bt)
    return {"w": w, "status": review_status(w), "heeft_tekst": bool(bt.strip()), "twijfel": twijfel,
            "n_beelden": len(bidx.get(w["pid"]) or bidx.get("naam:" + w["mapnaam"].lower()) or [])}


@app.route("/review")
def review_lijst():
    bidx = beelden_index()
    merk = request.args.get("merk", "")
    filt = request.args.get("filter", "open")
    rijen = [_review_rij(w, bidx) for w in werken() if not w["los"] and (not merk or w["merk"] == merk)]
    tel = {"open": sum(1 for r in rijen if not r["status"] and r["heeft_tekst"]),
           "twijfel": sum(1 for r in rijen if r["twijfel"] and not r["status"]),
           "ok": sum(1 for r in rijen if r["status"] in ("ok", "aangepast")),
           "fout": sum(1 for r in rijen if r["status"] == "fout"),
           "geen": sum(1 for r in rijen if not r["heeft_tekst"]),
           "alle": len(rijen)}
    kies = {"open": lambda r: not r["status"] and r["heeft_tekst"],
            "twijfel": lambda r: r["twijfel"] and not r["status"],
            "ok": lambda r: r["status"] in ("ok", "aangepast"),
            "fout": lambda r: r["status"] == "fout",
            "geen": lambda r: not r["heeft_tekst"]}.get(filt, lambda r: True)
    rijen = sorted((r for r in rijen if kies(r)), key=lambda r: (r["w"]["jaar"] or "9999", r["w"]["mapnaam"].lower()))
    return render_template("review_lijst.html", rijen=rijen, tel=tel, filt=filt, merk=merk)


def _volgende_open(na_pid, merk=""):
    lijst = sorted((w for w in werken() if not w["los"] and (not merk or w["merk"] == merk)),
                   key=lambda w: (w["jaar"] or "9999", w["mapnaam"].lower()))
    pids = [w["pid"] for w in lijst]
    start = pids.index(na_pid) + 1 if na_pid in pids else 0
    for w in lijst[start:] + lijst[:start]:
        heeft = (w["tekst"] or textfile.leeg())["velden"].get("Beeldbeschrijving", "").strip()
        if heeft and not review_status(w) and w["pid"] != na_pid:
            return w["pid"]
    return None


@app.route("/review/<pid>", methods=["GET", "POST"])
def review(pid):
    w = werk_map().get(pid) or abort(404)
    merk = request.args.get("merk", "")
    if request.method == "POST":
        actie = request.form.get("actie", "")
        data = w["tekst"] or textfile.leeg()
        for naam in ("Beeldbeschrijving", "Caption NL", "Caption EN", "Kort"):
            k = f"veld_{naam}"
            if k in request.form:
                data["velden"][naam] = request.form[k].replace("\r\n", "\n").strip()
        textfile.schrijf(w["pad"], data)
        notitie = request.form.get("notitie", "").replace("\n", " ").strip()
        if actie in REVIEW_WAARDEN:
            local.zet_yml(w["pad"], "review", actie)
            w["yml"]["review"] = actie
        elif actie == "reset":
            local.zet_yml(w["pad"], "review", "")
            w["yml"]["review"] = ""
        if notitie != w["yml"].get("review_notitie", ""):
            local.zet_yml(w["pad"], "review_notitie", notitie)
            w["yml"]["review_notitie"] = notitie
        n_verpl = _verwerk_verplaats(w, request.form)
        herlaad_werk(pid)
        flash(f"{w['mapnaam']}: {actie or 'opgeslagen'}"
              + (f" · {n_verpl} verplaats-markering(en) bijgewerkt" if n_verpl else ""))
        if actie in REVIEW_WAARDEN:
            nxt = _volgende_open(pid, merk)
            if nxt:
                return redirect(url_for("review", pid=nxt, merk=merk))
            flash("Alles beoordeeld 🎉")
            return redirect(url_for("review_lijst", merk=merk, filter="alle"))
        return redirect(url_for("review", pid=pid, merk=merk))

    bidx = beelden_index()
    tekst = w["tekst"] or textfile.leeg()
    bt = tekst["velden"].get("Beeldbeschrijving", "")
    alinea, alts, twijfel = _alt_teksten(bt)
    per_key = {p["key"]: p for p in online()["posts"]}
    verpl = verplaatsingen()
    beelden, gezien_iid = [], set()
    for b in bidx.get(pid) or bidx.get("naam:" + w["mapnaam"].lower()) or []:
        post = per_key.get(b.get("post") or "")
        n = len(beelden)
        alt = alts[n][1] if n < len(alts) else ""
        iid = item_id(pid, b)
        beelden.append({"b": b, "post": post, "alt": alt, "iid": iid,
                        "eerste": iid not in gezien_iid, "verpl": verpl.get(iid)})
        gezien_iid.add(iid)
    gekoppeld = sorted((per_key[k] for k in links_per_werk().get(pid, []) if k in per_key),
                       key=lambda p: p["timestamp"])
    # lokale previews als er geen opgehaalde beelden zijn (alleen niet-cloud foto's)
    lokaal = []
    if not beelden:
        for i, m in enumerate(w["media"]):
            if m["type"] == "img" and not m["cloud"]:
                iid = f"lokaal:{pid}:{m['rel']}"
                lokaal.append({"i": i, "iid": iid, "naam": m["rel"], "verpl": verpl.get(iid)})
        lokaal = lokaal[:24]
    alle = sorted((x for x in werken() if not x["los"] and (not merk or x["merk"] == merk)),
                  key=lambda x: (x["jaar"] or "9999", x["mapnaam"].lower()))
    pids = [x["pid"] for x in alle]
    i = pids.index(pid) if pid in pids else 0
    vorige = pids[i - 1] if i > 0 else None
    volgende = pids[i + 1] if i + 1 < len(pids) else None
    return render_template("review.html", w=w, tekst=tekst, beelden=beelden, alinea=alinea, twijfel=twijfel,
                           gekoppeld=gekoppeld, lokaal=lokaal, vorige=vorige, volgende=volgende,
                           positie=(i + 1, len(pids)), merk=merk, status=review_status(w),
                           werk_opties=_werk_opties(pid))


@app.route("/beeld/<batch>/<map_>/<bestand>")
def beeld(batch, map_, bestand):
    pad = os.path.normpath(os.path.join(BEELDEN_DIR, batch, map_, bestand))
    if not pad.startswith(os.path.normpath(BEELDEN_DIR) + os.sep) or not os.path.exists(pad):
        abort(404)
    return send_file(pad, mimetype="image/jpeg", max_age=86400)


PLACEHOLDER = """<svg xmlns='http://www.w3.org/2000/svg' width='240' height='160'>
<rect width='100%' height='100%' fill='#2a2a2e'/><text x='50%' y='50%' fill='#9a9aa2'
font-family='sans-serif' font-size='14' text-anchor='middle' dominant-baseline='middle'>{t}</text></svg>"""


@app.route("/thumb/<pid>/<int:idx>")
def thumb(pid, idx):
    w = werk_map().get(pid) or abort(404)
    if idx >= len(w["media"]):
        abort(404)
    m = w["media"][idx]
    forceer = request.args.get("laad") == "1"
    if m["type"] == "vid":
        return Response(PLACEHOLDER.format(t="▶ video"), mimetype="image/svg+xml")
    if m["cloud"] and not forceer:
        return Response(PLACEHOLDER.format(t="☁ alleen online"), mimetype="image/svg+xml")
    if not local.in_roots(m["pad"], cfg()["roots"]):
        abort(403)
    os.makedirs(THUMB_DIR, exist_ok=True)
    sleutel = hashlib.sha1(f"{m['pad']}|{m['size']}|{m['mtime']}".encode()).hexdigest()
    cache = os.path.join(THUMB_DIR, sleutel + ".jpg")
    if not os.path.exists(cache):
        try:
            with Image.open(m["pad"]) as im:
                im.draft("RGB", (480, 480))
                im = im.convert("RGB")
                im.thumbnail((360, 360))
                im.save(cache, "JPEG", quality=80)
        except Exception:
            return Response(PLACEHOLDER.format(t="kan niet lezen"), mimetype="image/svg+xml")
    return send_file(cache, mimetype="image/jpeg", max_age=86400)


# ---------- captions: bestaande caption ↔ Claude-voorstel ↔ beste versie ----------

def post_beelden():
    """{post_key: [beeld]} uit de manifests (zonder dubbelen)."""
    uit, gezien = {}, set()
    for lijst in beelden_index().values():
        for b in lijst:
            k = b.get("post")
            if k and (k, b["src"]) not in gezien:
                gezien.add((k, b["src"]))
                uit.setdefault(k, []).append(b)
    return uit


def caption_rijen():
    zorg_voor_suggesties()
    lk, wm, data, pb = links(), werk_map(), capt.laad(), post_beelden()
    rijen = []
    for g in STATE["groepen"]:
        pid = next((lk[k]["pid"] for k in g["keys"] if k in lk), None)
        it = capt.zoek(data, g) or {}
        cl = it.get("claude") or {}
        beelden = []
        for k in g["keys"]:
            for b in pb.get(k, []):
                if b["src"] not in {x["src"] for x in beelden}:
                    beelden.append(b)
        rijen.append({"g": g, "w": wm.get(pid), "it": it, "beelden": beelden,
                      "status": it.get("status", ""), "feedback": it.get("feedback", ""),
                      "heeft_claude": bool((cl.get("nl") or "").strip() or (cl.get("en") or "").strip()),
                      "heeft_beste": bool((it.get("beste") or {}).get("nl", "").strip()
                                          or (it.get("beste") or {}).get("en", "").strip())})
    return rijen


CAPTION_FILTERS = {
    "open": lambda r: r["heeft_claude"] and r["status"] not in ("klaar", "overslaan"),
    "nieuw": lambda r: not r["heeft_claude"] and r["status"] != "overslaan",
    "feedback": lambda r: bool(r["feedback"].strip()) and r["status"] != "klaar",
    "concept": lambda r: r["status"] == "concept",
    "klaar": lambda r: r["status"] == "klaar",
    "overslaan": lambda r: r["status"] == "overslaan",
    "geen_caption": lambda r: not r["g"]["captions"],
    "alle": lambda r: True,
}


def _caption_filter(rijen, merk, account, filt):
    kies = CAPTION_FILTERS.get(filt, CAPTION_FILTERS["alle"])
    return [r for r in rijen if (not merk or r["g"]["merk"] == merk)
            and (not account or account in r["g"]["accounts"]) and kies(r)]


@app.route("/captions/posts")
def captions_lijst():
    merk = request.args.get("merk", "")
    account = request.args.get("account", "")
    filt = request.args.get("filter", "open")
    alle = caption_rijen()
    basis = [r for r in alle if (not merk or r["g"]["merk"] == merk) and (not account or account in r["g"]["accounts"])]
    tel = {f: sum(1 for r in basis if k(r)) for f, k in CAPTION_FILTERS.items()}
    rijen = _caption_filter(alle, merk, account, filt)
    accounts = sorted({a for r in alle for a in r["g"]["accounts"]})
    return render_template("captions_lijst.html", rijen=rijen, tel=tel, filt=filt, merk=merk,
                           account=account, accounts=accounts)


@app.route("/captions/post/<path:gid>", methods=["GET", "POST"])
def caption(gid):
    merk = request.args.get("merk", "")
    account = request.args.get("account", "")
    filt = request.args.get("filter", "open")
    alle = caption_rijen()
    r = next((x for x in alle if x["g"]["gid"] == gid or gid in x["g"]["keys"]), None) or abort(404)
    g, w = r["g"], r["w"]
    nav = dict(merk=merk, account=account, filter=filt)
    if request.method == "POST":
        data = capt.laad()
        it = capt.item_voor(data, g)
        it["keys"] = list(g["keys"])
        for taal in ("nl", "en"):
            if f"beste_{taal}" in request.form:
                it["beste"][taal] = request.form[f"beste_{taal}"].replace("\r\n", "\n").strip()
        if "feedback" in request.form:
            it["feedback"] = request.form["feedback"].replace("\r\n", "\n").strip()
        actie = request.form.get("actie", "")
        if actie in capt.STATUSSEN:
            it["status"] = actie
        elif actie == "reset":
            it["status"] = ""
        it["gewijzigd"] = capt.nu()
        capt.bewaar(data)
        melding = actie or "opgeslagen"
        if actie == "naar_werk" and w:
            t = w["tekst"] or textfile.leeg()
            bekend = {textfile.norm(e["tekst"]) for e in t["eerder"]}
            for taal, veld in (("nl", "Caption NL"), ("en", "Caption EN")):
                if it["beste"][taal]:
                    oud = t["velden"].get(veld, "").strip()
                    if oud and textfile.norm(oud) not in bekend and textfile.norm(oud) != textfile.norm(it["beste"][taal]):
                        t["eerder"].append({"kop": f"vorige {veld} · {capt.nu()[:10]}", "tekst": oud})
                    t["velden"][veld] = it["beste"][taal]
            textfile.schrijf(w["pad"], t)
            herlaad_werk(w["pid"])
            melding = f"beste versie gezet als Caption NL/EN van {w['mapnaam']} (oude staat onder Eerdere captions)"
        flash(f"{g['start'][:10]} · {w['mapnaam'] if w else 'zonder werk'}: {melding}")
        if actie in ("klaar", "overslaan"):
            rest = _caption_filter(caption_rijen(), merk, account, filt)
            gids = [x["g"]["gid"] for x in alle]
            i = gids.index(g["gid"]) if g["gid"] in gids else -1
            volg = next((x for x in rest if gids.index(x["g"]["gid"]) > i and x["g"]["gid"] != g["gid"]), None) \
                or next((x for x in rest if x["g"]["gid"] != g["gid"]), None)
            if volg:
                return redirect(url_for("caption", gid=volg["g"]["gid"], **nav))
            flash("Niets meer open in deze lijst 🎉")
            return redirect(url_for("captions_lijst", **nav))
        return redirect(url_for("caption", gid=g["gid"], **nav))

    lijst = _caption_filter(alle, merk, account, filt)
    gids = [x["g"]["gid"] for x in lijst]
    i = gids.index(g["gid"]) if g["gid"] in gids else -1
    vorige = gids[i - 1] if i > 0 else None
    volgende = gids[i + 1] if 0 <= i < len(gids) - 1 else None
    it = r["it"] or {"claude": {}, "beste": {"nl": "", "en": ""}, "feedback": "", "status": ""}
    t = (w["tekst"] if w else None) or textfile.leeg()
    links_cl = capt.crosslinks(t["velden"].get("Crosslinks", ""))
    tags = []
    for c in links_cl:
        for h in c["ig"]:
            if h.lower() not in {x["h"].lower() for x in tags}:
                tags.append({"h": h, "wie": c["partij"], "zek": c["zekerheid"]})
    for h in capt.tags_uit(t["velden"].get("Credits", "")):
        if h.lower() not in {x["h"].lower() for x in tags}:
            tags.append({"h": h, "wie": "credits", "zek": ""})
    eigen = "@lichtjes.nl" if g["merk"] == "Lichtjes" else "@studiojarnoburger"
    andere = "@studiojarnoburger" if eigen == "@lichtjes.nl" else "@lichtjes.nl"
    hashtags = re.findall(r"#\w+", t["velden"].get("Hashtags", ""))
    _, alts, _ = _alt_teksten(t["velden"].get("Beeldbeschrijving", ""))
    plinks = {p["permalink"] for p in g["posts"]}
    alts_post = [a for b, a in alts if any(pl in b for pl in plinks)]
    return render_template("caption.html", r=r, g=g, w=w, it=it, t=t, crosslinks=links_cl, tags=tags,
                           eigen=eigen, andere=andere, hashtags=hashtags, alts_post=alts_post,
                           vorige=vorige, volgende=volgende, positie=(i + 1, len(gids)), nav=nav)


# ---------- captions per werk: Caption NL + EN + Hashtags uit _tekst.md ----------
# Status per werk in de yml: caption_review = klaar | later | overslaan | '' ; caption_notitie = feedback voor Claude.

CW_STATUSSEN = ("klaar", "later", "overslaan")  # overslaan = wordt niet gepost, geen tekst nodig
CW_VELDEN = ("Caption NL", "Caption EN", "Hashtags")
_CW_LOG = {"mtime": None, "claude": set()}


def _claude_geschreven():
    """Werkmappen waarvan Claude de Caption NL schreef (uit data/teksten-log-*.json met doe=true)."""
    import glob as _glob
    logs = sorted(_glob.glob(os.path.join(config.DATA_DIR, "teksten-log-*.json")))
    sleutel = tuple(os.path.getmtime(p) for p in logs)
    if _CW_LOG["mtime"] != sleutel:
        s = set()
        for p in logs:
            d = config.load_json(p, {})
            if d.get("doe"):
                s |= {os.path.normcase(l["pad"]).rsplit(os.sep, 1)[0] for l in d.get("log", [])
                      if "Caption NL" in l.get("velden", [])}
        _CW_LOG.update(mtime=sleutel, claude=s)
    return _CW_LOG["claude"]


def _cw_rij(w, bidx, claude):
    v = (w["tekst"] or textfile.leeg())["velden"]
    beelden = bidx.get(w["pid"]) or bidx.get("naam:" + w["mapnaam"].lower()) or []
    return {"w": w, "nl": v.get("Caption NL", "").strip(), "en": v.get("Caption EN", "").strip(),
            "hashtags": v.get("Hashtags", "").strip(), "status": (w["yml"].get("caption_review") or "").strip(),
            "notitie": (w["yml"].get("caption_notitie") or "").strip(),
            "claude": os.path.normcase(w["pad"]) in claude, "beeld": beelden[0] if beelden else None}


CW_FILTERS = {
    "open": lambda r: r["nl"] and r["status"] not in CW_STATUSSEN,
    "claude": lambda r: r["claude"] and r["status"] not in CW_STATUSSEN,
    "notitie": lambda r: bool(r["notitie"]) and r["status"] not in ("klaar", "overslaan"),
    "later": lambda r: r["status"] == "later",
    "klaar": lambda r: r["status"] == "klaar",
    "geen_nl": lambda r: not r["nl"] and r["status"] != "overslaan",
    "geen_en": lambda r: r["nl"] and not r["en"] and r["status"] != "overslaan",
    "overslaan": lambda r: r["status"] == "overslaan",
    "alle": lambda r: True,
}


def _cw_lijst(merk):
    bidx, claude = beelden_index(), _claude_geschreven()
    rijen = [_cw_rij(w, bidx, claude) for w in werken() if not w["los"] and (not merk or w["merk"] == merk)]
    return sorted(rijen, key=lambda r: (r["w"]["jaar"] or "9999", r["w"]["mapnaam"].lower()))


@app.route("/captions")
def captions_werken():
    merk = request.args.get("merk", "")
    filt = request.args.get("filter", "open")
    alle = _cw_lijst(merk)
    tel = {f: sum(1 for r in alle if k(r)) for f, k in CW_FILTERS.items()}
    rijen = [r for r in alle if CW_FILTERS.get(filt, CW_FILTERS["alle"])(r)]
    return render_template("captions_werken.html", rijen=rijen, tel=tel, filt=filt, merk=merk)


@app.route("/captions/werk/<pid>", methods=["GET", "POST"])
def caption_werk(pid):
    w = werk_map().get(pid) or abort(404)
    merk = request.args.get("merk", "")
    filt = request.args.get("filter", "open")
    nav = dict(merk=merk, filter=filt)
    if request.method == "POST":
        # altijd vers van schijf lezen, zodat andere velden (en wijzigingen buiten de app) blijven staan
        data = textfile.lees(w["pad"]) or textfile.leeg()
        for veld in CW_VELDEN:
            k = "veld_" + veld.replace(" ", "_")
            if k in request.form:
                data["velden"][veld] = request.form[k].replace("\r\n", "\n").strip()
        textfile.schrijf(w["pad"], data)
        actie = request.form.get("actie", "")
        if actie in CW_STATUSSEN or actie == "reset":
            waarde = "" if actie == "reset" else actie
            local.zet_yml(w["pad"], "caption_review", waarde)
            w["yml"]["caption_review"] = waarde
        notitie = request.form.get("notitie", "").replace("\r\n", " ").replace("\n", " ").strip()
        if notitie != (w["yml"].get("caption_notitie") or ""):
            local.zet_yml(w["pad"], "caption_notitie", notitie)
            w["yml"]["caption_notitie"] = notitie
        herlaad_werk(pid)
        flash(f"{w['mapnaam']}: {actie or 'opgeslagen'}")
        if actie in CW_STATUSSEN:
            lijst = [r for r in _cw_lijst(merk) if CW_FILTERS.get(filt, CW_FILTERS["alle"])(r)]
            pids = [r["w"]["pid"] for r in _cw_lijst(merk)]
            i = pids.index(pid) if pid in pids else -1
            volg = next((r for r in lijst if pids.index(r["w"]["pid"]) > i), None) or next(iter(lijst), None)
            if volg and volg["w"]["pid"] != pid:
                return redirect(url_for("caption_werk", pid=volg["w"]["pid"], **nav))
            flash("Niets meer open in deze lijst 🎉")
            return redirect(url_for("captions_werken", **nav))
        return redirect(url_for("caption_werk", pid=pid, **nav))

    bidx = beelden_index()
    t = textfile.lees(w["pad"]) or textfile.leeg()
    beelden = [url_for("beeld", batch=b["src"].split("/")[0], map_=b["src"].split("/")[1], bestand=b["bestand"])
               for b in (bidx.get(pid) or bidx.get("naam:" + w["mapnaam"].lower()) or [])]
    if not beelden:
        beelden = [url_for("thumb", pid=pid, idx=i) for i, m in enumerate(w["media"])
                   if m["type"] == "img" and not m["cloud"]][:8]
    links_cl = capt.crosslinks(t["velden"].get("Crosslinks", ""))
    tags = []
    for c in links_cl:
        for h in c["ig"]:
            if h.lower() not in {x["h"].lower() for x in tags}:
                tags.append({"h": h, "wie": c["partij"], "zek": c["zekerheid"]})
    for h in capt.tags_uit(t["velden"].get("Credits", "")):
        if h.lower() not in {x["h"].lower() for x in tags}:
            tags.append({"h": h, "wie": "credits", "zek": ""})
    eigen = "@lichtjes.nl" if w["merk"] == "Lichtjes" else "@studiojarnoburger"
    andere = "@studiojarnoburger" if eigen == "@lichtjes.nl" else "@lichtjes.nl"
    per_key = {p["key"]: p for p in online()["posts"]}
    gekoppeld = sorted((per_key[k] for k in links_per_werk().get(pid, []) if k in per_key),
                       key=lambda p: p["timestamp"])
    alinea, _, twijfel = _alt_teksten(t["velden"].get("Beeldbeschrijving", ""))
    lijst = [r for r in _cw_lijst(merk) if CW_FILTERS.get(filt, CW_FILTERS["alle"])(r)]
    pids = [r["w"]["pid"] for r in lijst]
    i = pids.index(pid) if pid in pids else -1
    vorige = pids[i - 1] if i > 0 else None
    volgende = pids[i + 1] if 0 <= i < len(pids) - 1 else None
    return render_template("caption_werk.html", w=w, t=t, beelden=beelden, tags=tags, eigen=eigen,
                           andere=andere, crosslinks=links_cl, gekoppeld=gekoppeld, alinea=alinea,
                           twijfel=twijfel, status=(w["yml"].get("caption_review") or ""),
                           notitie=(w["yml"].get("caption_notitie") or ""),
                           claude=os.path.normcase(w["pad"]) in _claude_geschreven(),
                           vorige=vorige, volgende=volgende, positie=(i + 1, len(pids)), nav=nav)


# ---------- verplaats-markeringen (vanuit Review) ----------
# Alleen MARKEREN: data/verplaats.json = {item_id: {van, van_map, naar, naar_map, nieuw, op}}.
# Uitvoeren (post herkoppelen / bestand verplaatsen) gebeurt later met een tool, met proefrun.
VERPLAATS_PATH = os.path.join(config.DATA_DIR, "verplaats.json")


def verplaatsingen():
    return config.load_json(VERPLAATS_PATH, {})


def item_id(pid, b):
    """Een opgehaald beeld hoort bij een post (post verhuist in z'n geheel); anders een lokaal bestand."""
    if b.get("post"):
        return "post:" + b["post"]
    return f"lokaal:{pid}:{b.get('lokaal') or b.get('bestand', '')}"


def _werk_label(w):
    return f"{w['mapnaam']} · {w['merk']}"


def _werk_opties(behalve=None):
    return sorted((_werk_label(w) for w in werken() if w["pid"] != behalve), key=str.lower)


def _verwerk_verplaats(w, form):
    """Leest velden 'verpl::<item_id>' (tekst: '<map> · <merk>' of een nieuwe naam). Leeg = markering weg."""
    v = verplaatsingen()
    per_label = {_werk_label(x): x for x in werken()}
    n = 0
    for k in form:
        if not k.startswith("verpl::"):
            continue
        iid, waarde = k[len("verpl::"):], form.get(k, "").strip()
        oud = v.get(iid)
        if not waarde:
            if oud:
                del v[iid]
                n += 1
            continue
        doel = per_label.get(waarde)
        if doel and doel["pid"] == w["pid"]:
            if oud:
                del v[iid]
                n += 1
            continue
        rec = {"van": w["pid"], "van_map": w["mapnaam"],
               "naar": doel["pid"] if doel else "", "naar_map": doel["mapnaam"] if doel else waarde,
               "nieuw": not doel, "merk": doel["merk"] if doel else w["merk"],
               "op": dt.datetime.now().isoformat(timespec="seconds")}
        if not oud or (oud.get("naar"), oud.get("naar_map")) != (rec["naar"], rec["naar_map"]):
            v[iid] = rec
            n += 1
    if n:
        config.save_json(VERPLAATS_PATH, v)
    return n


@app.route("/review/verplaats")
def verplaats_lijst():
    v = verplaatsingen()
    wm = werk_map()
    rijen = sorted(({"iid": k, **r, "van_ok": r["van"] in wm, "naar_ok": (not r["naar"]) or r["naar"] in wm}
                    for k, r in v.items()), key=lambda r: (r["van_map"].lower(), r["iid"]))
    return render_template("verplaats_lijst.html", rijen=rijen)


# ---------- mogelijk dubbele werken ----------
# Kandidaten: data/dubbel_kandidaten.json (door Claude samengesteld).
# Besluiten: data/dubbel_besluit.json = {groep_id: {besluit: samen|niet|twijfel, doel: pid, notitie, op}}.
DUBBEL_KAND_PATH = os.path.join(config.DATA_DIR, "dubbel_kandidaten.json")
DUBBEL_BESLUIT_PATH = os.path.join(config.DATA_DIR, "dubbel_besluit.json")


def _werk_beelden(w, bidx, n=6):
    bl = [url_for("beeld", batch=b["src"].split("/")[0], map_=b["src"].split("/")[1], bestand=b["bestand"])
          for b in (bidx.get(w["pid"]) or bidx.get("naam:" + w["mapnaam"].lower()) or [])]
    if not bl:
        bl = [url_for("thumb", pid=w["pid"], idx=i) for i, m in enumerate(w["media"])
              if m["type"] == "img" and not m["cloud"]]
    return bl[:n]


@app.route("/dubbel", methods=["GET", "POST"])
def dubbel():
    filt = request.args.get("filter", "open")
    bes = config.load_json(DUBBEL_BESLUIT_PATH, {})
    if request.method == "POST":
        gid, actie = request.form.get("gid", ""), request.form.get("actie", "")
        if actie == "reset":
            bes.pop(gid, None)
        elif actie in ("samen", "niet", "twijfel"):
            bes[gid] = {"besluit": actie, "doel": request.form.get("doel", "") if actie == "samen" else "",
                        "notitie": request.form.get("notitie", "").strip(),
                        "op": dt.datetime.now().isoformat(timespec="seconds")}
        config.save_json(DUBBEL_BESLUIT_PATH, bes)
        flash(f"{gid}: {actie}")
        return redirect(url_for("dubbel", filter=filt) + f"#{gid}")
    wm, bidx, lpw = werk_map(), beelden_index(), links_per_werk()
    groepen = []
    for g in config.load_json(DUBBEL_KAND_PATH, []):
        leden = [{"w": wm[p], "beelden": _werk_beelden(wm[p], bidx), "n_posts": len(lpw.get(p, []))}
                 for p in g["pids"] if p in wm]
        if len(leden) < 2:
            continue
        groepen.append({"id": g["id"], "reden": g["reden"], "leden": leden, "besluit": bes.get(g["id"])})
    tel = {"open": sum(1 for g in groepen if not g["besluit"]), "alle": len(groepen),
           "beslist": sum(1 for g in groepen if g["besluit"])}
    if filt == "open":
        groepen = [g for g in groepen if not g["besluit"]]
    elif filt == "beslist":
        groepen = [g for g in groepen if g["besluit"]]
    return render_template("dubbel.html", groepen=groepen, tel=tel, filt=filt)


# ---------- publiceer: per bestaande post de nieuwe tekst klaarzetten, Jarno plakt zelf ----------
PUBLICEER_PATH = os.path.join(config.DATA_DIR, "publiceer.json")
FB_NAMEN_PATH = os.path.join(config.DATA_DIR, "fb_namen.json")  # {"@handle": "Naam op FB"}
_HANDLE = re.compile(r"(?<![\w.])@([A-Za-z0-9_.]*[A-Za-z0-9_])")


def _fb_tekst(tekst, naam_bij_handle):
    """FB-variant: @handle -> naam van de partij (uit Crosslinks), anders handle zonder @."""
    return _HANDLE.sub(lambda m: naam_bij_handle.get("@" + m.group(1).lower(), m.group(1)), tekst)


def _publiceer_rijen():
    gedaan = config.load_json(PUBLICEER_PATH, {})
    per_key = {p["key"]: p for p in online()["posts"]}
    wm, lpw = werk_map(), links_per_werk()
    # handle -> naam: eerst uit alle Crosslinks, daarna handmatige lijst data/fb_namen.json (wint)
    globaal = {}
    for w_ in wm.values():
        for c in capt.crosslinks(((w_["tekst"] or textfile.leeg())["velden"]).get("Crosslinks", "")):
            for h in c["ig"]:
                globaal.setdefault(h.lower(), c["partij"])
    handmatig = {k.lower(): v for k, v in config.load_json(FB_NAMEN_PATH, {}).items()}
    globaal.update(handmatig)
    rijen = []
    for pid, keys in lpw.items():
        w = wm.get(pid)
        if not w:
            continue
        status = (w["yml"].get("caption_review") or "").strip()
        v = (w["tekst"] or textfile.leeg())["velden"]
        nl, en, ht = (v.get("Caption NL", "").strip(), v.get("Caption EN", "").strip(),
                      v.get("Hashtags", "").strip())
        if status == "overslaan" or not en:
            continue
        naam_bij = dict(globaal)
        for c in capt.crosslinks(v.get("Crosslinks", "")):
            for h in c["ig"]:
                if h.lower() not in handmatig:
                    naam_bij[h.lower()] = c["partij"]
        for k in keys:
            p = per_key.get(k)
            if not p:
                continue
            delen = [en, " ".join(re.findall(r"#\w+", ht))]  # alleen Engels (keuze Jarno 04-10)
            tekst = "\n\n".join(d for d in delen if d)
            if p["platform"] == "fb":
                tekst = _fb_tekst(tekst, naam_bij)
            thumbs = p.get("thumbs") or []
            if isinstance(thumbs, str):
                thumbs = re.findall(r"https?://[^'\"\s,\]]+", thumbs)
            rijen.append({"p": p, "w": w, "status": status, "tekst": tekst, "oud": (p.get("caption") or "").strip(),
                          "thumb": thumbs[0] if thumbs else "", "gedaan": gedaan.get(k, {}).get("op", ""),
                          "zelfde": textfile.norm(p.get("caption") or "") == textfile.norm(tekst)})
    return sorted(rijen, key=lambda r: (r["w"]["jaar"] or "9999", r["w"]["mapnaam"].lower(), r["p"]["timestamp"]))


@app.route("/publiceer", methods=["GET", "POST"])
def publiceer():
    if request.method == "POST":
        gedaan = config.load_json(PUBLICEER_PATH, {})
        key, aan = request.form.get("key", ""), request.form.get("gedaan") == "1"
        if aan:
            gedaan[key] = {"op": dt.datetime.now().isoformat(timespec="seconds")}
        else:
            gedaan.pop(key, None)
        config.save_json(PUBLICEER_PATH, gedaan)
        return {"ok": True, "key": key, "gedaan": aan, "n": len(gedaan)}
    stap = request.args.get("stap") or _eerste_open_stap()
    return redirect(_stap_start(stap, request.args.get("filter", "open")))


# volgorde gekozen door Jarno 04-10: SJB IG -> SJB FB -> Lichtjes IG -> Lichtjes FB
PUBLICEER_STAPPEN = [("sjb-ig", "SJB · Instagram", "SJB", "ig"), ("sjb-fb", "SJB · Facebook", "SJB", "fb"),
                     ("lichtjes-ig", "Lichtjes · Instagram", "Lichtjes", "ig"),
                     ("lichtjes-fb", "Lichtjes · Facebook", "Lichtjes", "fb")]


def _publiceer_werken(stap):
    """Per werk de posts van een stap (merk van het account + platform), alleen captions 'klaar'."""
    _, _, merk, pf = next(s for s in PUBLICEER_STAPPEN if s[0] == stap)
    per = {}
    for r in _publiceer_rijen():
        if r["status"] != "klaar" or r["p"]["platform"] != pf or r["p"]["merk"] != merk:
            continue
        x = per.setdefault(r["w"]["pid"], {"pid": r["w"]["pid"], "w": r["w"], "posts": [], "tekst": r["tekst"],
                                           "thumbs": []})
        x["posts"].append(r)
        if r["thumb"] and len(x["thumbs"]) < 4:
            x["thumbs"].append(r["thumb"])
    for x in per.values():
        x["open"] = any(not r["gedaan"] for r in x["posts"])
    return list(per.values())


def _stappen_tel():
    uit = []
    for sid, naam, _, _ in PUBLICEER_STAPPEN:
        ws = _publiceer_werken(sid)
        posts = [r for x in ws for r in x["posts"]]
        uit.append({"id": sid, "naam": naam, "werken": len(ws), "posts": len(posts),
                    "open": sum(1 for r in posts if not r["gedaan"]),
                    "eerste_open": next((x["pid"] for x in ws if x["open"]), None),
                    "eerste": ws[0]["pid"] if ws else None})
    return uit


def _eerste_open_stap():
    return next((s["id"] for s in _stappen_tel() if s["open"]), PUBLICEER_STAPPEN[0][0])


def _stap_start(stap, filt):
    s = next((t for t in _stappen_tel() if t["id"] == stap), None)
    pid = s and (s["eerste_open"] if filt == "open" else s["eerste"]) or (s and s["eerste"])
    if not pid:
        flash(f"{s['naam'] if s else stap}: niets te doen")
        return url_for("publiceer_leeg")
    return url_for("publiceer_werk", stap=stap, pid=pid, filter=filt)


@app.route("/publiceer/klaar")
def publiceer_leeg():
    return render_template("publiceer.html", x=None, stappen=_stappen_tel(), stap="", filt="open")


@app.route("/publiceer/<stap>/<pid>")
def publiceer_werk(stap, pid):
    if stap not in {s[0] for s in PUBLICEER_STAPPEN}:
        abort(404)
    filt = request.args.get("filter", "open")
    werken_ = _publiceer_werken(stap)
    x = next((w_ for w_ in werken_ if w_["pid"] == pid), None)
    if not x:
        return redirect(_stap_start(stap, filt))
    i = [w_["pid"] for w_ in werken_].index(pid)
    zichtbaar = lambda w_: filt == "alle" or w_["open"] or w_["pid"] == pid
    lijst = [w_ for w_ in werken_ if zichtbaar(w_)]
    vorige = next((w_["pid"] for w_ in reversed(werken_[:i]) if zichtbaar(w_)), None)
    volgende = next((w_["pid"] for w_ in werken_[i + 1:] if zichtbaar(w_)), None)
    ids = [s[0] for s in PUBLICEER_STAPPEN]
    volgende_stap = ids[ids.index(stap) + 1] if ids.index(stap) + 1 < len(ids) else None
    stap_naam = next(s[1] for s in PUBLICEER_STAPPEN if s[0] == stap)
    return render_template("publiceer.html", x=x, stap=stap, stap_naam=stap_naam, filt=filt,
                           positie=([w_["pid"] for w_ in lijst].index(pid) + 1, len(lijst)),
                           vorige=vorige, volgende=volgende, volgende_stap=volgende_stap,
                           stappen=_stappen_tel(), platform=stap.split("-")[1])


# ---------- plannen (swipe per werk) + planning (4 sleepbare lijsten) ----------
PLAN_PATH = os.path.join(config.DATA_DIR, "plan.json")          # {pid: {doelen:[..], niet:bool, klaar:ts}}
PLANNING_PATH = os.path.join(config.DATA_DIR, "planning.json")  # {doel: {"volgorde":[pid..], "gepost":{pid: ts}}}
DOELEN = [("ig-sjb", "Insta SJB", "ig", "@studiojarnoburger"), ("ig-lichtjes", "Insta Lichtjes", "ig", "@lichtjes.nl"),
          ("fb-sjb", "FB SJB", "fb", "Studio Jarno Burger"), ("fb-lichtjes", "FB Lichtjes", "fb", "Lichtjes")]
DOEL_BIJ_ACCOUNT = {(pf, acc): d for d, _, pf, acc in DOELEN}


def _naam_map():
    m = {}
    for w_ in werk_map().values():
        for c in capt.crosslinks(((w_["tekst"] or textfile.leeg())["velden"]).get("Crosslinks", "")):
            for h in c["ig"]:
                m.setdefault(h.lower(), c["partij"])
    m.update({k.lower(): v for k, v in config.load_json(FB_NAMEN_PATH, {}).items()})
    return m


def _plan_werken():
    """Werken (niet _Los), oud -> nieuw; werken die op beide eigen plekken al gepost zijn vallen weg (keuze Jarno 06-10)."""
    per_key, lpw = {p["key"]: p for p in online()["posts"]}, links_per_werk()
    uit = []
    for w in werken():
        if w["los"] or os.sep + "_Promoted" + os.sep in w["pad"]:  # _Promoted = afgerond
            continue
        g = _gepost_per_doel(w["pid"], per_key, lpw)
        if all(g[d] for d, *_ in _eigen_doelen(w)):
            continue
        uit.append(w)
    return sorted(uit, key=lambda w: (w["jaar"] or "9999", w["mapnaam"].lower()))


def _gepost_per_doel(pid, per_key, lpw):
    uit = {d: [] for d, *_ in DOELEN}
    for k in lpw.get(pid, []):
        p = per_key.get(k)
        d = p and DOEL_BIJ_ACCOUNT.get((p["platform"], p["account"]))
        if d:
            uit[d].append(p)
    for d in uit:
        uit[d].sort(key=lambda p: p["timestamp"])
    return uit


def _post_tekst(w, doel, naam_map=None):
    v = (w["tekst"] or textfile.leeg())["velden"]
    tekst = "\n\n".join(d for d in (v.get("Caption EN", "").strip(),
                                    " ".join(re.findall(r"#\w+", v.get("Hashtags", "")))) if d)
    if doel.startswith("fb"):
        tekst = _fb_tekst(tekst, naam_map if naam_map is not None else _naam_map())
    return tekst


def _eigen_doelen(w):
    """SJB-werk -> alleen Insta SJB + FB SJB; Lichtjes-werk -> alleen Insta + FB Lichtjes (keuze Jarno 06-10)."""
    sleutel = "lichtjes" if w["merk"] == "Lichtjes" else "sjb"
    return [d for d in DOELEN if d[0].endswith("-" + sleutel)]


def _plan_open(w, plan):
    return w["pid"] not in plan or not plan[w["pid"]].get("klaar")


@app.route("/plannen")
def plannen():
    filt = request.args.get("filter", "open")
    plan = config.load_json(PLAN_PATH, {})
    lijst = [w for w in _plan_werken() if filt == "alle" or _plan_open(w, plan)]
    if not lijst:
        flash("Alle werken zijn beoordeeld 🎉 — door naar Planning")
        return redirect(url_for("planning"))
    return redirect(url_for("plan_werk", pid=lijst[0]["pid"], filter=filt))


@app.route("/plannen/<pid>", methods=["GET", "POST"])
def plan_werk(pid):
    w = werk_map().get(pid) or abort(404)
    filt = request.args.get("filter", "open")
    plan = config.load_json(PLAN_PATH, {})
    alle = _plan_werken()
    pids = [x["pid"] for x in alle]
    if pid not in pids:  # al op beide eigen plekken gepost
        flash(f"{w['mapnaam']} staat al op beide plekken van {w['merk']}")
        return redirect(url_for("plannen", filter=filt))
    i = pids.index(pid)
    zichtbaar = lambda x: filt == "alle" or _plan_open(x, plan) or x["pid"] == pid
    vorige = next((x["pid"] for x in reversed(alle[:i]) if zichtbaar(x)), None)
    volgende = next((x["pid"] for x in alle[i + 1:] if zichtbaar(x)), None)

    if request.method == "POST":
        data = textfile.lees(w["pad"]) or textfile.leeg()
        gewijzigd = False
        for veld, k in (("Caption EN", "caption_en"), ("Hashtags", "hashtags")):
            if k in request.form:
                nieuw = request.form[k].replace("\r\n", "\n").strip()
                if nieuw != data["velden"].get(veld, "").strip():
                    data["velden"][veld] = nieuw
                    gewijzigd = True
        if gewijzigd:
            textfile.schrijf(w["pad"], data)
            herlaad_werk(pid)
        actie = request.form.get("actie", "opslaan")
        niet = request.form.get("niet") == "1"
        it = plan.get(pid, {})
        it["doelen"] = [] if niet else [d for d, *_ in _eigen_doelen(w) if request.form.get("doel_" + d) == "1"]
        it["niet"] = niet
        if actie == "klaar":
            it["klaar"] = dt.datetime.now().isoformat(timespec="seconds")
        elif actie == "heropen":
            it.pop("klaar", None)
        plan[pid] = it
        config.save_json(PLAN_PATH, plan)
        flash(f"{w['mapnaam']}: {'klaar' if actie == 'klaar' else 'opgeslagen'}"
              f"{' · tekst bijgewerkt' if gewijzigd else ''}")
        if actie == "klaar":
            if volgende:
                return redirect(url_for("plan_werk", pid=volgende, filter=filt))
            return redirect(url_for("plannen", filter=filt))
        if actie in ("volgende", "vorige"):
            doel = volgende if actie == "volgende" else vorige
            if doel:
                return redirect(url_for("plan_werk", pid=doel, filter=filt))
        return redirect(url_for("plan_werk", pid=pid, filter=filt))

    per_key = {p["key"]: p for p in online()["posts"]}
    gepost = _gepost_per_doel(pid, per_key, links_per_werk())
    it = plan.get(pid)
    eigen = _eigen_doelen(w)
    if it is None:  # voorstel: eigen merk, waar nog niets staat
        it = {"doelen": [d for d, *_ in eigen if not gepost[d]], "niet": False, "voorstel": True}
    ander_merk = [p for d, *_ in DOELEN if d not in {e[0] for e in eigen} for p in gepost[d]]
    v = (w["tekst"] or textfile.leeg())["velden"]
    lijst = [x for x in alle if zichtbaar(x)]
    tel = {"open": sum(1 for x in alle if _plan_open(x, plan)), "alle": len(alle)}
    return render_template("plan.html", w=w, it=it, gepost=gepost, doelen=eigen, ander_merk=ander_merk, filt=filt,
                           beelden=_werk_beelden(w, beelden_index(), n=12),
                           caption_en=v.get("Caption EN", ""), hashtags=v.get("Hashtags", ""),
                           caption_nl=v.get("Caption NL", ""), status=(w["yml"].get("caption_review") or ""),
                           vorige=vorige, volgende=volgende, tel=tel,
                           positie=([x["pid"] for x in lijst].index(pid) + 1, len(lijst)))


@app.route("/planning", methods=["GET", "POST"])
def planning():
    pl = config.load_json(PLANNING_PATH, {})
    if request.method == "POST":
        d = request.get_json(force=True)
        doel = d.get("doel")
        if doel not in {x[0] for x in DOELEN}:
            abort(400)
        blok = pl.setdefault(doel, {"volgorde": [], "gepost": {}})
        if "volgorde" in d:
            blok["volgorde"] = list(d["volgorde"])
        if "gepost" in d:
            pid, aan = d["gepost"], d.get("aan", True)
            if aan:
                blok["gepost"][pid] = dt.datetime.now().isoformat(timespec="seconds")
            else:
                blok["gepost"].pop(pid, None)
        config.save_json(PLANNING_PATH, pl)
        uit = {"ok": True}
        if "gepost" in d:
            uit.update(_auto_promoted(d["gepost"]))
        return uit
    plan, wm, bidx, nm = config.load_json(PLAN_PATH, {}), werk_map(), beelden_index(), _naam_map()
    kolommen = []
    for doel, naam, pf, acc in DOELEN:
        blok = pl.get(doel, {"volgorde": [], "gepost": {}})
        kandidaten = [p for p, it in plan.items() if it.get("klaar") and not it.get("niet")
                      and doel in it.get("doelen", []) and p in wm
                      and doel in {e[0] for e in _eigen_doelen(wm[p])}]
        volg = [p for p in blok["volgorde"] if p in kandidaten]
        volg += sorted((p for p in kandidaten if p not in volg),
                       key=lambda p: (wm[p]["jaar"] or "9999", wm[p]["mapnaam"].lower()))
        items = [{"w": wm[p], "tekst": _post_tekst(wm[p], doel, nm), "beelden": _werk_beelden(wm[p], bidx, n=10),
                  "gepost": blok["gepost"].get(p, "")} for p in volg]
        kolommen.append({"doel": doel, "naam": naam, "items": items,
                         "open": sum(1 for x in items if not x["gepost"])})
    actief = request.args.get("doel") or next((k["doel"] for k in kolommen if k["open"]), DOELEN[0][0])
    return render_template("planning.html", kolommen=kolommen, actief=actief)


# ---------- automatisch naar _Promoted zodra alle geplande plekken gepost zijn (keuze Jarno 06-10) ----------
PID_BESTANDEN = ["links.json", "plan.json", "planning.json", "publiceer.json", "beelden_batch1.json",
                 "beelden_batch2.json", "context_alle.json", "online_research.json", "verplaats.json",
                 "dubbel_besluit.json", "dubbel_kandidaten.json", "hashes.json", "personen_fb.json"]
PROMOTED_LOG = os.path.join(config.DATA_DIR, "promoted-auto-log.json")


def _verhuis_werk(w, naar_promoted=True):
    """Verplaatst de werkmap tussen _To Promote en _Promoted; pid en paden in alle data-bestanden mee.
    Geeft nieuw pid terug (of None bij fout)."""
    van, naar = ("_To Promote", "_Promoted") if naar_promoted else ("_Promoted", "_To Promote")
    bron = w["pad"]
    if os.sep + van + os.sep not in bron:
        return None
    doel = bron.replace(os.sep + van + os.sep, os.sep + naar + os.sep, 1)
    if os.path.exists(doel):
        raise OSError(f"bestaat al: {doel}")
    os.makedirs(os.path.dirname(doel), exist_ok=True)
    for poging in range(3):
        try:
            os.rename(bron, doel)
            break
        except OSError:
            if poging == 2:
                raise
            time.sleep(2)  # OneDrive-lock
    oud, nieuw = w["pid"], local.pid_voor(doel)
    lk = links()
    for v in lk.values():
        if v.get("pid") == oud:
            v["pid"], v["pad"] = nieuw, doel
    config.save_json(config.LINKS_PATH, lk)
    bestanden = [os.path.join(config.DATA_DIR, f) for f in PID_BESTANDEN if f != "links.json"]
    bestanden += glob.glob(os.path.join(config.DATA_DIR, "beelden", "*", "manifest.json"))
    for f in bestanden:
        if not os.path.exists(f):
            continue
        t = open(f, encoding="utf-8").read()
        t2 = t.replace(oud, nieuw).replace(json.dumps(bron)[1:-1], json.dumps(doel)[1:-1])
        if t2 != t:
            json.loads(t2)
            open(f, "w", encoding="utf-8").write(t2)
    root = next((r for r in cfg()["roots"] if os.path.normcase(doel).startswith(os.path.normcase(r["pad"]) + os.sep)), None)
    nw = local._werk(doel, w["merk"], root["pad"] if root else os.path.dirname(doel))
    lijst = STATE["werken"] or []
    for i, x in enumerate(lijst):
        if x["pid"] == oud:
            lijst[i] = nw
    log = config.load_json(PROMOTED_LOG, [])
    log.append({"op": dt.datetime.now().isoformat(timespec="seconds"), "map": w["mapnaam"], "van": bron,
                "naar": doel, "pid_oud": oud, "pid_nieuw": nieuw})
    config.save_json(PROMOTED_LOG, log)
    return nieuw


def _auto_promoted(pid):
    """Na (on)gepost-markering: alle geplande doelen gepost -> naar _Promoted; anders terug naar _To Promote."""
    w = werk_map().get(pid)
    it = config.load_json(PLAN_PATH, {}).get(pid, {})
    if not w or not it.get("doelen"):
        return {}
    pl = config.load_json(PLANNING_PATH, {})
    alles = all(pid in pl.get(d, {}).get("gepost", {}) for d in it["doelen"])
    in_promoted = os.sep + "_Promoted" + os.sep in w["pad"]
    try:
        if alles and not in_promoted:
            return {"pid": _verhuis_werk(w, True), "verplaatst": "_Promoted"}
        if not alles and in_promoted:
            return {"pid": _verhuis_werk(w, False), "verplaatst": "_To Promote"}
    except OSError as e:
        return {"fout": f"verplaatsen mislukt: {e}"}
    return {}


# ---------- 3 · Publiceer (nieuwe posts): per doel in planningsvolgorde alles om de post te maken ----------
def _planning_lijst(doel):
    """[pid] in de volgorde van de Planning-tab voor dit doel + dict gepost."""
    pl = config.load_json(PLANNING_PATH, {}).get(doel, {"volgorde": [], "gepost": {}})
    plan, wm = config.load_json(PLAN_PATH, {}), werk_map()
    kand = [p for p, it in plan.items() if it.get("klaar") and not it.get("niet") and doel in it.get("doelen", [])
            and p in wm and doel in {e[0] for e in _eigen_doelen(wm[p])}]
    volg = [p for p in pl.get("volgorde", []) if p in kand]
    volg += sorted((p for p in kand if p not in volg), key=lambda p: (wm[p]["jaar"] or "9999", wm[p]["mapnaam"].lower()))
    return volg, pl.get("gepost", {})


def _post_beelden(w):
    """Beelden in vaste volgorde met alt-tekst (uit Beeldbeschrijving) en link naar het origineel (als lokaal)."""
    _, alts, _ = _alt_teksten(((w["tekst"] or textfile.leeg())["velden"]).get("Beeldbeschrijving", ""))
    uit = []
    for b in beelden_index().get(w["pid"]) or beelden_index().get("naam:" + w["mapnaam"].lower()) or []:
        src = b["src"].split("/")
        alt = next((a for bron, a in alts if (b.get("lokaal") and bron == "lokaal " + b["lokaal"])
                    or (b.get("permalink") and b["permalink"] in bron)), "")
        orig = None
        if b.get("lokaal"):
            m = next((m for m in w["media"] if m["rel"] == b["lokaal"] or m["naam"] == b["lokaal"]), None)
            if m:
                orig = url_for("origineel", pid=w["pid"], rel=m["rel"])
        uit.append({"url": url_for("beeld", batch=src[0], map_=src[1], bestand=b["bestand"]), "alt": alt,
                    "origineel": orig, "naam": b.get("lokaal") or b.get("permalink", ""), "type": b.get("type", "")})
    if not uit:
        uit = [{"url": u, "alt": "", "origineel": None, "naam": "", "type": "foto"} for u in _werk_beelden(w, beelden_index())]
    # nieuwe post met nieuw materiaal: gekozen nieuwe bestanden eerst (in gekozen volgorde)
    gekozen = config.load_json(PLAN_PATH, {}).get(w["pid"], {}).get("beelden") or []
    if gekozen:
        nieuw = []
        for b in gekozen:
            if os.path.exists(os.path.join(w["pad"], b)):
                u = url_for("origineel", pid=w["pid"], rel=b)
                nieuw.append({"url": u, "alt": "", "origineel": u, "naam": b, "nieuw": True,
                              "type": "video" if os.path.splitext(b)[1].lower() in VID_EXT else "foto"})
        uit = nieuw + [{**x, "nieuw": False} for x in uit]
    return uit


@app.route("/origineel/<pid>/<path:rel>")
def origineel(pid, rel):
    w = werk_map().get(pid) or abort(404)
    pad = os.path.normpath(os.path.join(w["pad"], rel))
    if not pad.startswith(os.path.normpath(w["pad"]) + os.sep) or not os.path.exists(pad):
        abort(404)
    return send_file(pad, as_attachment=request.args.get("dl") == "1")


@app.route("/actie/open_map/<pid>", methods=["POST"])
def actie_open_map(pid):
    w = werk_map().get(pid) or abort(404)
    try:
        os.startfile(w["pad"])  # Windows Verkenner
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "fout": str(e)}, 500


@app.route("/posten")
def posten():
    doel = request.args.get("doel")
    if doel not in {d[0] for d in DOELEN}:
        doel = next((d for d, *_ in DOELEN if any(p not in _planning_lijst(d)[1] for p in _planning_lijst(d)[0])),
                    DOELEN[0][0])
    volg, gepost = _planning_lijst(doel)
    pid = next((p for p in volg if p not in gepost), volg[0] if volg else None)
    if not pid:
        flash(f"Niets gepland voor {dict((d, n) for d, n, *_ in DOELEN)[doel]}")
        return redirect(url_for("planning", doel=doel))
    return redirect(url_for("post_werk", doel=doel, pid=pid))


@app.route("/posten/<doel>/<pid>")
def post_werk(doel, pid):
    if doel not in {d[0] for d in DOELEN}:
        abort(404)
    w = werk_map().get(pid) or abort(404)
    volg, gepost = _planning_lijst(doel)
    if pid not in volg:
        return redirect(url_for("posten", doel=doel))
    i = volg.index(pid)
    naam, pf, acc = next((n, p, a) for d, n, p, a in DOELEN if d == doel)
    v = (w["tekst"] or textfile.leeg())["velden"]
    tekst = _post_tekst(w, doel)
    links_cl = capt.crosslinks(v.get("Crosslinks", ""))
    handles = sorted({h for h in re.findall(r"(?<![\w.])@[A-Za-z0-9_.]*[A-Za-z0-9_]", v.get("Caption EN", ""))})
    fb_profielen = [{"wie": c["partij"], "url": m}
                    for c in links_cl for m in re.findall(r"(?:https?://)?(?:www\.)?facebook\.com/[^\s·)]+", c["regel"])]
    tabs = []
    for d, n, *_ in DOELEN:
        vl, gp = _planning_lijst(d)
        tabs.append({"doel": d, "naam": n, "open": sum(1 for p in vl if p not in gp), "totaal": len(vl)})
    volgende_open = next((p for p in volg[i + 1:] if p not in gepost), None)
    return render_template("posten.html", w=w, doel=doel, naam=naam, platform=pf, account=acc, tekst=tekst,
                           beelden=_post_beelden(w), plek=v.get("Jaar en plek", ""), handles=handles,
                           fb_profielen=fb_profielen, gepost=gepost.get(pid, ""), positie=(i + 1, len(volg)),
                           vorige=volg[i - 1] if i > 0 else None, volgende=volg[i + 1] if i + 1 < len(volg) else None,
                           volgende_open=volgende_open, tabs=tabs)


# ---------- _Los uitzoeken: per los bestand een werk kiezen (alleen markeren; uitvoeren via tools/uitvoer_los.py) ----------
LOS_MATCH_PATH = os.path.join(config.DATA_DIR, "los_match.json")    # gemaakt door tools/match_los.py
LOS_BESLUIT_PATH = os.path.join(config.DATA_DIR, "los_besluit.json")  # {los_pid|rel: {actie, pid, naam, op}}
LOS_ACTIES = ("werk", "dubbel", "nieuw", "weg", "later")


def _los_lijst():
    return config.load_json(LOS_MATCH_PATH, [])


def _los_sleutel(r):
    return f"{r['los_pid']}|{r['rel']}"


@app.route("/los")
def los_lijst():
    filt = request.args.get("filter", "open")
    lijst, bes = _los_lijst(), config.load_json(LOS_BESLUIT_PATH, {})
    if not lijst:
        flash("Nog geen vergelijking: draai tools/match_los.py")
        return redirect(url_for("overzicht"))
    i = next((i for i, r in enumerate(lijst) if filt == "alle" or _los_sleutel(r) not in bes
              or bes[_los_sleutel(r)].get("actie") == "later" and filt == "later"), 0)
    return redirect(url_for("los_item", i=i, filter=filt))


@app.route("/los/<int:i>", methods=["GET", "POST"])
def los_item(i):
    filt = request.args.get("filter", "open")
    lijst = _los_lijst()
    if not 0 <= i < len(lijst):
        return redirect(url_for("los_lijst", filter=filt))
    r = lijst[i]
    bes = config.load_json(LOS_BESLUIT_PATH, {})
    open_ = lambda j: filt == "alle" or _los_sleutel(lijst[j]) not in bes or j == i
    vorige = next((j for j in range(i - 1, -1, -1) if open_(j)), None)
    volgende = next((j for j in range(i + 1, len(lijst)) if open_(j)), None)
    if request.method == "POST":
        actie = request.form.get("actie", "")
        if actie == "promote":  # eigen nieuw werk in _To Promote; naam = getypt of bestandsnaam
            naam = request.form.get("nieuw", "").strip() or os.path.splitext(r["naam"])[0]
            bes[_los_sleutel(r)] = {"actie": "nieuw", "pid": "", "naam": naam, "promote": True, "merk": r["merk"],
                                    "bestand": r["naam"], "op": dt.datetime.now().isoformat(timespec="seconds")}
            config.save_json(LOS_BESLUIT_PATH, bes)
        elif actie in LOS_ACTIES:
            bes[_los_sleutel(r)] = {"actie": actie, "pid": request.form.get("pid", "") if actie == "werk" else
                                    (r.get("voorstel") or request.form.get("pid", "")) if actie == "dubbel" else "",
                                    "naam": request.form.get("nieuw", "").strip() if actie == "nieuw" else "",
                                    "merk": r["merk"], "bestand": r["naam"],
                                    "op": dt.datetime.now().isoformat(timespec="seconds")}
            config.save_json(LOS_BESLUIT_PATH, bes)
        elif actie == "reset":
            bes.pop(_los_sleutel(r), None)
            config.save_json(LOS_BESLUIT_PATH, bes)
            return redirect(url_for("los_item", i=i, filter=filt))
        if volgende is not None:
            return redirect(url_for("los_item", i=volgende, filter=filt))
        return redirect(url_for("los_lijst", filter=filt))
    wm = werk_map()
    werken_ = sorted((w for w in wm.values() if not w["los"]),
                     key=lambda w: (w["merk"] != r["merk"], w["merk"], w["jaar"] or "9999", w["mapnaam"].lower()))
    tel = collections.Counter(x["soort"] for x in lijst)
    beslist = collections.Counter(b.get("actie") for b in bes.values())
    open_n = sum(1 for x in lijst if _los_sleutel(x) not in bes)
    gekozen = bes.get(_los_sleutel(r), {})
    return render_template("los.html", r=r, i=i, n=len(lijst), filt=filt, vorige=vorige, volgende=volgende,
                           werken=werken_, wm=wm, tel=tel, beslist=beslist, open_n=open_n, gekozen=gekozen,
                           bestand_url=url_for("origineel", pid=r["los_pid"], rel=r["rel"]))


_DATUM_IN_NAAM = re.compile(r"(?<!\d)(20\d{2}|19\d{2})[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])(?!\d)")


def _los_datum(naam):
    m = _DATUM_IN_NAAM.search(naam)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


@app.route("/los/namen", methods=["GET", "POST"])
def los_namen():
    """Alle resterende _Los-items in één raster: naam per item (zelfde naam = zelfde werk; naam van bestaand werk = daarheen)."""
    lijst, bes = _los_lijst(), config.load_json(LOS_BESLUIT_PATH, {})
    wm = werk_map()
    per_mapnaam = {w["mapnaam"].lower(): w for w in wm.values() if not w["los"]}
    if request.method == "POST":
        n_gewijzigd = 0
        for k in request.form.getlist("key"):
            r = next((x for x in lijst if _los_sleutel(x) == k), None)
            if not r:
                continue
            idx = request.form.get("idx_" + k)
            naam = request.form.get("naam_" + idx, "").strip()
            actie = request.form.get("actie_" + idx, "nieuw")
            oud = bes.get(k, {})
            nieuw = {"merk": r["merk"], "bestand": r["naam"], "op": dt.datetime.now().isoformat(timespec="seconds")}
            if actie == "later" and naam:
                actie = "nieuw"  # getypte naam wint van 'later' (bug 06-10: namen gingen verloren)
            if actie in ("dubbel", "weg", "later"):
                nieuw.update(actie=actie, pid="", naam="")
            elif naam and naam.lower() in per_mapnaam:
                nieuw.update(actie="werk", pid=per_mapnaam[naam.lower()]["pid"], naam="")
            elif naam:
                nieuw.update(actie="nieuw", pid="", naam=naam)
            else:
                continue  # leeg laten = niets veranderen
            if {a: oud.get(a) for a in ("actie", "pid", "naam")} != {a: nieuw.get(a) for a in ("actie", "pid", "naam")}:
                bes[k] = nieuw
                n_gewijzigd += 1
        config.save_json(LOS_BESLUIT_PATH, bes)
        flash(f"{n_gewijzigd} items bijgewerkt")
        return redirect(url_for("los_namen"))
    items = []
    for r in lijst:
        b = bes.get(_los_sleutel(r), {})
        stam = os.path.splitext(r["naam"])[0]
        naam = b.get("naam") if b.get("naam") and b.get("naam") != stam else ""
        if b.get("actie") == "werk" and wm.get(b.get("pid")):
            naam = wm[b["pid"]]["mapnaam"]
        datum = _los_datum(r["naam"])
        voorstel = (f"{datum[:4]} Drone" if r["naam"].upper().startswith("DJI_") and datum else
                    f"{datum[:4]} …" if datum else "JJJJ Naam")
        if not naam and voorstel.endswith("Drone"):
            naam = voorstel  # voorstel: alle DJI-video's van één jaar samen
        items.append({"r": r, "key": _los_sleutel(r), "actie": b.get("actie", "nieuw") if b.get("actie") != "werk" else "nieuw",
                      "naam": naam, "placeholder": voorstel, "datum": datum,
                      "url": url_for("origineel", pid=r["los_pid"], rel=r["rel"])})
    items.sort(key=lambda x: (x["r"]["merk"], x["datum"] or "9999", x["r"]["naam"].lower()))
    namen_in_gebruik = sorted({x["naam"] for x in items if x["naam"]})
    return render_template("los_namen.html", items=items, werken=sorted(per_mapnaam.values(), key=lambda w: w["mapnaam"]),
                           namen_in_gebruik=namen_in_gebruik, wm=wm)


# ---------- 0 · Nieuw materiaal: per werk met nieuwe bestanden kiezen: nieuwe post ja/nee + tekst ----------
NM_PATH = os.path.join(config.DATA_DIR, "nieuw_materiaal.json")       # {werkmap-pad: [bestand, ...]} (uit uitvoer_los)
NM_CONCEPT_PATH = os.path.join(config.DATA_DIR, "nieuw_concepten.json")  # {pid-bij-aanmaak: {werk, advies, reden, kies, caption_en, hashtags, vraag}}
NM_BESLUIT_PATH = os.path.join(config.DATA_DIR, "nieuw_besluit.json")  # {merk|mapnaam: {besluit: ja|nee, op, doelen, bestanden}}
VID_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gpp", ".wmv", ".mpg", ".mpeg"}


def _nm_sleutel(w):
    return f"{w['merk']}|{w['mapnaam']}"


def _nm_werken():
    """[(werk, [nieuwe bestanden], concept)] in vaste volgorde; werk gezocht op merk+mapnaam (pad/pid kunnen veranderen)."""
    nm = config.load_json(NM_PATH, {})
    conc = config.load_json(NM_CONCEPT_PATH, {})
    conc_naam = {(c.get("werk") or "").lower(): c for c in conc.values()}
    per_naam = {}
    for w in werken():
        if not w["los"]:
            per_naam.setdefault(w["mapnaam"].lower(), []).append(w)
    uit = []
    for pad, bestanden in sorted(nm.items(), key=lambda kv: kv[0].lower()):
        naam = os.path.basename(pad).lower()
        kand = per_naam.get(naam, [])
        w = next((x for x in kand if os.path.normcase(x["pad"]) == os.path.normcase(pad)), kand[0] if kand else None)
        if not w:
            continue
        aanwezig = [b for b in bestanden if os.path.exists(os.path.join(w["pad"], b))]
        if aanwezig:
            uit.append((w, aanwezig, conc.get(w["pid"]) or conc_naam.get(naam) or {}))
    uit.sort(key=lambda x: (x[0]["merk"] != "Lichtjes", x[0]["jaar"] or "9999", x[0]["mapnaam"].lower()))
    return uit


@app.route("/nieuw")
def nieuw_lijst():
    filt = request.args.get("filter", "open")
    bes = config.load_json(NM_BESLUIT_PATH, {})
    lijst = [x for x in _nm_werken() if filt == "alle" or _nm_sleutel(x[0]) not in bes]
    if not lijst:
        flash("Al het nieuwe materiaal is beoordeeld 🎉 — door naar Planning")
        return redirect(url_for("planning"))
    return redirect(url_for("nieuw_werk", sleutel=_nm_sleutel(lijst[0][0]), filter=filt))


@app.route("/nieuw/<path:sleutel>", methods=["GET", "POST"])
def nieuw_werk(sleutel):
    filt = request.args.get("filter", "open")
    alle = _nm_werken()
    bes = config.load_json(NM_BESLUIT_PATH, {})
    idx = next((i for i, x in enumerate(alle) if _nm_sleutel(x[0]) == sleutel), None)
    if idx is None:
        return redirect(url_for("nieuw_lijst", filter=filt))
    w, bestanden, conc = alle[idx]
    zichtbaar = lambda x: filt == "alle" or _nm_sleutel(x[0]) not in bes or _nm_sleutel(x[0]) == sleutel
    vorige = next((_nm_sleutel(x[0]) for x in reversed(alle[:idx]) if zichtbaar(x)), None)
    volgende = next((_nm_sleutel(x[0]) for x in alle[idx + 1:] if zichtbaar(x)), None)
    eigen = _eigen_doelen(w)
    if request.method == "POST":
        actie = request.form.get("actie", "")
        if actie in ("ja", "nee"):
            gekozen = [b for b in request.form.getlist("bestand") if b in bestanden]
            doelen = [d for d, *_ in eigen if request.form.get("doel_" + d) == "1"]
            if actie == "ja":
                # tekst: nieuwe Caption EN/Hashtags; oude Caption EN naar 'Eerdere captions'
                data = textfile.lees(w["pad"]) or textfile.leeg()
                oud = data["velden"].get("Caption EN", "").strip()
                nieuw_tekst = request.form.get("caption_en", "").replace("\r\n", "\n").strip()
                if oud and textfile.norm(oud) != textfile.norm(nieuw_tekst):
                    data["eerder"].append({"kop": f"vorige Caption EN · {dt.date.today().isoformat()}", "tekst": oud})
                data["velden"]["Caption EN"] = nieuw_tekst
                data["velden"]["Hashtags"] = request.form.get("hashtags", "").strip()
                textfile.schrijf(w["pad"], data)
                herlaad_werk(w["pid"])
                plan = config.load_json(PLAN_PATH, {})
                plan[w["pid"]] = {"doelen": doelen, "niet": False, "klaar": dt.datetime.now().isoformat(timespec="seconds"),
                                  "nieuw_materiaal": True, "beelden": gekozen}
                config.save_json(PLAN_PATH, plan)
                pl = config.load_json(PLANNING_PATH, {})
                for d in doelen:
                    pl.setdefault(d, {"volgorde": [], "gepost": {}})["gepost"].pop(w["pid"], None)
                config.save_json(PLANNING_PATH, pl)
            bes[sleutel] = {"besluit": actie, "doelen": doelen if actie == "ja" else [], "bestanden": gekozen,
                            "op": dt.datetime.now().isoformat(timespec="seconds")}
            config.save_json(NM_BESLUIT_PATH, bes)
            melding = f"{w['mapnaam']}: {'nieuwe post gepland' if actie == 'ja' else 'geen nieuwe post'}"
            if actie == "ja" and os.sep + "_Promoted" + os.sep in w["pad"] and doelen:
                try:
                    _verhuis_werk(w, naar_promoted=False)
                    melding += " · map terug naar _To Promote"
                except OSError as e:
                    melding += f" · verplaatsen mislukt: {e}"
            flash(melding)
        elif actie == "reset":
            bes.pop(sleutel, None)
            config.save_json(NM_BESLUIT_PATH, bes)
            return redirect(url_for("nieuw_werk", sleutel=sleutel, filter=filt))
        if volgende:
            return redirect(url_for("nieuw_werk", sleutel=volgende, filter=filt))
        return redirect(url_for("nieuw_lijst", filter=filt))
    v = (w["tekst"] or textfile.leeg())["velden"]
    gekozen = bes.get(sleutel, {})
    kies = set(gekozen.get("bestanden") or conc.get("kies") or bestanden)
    media = [{"naam": b, "url": url_for("origineel", pid=w["pid"], rel=b),
              "video": os.path.splitext(b)[1].lower() in VID_EXT, "gekozen": b in kies} for b in bestanden]
    per_key = {p["key"]: p for p in online()["posts"]}
    gepost = _gepost_per_doel(w["pid"], per_key, links_per_werk())
    tel = {"open": sum(1 for x in alle if _nm_sleutel(x[0]) not in bes), "alle": len(alle)}
    lijst = [x for x in alle if zichtbaar(x)]
    return render_template("nieuw.html", w=w, media=media, conc=conc, gekozen=gekozen, doelen=eigen, gepost=gepost,
                           caption_en=conc.get("caption_en") or v.get("Caption EN", ""),
                           hashtags=conc.get("hashtags") or v.get("Hashtags", ""), oud_caption=v.get("Caption EN", ""),
                           vorige=vorige, volgende=volgende, filt=filt, tel=tel, sleutel=sleutel,
                           positie=([_nm_sleutel(x[0]) for x in lijst].index(sleutel) + 1, len(lijst)))


if __name__ == "__main__":
    poort = 5077
    if os.environ.get("STB_GEEN_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{poort}")).start()
    app.run(host="127.0.0.1", port=poort, debug=False)
