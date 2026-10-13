"""Haalt per werk max 4 beelden op (thumbnails van gekoppelde posts) voor beschrijving door Claude.

python tools/beelden_ophalen.py <batchnr> [aantal_werken=10]
-> data/beelden/batch<N>/<nr>_<werk>/<i>.jpg  +  data/beelden/batch<N>/manifest.json
Volgorde: werken met de meeste gekoppelde posts eerst; werken die al een Beeldbeschrijving hebben worden overgeslagen.
"""
import io, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STB_GEEN_BROWSER", "1")
import requests  # noqa: E402
from PIL import Image  # noqa: E402
import app as A  # noqa: E402
from core import config, match  # noqa: E402

batch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
aantal = int(sys.argv[2]) if len(sys.argv) > 2 else 10
uitdir = os.path.join(config.DATA_DIR, "beelden", f"batch{batch}")
os.makedirs(uitdir, exist_ok=True)

wm = A.werk_map()
posts = {p["key"]: p for p in A.online()["posts"]}
per_werk = {}
for k, v in A.links().items():
    if v["pid"] in wm and k in posts:
        per_werk.setdefault(v["pid"], []).append(posts[k])

def heeft_beschrijving(w):
    return bool(w["tekst"] and w["tekst"]["velden"].get("Beeldbeschrijving", "").strip())

al_gedaan = set()
for d in os.listdir(os.path.join(config.DATA_DIR, "beelden")):
    mp = os.path.join(config.DATA_DIR, "beelden", d, "manifest.json")
    if d != f"batch{batch}" and os.path.exists(mp):
        al_gedaan |= {m["pid"] for m in json.load(open(mp, encoding="utf-8"))}

ALLES = "--alles" in sys.argv
pool = [pid for pid, w in wm.items() if not w["los"]] if ALLES else list(per_werk)
kandidaten = sorted((pid for pid in pool if not heeft_beschrijving(wm[pid]) and pid not in al_gedaan),
                    key=lambda pid: (-len(per_werk.get(pid, [])), wm[pid]["mapnaam"]))[:aantal]
manifest = []
for nr, pid in enumerate(kandidaten, 1):
    w = wm[pid]
    slug = re.sub(r"[^\w\-]+", "_", w["mapnaam"])[:40]
    d = os.path.join(uitdir, f"{nr:02d}_{slug}")
    os.makedirs(d, exist_ok=True)
    ps = sorted(per_werk.get(pid, []), key=lambda p: (not p["caption"].strip(), p["timestamp"]))
    beelden, hashes = [], []
    for p in ps:
        for url in p["thumbs"][:2]:
            if len(beelden) >= 4:
                break
            try:
                r = requests.get(url, timeout=20); r.raise_for_status()
                im = Image.open(io.BytesIO(r.content)).convert("RGB")
            except Exception as e:  # noqa: BLE001
                continue
            h = match.dhash_img(im)
            if any(match.afstand(h, x) <= 6 for x in hashes):
                continue  # bijna hetzelfde beeld (IG/FB-dubbel)
            hashes.append(h)
            im.thumbnail((512, 512))
            fn = f"{len(beelden)+1}.jpg"
            im.save(os.path.join(d, fn), "JPEG", quality=82)
            beelden.append({"bestand": fn, "post": p["key"], "platform": p["platform"], "datum": p["timestamp"][:10],
                            "permalink": p["permalink"], "type": p["media_type"]})
    # lokale foto's aanvullen (eerst lokaal aanwezige, dan cloud-only: OneDrive downloadt die)
    if len(beelden) < 4:
        imgs = [m for m in w["media"] if m["type"] == "img" and not m["naam"].lower().endswith((".gif", ".heic"))]
        imgs.sort(key=lambda m: (m["cloud"], -m["size"]))
        stap = max(1, len(imgs) // 8)
        for m in imgs[::stap]:
            if len(beelden) >= 4:
                break
            try:
                with Image.open(m["pad"]) as im0:
                    im0.draft("RGB", (1024, 1024))
                    im = im0.convert("RGB")
            except Exception:  # noqa: BLE001
                continue
            h = match.dhash_img(im)
            if any(match.afstand(h, x) <= 6 for x in hashes):
                continue
            hashes.append(h)
            im.thumbnail((512, 512))
            fn = f"{len(beelden)+1}.jpg"
            im.save(os.path.join(d, fn), "JPEG", quality=82)
            beelden.append({"bestand": fn, "lokaal": m["rel"], "platform": "lokaal", "datum": "", "permalink": "",
                            "type": "foto"})
    # contactblad 2x2 voor snelle beoordeling
    if beelden:
        S = 300
        blad = Image.new("RGB", (S * 2 + 8, S * 2 + 8), "white")
        from PIL import ImageDraw
        for i, b in enumerate(beelden):
            im = Image.open(os.path.join(d, b["bestand"])); im.thumbnail((S, S))
            x, y = (i % 2) * (S + 8), (i // 2) * (S + 8)
            blad.paste(im, (x, y)); ImageDraw.Draw(blad).text((x + 5, y + 5), str(i + 1), fill="yellow")
        os.makedirs(os.path.join(uitdir, "bladen"), exist_ok=True)
        blad.save(os.path.join(uitdir, "bladen", f"{nr:03d}.jpg"), "JPEG", quality=78)
    caps = []
    for p in ps:
        c = p["caption"].strip()
        if c and c not in caps:
            caps.append(c)
    manifest.append({"nr": nr, "pid": pid, "merk": w["merk"], "mapnaam": w["mapnaam"], "jaar": w["jaar"],
                     "map": os.path.relpath(d, uitdir), "n_posts": len(ps), "captions": caps[:6],
                     "notitie": w["yml"].get("notitie", ""), "beelden": beelden,
                     "n_media": len(w["media"]), "n_vid": w["n_vid"],
                     "submappen": sorted({m["rel"].split("/")[0] for m in w["media"] if "/" in m["rel"]})[:8],
                     "bestandsnamen": [m["naam"] for m in w["media"][:12]]})
json.dump(manifest, open(os.path.join(uitdir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"batch{batch}: {len(manifest)} werken, {sum(len(m['beelden']) for m in manifest)} beelden -> {uitdir}")
for m in manifest:
    print(f"  {m['nr']:2} {m['mapnaam']} ({m['n_posts']} posts, {len(m['beelden'])} beelden)")
