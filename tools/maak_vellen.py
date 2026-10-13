"""Maakt per werk met nieuw materiaal één contactvel (JPG) met de nieuwe beelden en videoframes,
plus data/_vellen/context.json (bestaande tekst van het werk). Leest alleen bronbestanden.

python tools/maak_vellen.py
"""
import os, sys, re, json, subprocess, tempfile
os.environ["STB_GEEN_BROWSER"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config  # noqa: E402
from PIL import Image, ImageDraw, ImageOps  # noqa: E402
import imageio_ffmpeg  # noqa: E402

FF = imageio_ffmpeg.get_ffmpeg_exe()
UIT = os.path.join(config.DATA_DIR, "_vellen")
os.makedirs(UIT, exist_ok=True)
TW, TH, KOL = 360, 270, 4
IMG = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".jfif", ".bmp", ".gif", ".tif", ".tiff"}


def duur(pad):
    p = subprocess.run([FF, "-i", pad], capture_output=True, text=True, errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0


def frame(pad, t):
    with tempfile.TemporaryDirectory() as d:
        o = os.path.join(d, "f.jpg")
        subprocess.run([FF, "-y", "-ss", f"{t:.2f}", "-i", pad, "-frames:v", "1", "-vf", "scale=640:-2", o],
                       capture_output=True)
        return Image.open(o).copy() if os.path.exists(o) else None


def tegel(im, label):
    t = Image.new("RGB", (TW, TH + 22), (30, 30, 30))
    if im is not None:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((TW, TH))
        t.paste(im, ((TW - im.width) // 2, (TH - im.height) // 2))
    ImageDraw.Draw(t).text((6, TH + 4), label[:56], fill=(255, 255, 0))
    return t


nm = config.load_json(os.path.join(config.DATA_DIR, "nieuw_materiaal.json"), {})
ctx = {}
with A.app.test_request_context():
    per_pad = {os.path.normcase(w["pad"]): w for w in A.werken(herscan=True) if not w["los"]}
    for i, (pad, bestanden) in enumerate(sorted(nm.items()), 1):
        w = per_pad.get(os.path.normcase(pad))
        if not w:
            print("werk niet gevonden:", pad); continue
        tegels = []
        for j, b in enumerate(bestanden, 1):
            f = os.path.join(pad, b)
            if not os.path.exists(f):
                continue
            ext = os.path.splitext(b)[1].lower()
            try:
                if ext in IMG:
                    tegels.append(tegel(Image.open(f), f"#{j} {b}"))
                else:
                    d = duur(f)
                    for pct in (0.15, 0.6):
                        tegels.append(tegel(frame(f, max(0.5, d * pct)), f"#{j} VIDEO {int(d)}s @{int(pct*100)}% {b}"))
            except Exception as e:
                tegels.append(tegel(None, f"#{j} FOUT {b}: {e}"))
        if not tegels:
            continue
        rijen = (len(tegels) + KOL - 1) // KOL
        vel = Image.new("RGB", (KOL * TW, rijen * (TH + 22)), (0, 0, 0))
        for k, t in enumerate(tegels):
            vel.paste(t, ((k % KOL) * TW, (k // KOL) * (TH + 22)))
        naam = f"{i:02d}_{re.sub(r'[^A-Za-z0-9 _-]', '', w['mapnaam'])}.jpg"
        vel.save(os.path.join(UIT, naam), quality=82)
        v = (w["tekst"] or {}).get("velden", {})
        ctx[naam] = {"pid": w["pid"], "pad": pad, "mapnaam": w["mapnaam"], "merk": w["merk"],
                     "promoted": "_Promoted" in pad, "nieuw": bestanden,
                     "jaar_en_plek": v.get("Jaar en plek", ""), "kort": v.get("Kort", ""),
                     "caption_en": v.get("Caption EN", ""), "hashtags": v.get("Hashtags", ""),
                     "credits": v.get("Credits", "")}
        print(naam, len(bestanden), "bestanden,", len(tegels), "tegels")
json.dump(ctx, open(os.path.join(UIT, "context.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
