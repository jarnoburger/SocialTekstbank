"""Eenmalig: vervangt publiceer-GET + helpers door 4-stappen-versie. Backup: app.py.voor-stappen.bak"""
import io, os, shutil
P = os.path.join(os.path.dirname(__file__), "..", "app.py")
src = io.open(P, encoding="utf-8").read()
start = src.index('    filt = request.args.get("filter", "open")\n    werken_ = _publiceer_werken(')
eind = src.index('if __name__ == "__main__":')
nieuw = '''    stap = request.args.get("stap") or _eerste_open_stap()
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


'''
shutil.copy(P, P + ".voor-stappen.bak")
io.open(P, "w", encoding="utf-8", newline="").write(src[:start] + nieuw + src[eind:])
print("ok", len(src), "->", len(src[:start] + nieuw + src[eind:]))
