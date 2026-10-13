"""Werkt het _To Promote-deel van INDEX.md bij (per merk-hoofdmap), op basis van de actuele scan.

- Vervangt de oude secties '## _To Promote...' door één blok tussen markers.
- Structuurtabel: rijen voor _To Promote worden één actuele rij.
- Opmerkingen en disciplines uit de oude tabellen worden per werk overgenomen (naam-match).
- Opgeloste aandachtspunten (mappen 1-5, dubbele mappen, Done\\Done ...) worden doorgestreept.
Backup: INDEX.backup-<datum>.md naast het origineel.

python tools/index_promote.py          -> proefrun (toont het nieuwe blok)
python tools/index_promote.py --doe    -> schrijven
"""
import datetime as dt
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import config  # noqa: E402

DOE = "--doe" in sys.argv
START, EIND = "<!-- SocialTekstbank:start -->", "<!-- SocialTekstbank:eind -->"
VANDAAG = dt.date.today().strftime("%d-%m-%Y")


def sleutel(naam):
    n = re.sub(r"^[\d\-–~ ]+", "", naam.lower())
    n = re.sub(r"\(.*?\)|`|\+.*$", "", n)
    return re.sub(r"[^a-z0-9]", "", n.replace("_", ""))


def oude_opmerkingen(tekst):
    """{sleutel: (discipline, opmerking)} uit oude markdowntabellen in _To Promote-secties."""
    uit = {}
    for regel in tekst.splitlines():
        if not regel.startswith("|") or regel.startswith("|---"):
            continue
        cellen = [c.strip() for c in regel.strip("|").split("|")]
        if len(cellen) == 7:   # SJB: Project | Jaar | Discipline | Beeld | Video | GB | Opmerking
            namen, disc, opm = cellen[0], cellen[2], cellen[6]
        elif len(cellen) == 5:  # Lichtjes: Onderdeel | Jaar | Beeld | Video | Opmerking
            namen, disc, opm = cellen[0], "", cellen[4]
        else:
            continue
        for naam in re.split(r",| / ", namen):
            k = sleutel(naam)
            if k and (disc or opm):
                uit[k] = (disc, opm)
    return uit


def total_gb_fix(x):
    return x


def blok(merk, werken, lpw, oud):
    rij = []
    totaal_gb = 0.0
    for w in werken:
        if w["los"]:
            continue
        gb = sum(m["size"] for m in w["media"]) / 1e9
        totaal_gb += gb
        n_posts = len(lpw.get(w["pid"], []))
        status = ("online" if n_posts else {"gepromoot": "gepromoot (niet gekoppeld)", "te promoten": "te posten",
                                              "deels": "deels", "niet promoten": "niet promoten"}.get(w["promotie"], "?"))
        st = w["status"]
        tekst = "".join(x for x, ok in (("K", st["kort"]), ("L", st["lang"]), ("C", st["caption"])) if ok) or "–"
        disc, opm = oud.get(sleutel(w["naam"]), ("", ""))
        disc = w["yml"].get("discipline") or disc
        gb_txt = f"{gb:.1f}".replace(".", ",")
        rij.append(f"| {w['mapnaam']} | {w['jaar'] or '?'} | {disc or ''} | {w['n_img']} | {w['n_vid']} | "
                   f"{gb_txt} | {status} | {tekst} | {opm} |")
    los = [w for w in werken if w["los"]]
    n_los = sum(len(w["media"]) for w in los)
    kop = [START,
           f"## _To Promote — per werk (actueel {VANDAAG}, gegenereerd door SocialTekstbank)",
           "",
           "Alle werken staan direct in `_To Promote\\` (geen Done/ToDo-mappen meer). "
           "Mapnaam = `JJJJ Naam`; status staat in `_project.yml` → `promotie:` en wordt in de app aangevuld met "
           "gekoppelde posts. Teksten per werk in `_tekst.md`, koppelingen in `_social.json`.",
           "",
           "Status: **online** = post gekoppeld · **gepromoot (niet gekoppeld)** = stond in Done, post nog niet gevonden · "
           "**te posten** = stond in ToDo. Tekst: K = kort, L = lang, C = caption.",
           "",
           "| Werk | Jaar | Discipline | Foto | Video | GB | Status | Tekst | Opmerking |",
           "|---|---|---|---|---|---|---|---|---|"]
    voet = ["",
            f"**Totaal:** {len(rij)} werken, {str(round(total_gb_fix(totaal_gb),1)).replace('.', ',')} GB media · `_Los\\`: {n_los} losse bestanden "
            "(social-downloads zonder projectlabel).",
            f"Werken zonder jaartal: {sum(1 for w in werken if not w['los'] and not w['jaar'])}.",
            EIND]
    return "\n".join(kop + rij + voet), len(rij), totaal_gb, n_los


OPGELOST = [r"Mappen `1`–`5`", r"Dubbele projectmappen", r"Dubbele/onduidelijke mappen",
            r"losse social-media-downloads zonder projectlabel"]


def werk_index(root_cfg, werken, lpw):
    hoofd = os.path.dirname(root_cfg["pad"])
    pad = os.path.join(hoofd, "INDEX.md")
    with open(pad, encoding="utf-8-sig") as f:
        tekst = f.read()
    oud = oude_opmerkingen(tekst)
    nieuw_blok, n, gb, n_los = blok(root_cfg["merk"], werken, lpw, oud)

    if START in tekst:
        tekst = re.sub(re.escape(START) + r".*?" + re.escape(EIND), lambda m: nieuw_blok, tekst, flags=re.S)
    else:
        # oude _To Promote-secties vervangen door het blok
        delen = re.split(r"(?m)^(## .*)$", tekst)
        uit, ingevoegd, i = [delen[0]], False, 1
        while i < len(delen):
            kop, inhoud = delen[i], delen[i + 1]
            if kop.startswith("## _To Promote"):
                if not ingevoegd:
                    uit.append(nieuw_blok + "\n\n")
                    ingevoegd = True
            else:
                uit.append(kop + inhoud)
            i += 2
        if not ingevoegd:
            uit.append("\n" + nieuw_blok + "\n")
        tekst = "".join(uit)

    # structuurtabel: _To Promote-rijen -> één rij
    regels, nieuw, gedaan = tekst.splitlines(), [], False
    for r in regels:
        if r.startswith("| `_To Promote"):
            if not gedaan:
                nieuw.append(f"| `_To Promote\\` | {n} werken direct in de map (status in `_project.yml`), "
                             f"`_Los\\` ({n_los} losse bestanden) — zie tabel | {str(round(gb,1)).replace('.', ',')} GB media | ★★★ hoofdbron |")
                gedaan = True
            continue
        if r.startswith("- ") and any(re.search(p, r) for p in OPGELOST) and not r.startswith("- ~~"):
            r = f"- ~~{r[2:]}~~ → opgelost {VANDAAG} (herstructurering SocialTekstbank)"
        nieuw.append(r)
    tekst = "\n".join(nieuw) + "\n"

    notitie = (f"_Bijgewerkt {VANDAAG} door SocialTekstbank: `_To Promote` plat gemaakt (geen Done/ToDo/1-5), "
               "mapnamen `JJJJ Naam`, jaartallen uitgezocht, status in `_project.yml`. "
               "Log: `E:\\Code\\_Projects\\SocialTekstbank\\data\\*-log.json`._")
    if "door SocialTekstbank: `_To Promote` plat" not in tekst:
        tekst = tekst.replace("\n\n", "\n\n" + notitie + "\n\n", 1)
    return pad, tekst, nieuw_blok


ws = A.werken(herscan=True)
lpw = A.links_per_werk()
for r in config.load_config()["roots"]:
    eigen = [w for w in ws if w["merk"] == r["merk"]]
    pad, tekst, nieuw_blok = werk_index(r, eigen, lpw)
    print(f"===== {pad}\n{nieuw_blok[:1500]}\n...")
    if DOE:
        backup = pad.replace("INDEX.md", f"INDEX.backup-{dt.datetime.now():%Y%m%d-%H%M%S}.md")
        if not os.path.exists(backup):  # nooit een eerdere backup overschrijven
            shutil.copy(pad, backup)
        with open(pad, "w", encoding="utf-8") as f:
            f.write(tekst)
        print("geschreven:", pad)
if not DOE:
    print("\nProefrun. Schrijven met --doe")
