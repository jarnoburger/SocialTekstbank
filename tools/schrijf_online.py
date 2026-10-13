"""Schrijft online research (crosslinks, jaar/plek, credits, bijgewerkte beeldalinea) naar _tekst.md per werk.

python tools/schrijf_online.py data/online_research.json          -> proefrun
python tools/schrijf_online.py data/online_research.json --doe    -> schrijven

Regels:
- Crosslinks: altijd (her)schrijven als het veld leeg is of door Claude gemaakt (marker), anders overslaan.
- Jaar en plek / Credits: alleen vullen als ze leeg zijn; anders komt het voorstel onder Crosslinks.
- Beeldbeschrijving: de eerste alinea (vóór 'Beelden') wordt vervangen door alinea_update; beeldregels blijven.
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A  # noqa: E402
from core import textfile  # noqa: E402

DOE = "--doe" in sys.argv
VANDAAG = dt.date.today().strftime("%d-%m-%Y")
MARKER = "_Online research Claude"


def crosslinks_tekst(r, extra):
    regels = []
    for p in r.get("partijen", []):
        delen = [f"{p.get('rol', '').capitalize() or 'Partij'}: {p['naam']}"]
        if p.get("web"):
            delen.append(p["web"])
        if p.get("instagram"):
            delen.append(p["instagram"])
        delen.append(f"zekerheid {p.get('zekerheid', '?')}")
        if p.get("notitie"):
            delen.append(p["notitie"])
        regels.append("- " + " · ".join(delen))
    if not regels:
        regels.append("- Geen externe partij (eigen werk)." if r.get("geen_extern") else "- Geen partij online gevonden.")
    if r.get("correcties"):
        regels += ["", "Te checken: " + r["correcties"].strip()]
    regels += extra
    bronnen = [b for b in dict.fromkeys(r.get("bronnen", []) + [p.get("bron") for p in r.get("partijen", [])]) if b]
    if bronnen:
        regels += ["", "Bronnen:"] + [f"- {b}" for b in bronnen[:8]]
    regels += ["", f"{MARKER} {VANDAAG}. Alleen links die in zoekresultaten zijn gezien; zekerheid laag = eerst checken._"]
    return "\n".join(regels)


def nieuwe_beeldtekst(oud, alinea):
    alinea = alinea.strip()
    if not oud.strip():
        return f"{alinea}\n\n_Voorzet Claude {VANDAAG}, op basis van online research. Graag controleren._"
    regels = oud.splitlines()
    # eerste regel die met 'Beelden' of '- ' of 'Twijfel' of '_' begint = einde alinea
    for i, r in enumerate(regels):
        rs = r.strip()
        if rs.lower().startswith("beelden") or rs.startswith("- ") or rs.lower().startswith("twijfel") or rs.startswith("_"):
            rest = "\n".join(regels[i:]).strip()
            break
    else:
        rest = ""
    rest = rest.replace("_Voorzet Claude 03-10-2026, op basis van beelden + captions.",
                        f"_Voorzet Claude 03-10-2026 (beelden + captions), aangevuld {VANDAAG} met online research.")
    return f"{alinea}\n\n{rest}".strip()


pad = sys.argv[1]
research = json.load(open(pad, encoding="utf-8"))
per_pid = {w["pid"]: w for w in A.werken(herscan=True)}
tel = {"geschreven": 0, "niet gevonden": 0, "crosslinks overgeslagen": 0}
for r in research:
    w = per_pid.get(r["pid"])
    if not w:
        print("NIET GEVONDEN:", r["mapnaam"])
        tel["niet gevonden"] += 1
        continue
    data = w["tekst"] or textfile.leeg()
    v = data["velden"]
    extra, wijz = [], []
    for veld, sleutel in (("Jaar en plek", "jaar_en_plek"), ("Credits", "credits")):
        nieuw = (r.get(sleutel) or "").strip()
        if not nieuw:
            continue
        if not v.get(veld, "").strip():
            v[veld] = nieuw
            wijz.append(veld)
        elif textfile.norm(nieuw) != textfile.norm(v[veld]):
            extra += ["", f"Voorstel {veld.lower()}: {nieuw}"]
    cl = v.get("Crosslinks", "")
    if not cl.strip() or MARKER in cl:
        v["Crosslinks"] = crosslinks_tekst(r, extra)
        wijz.append("Crosslinks")
    else:
        tel["crosslinks overgeslagen"] += 1
    if (r.get("alinea_update") or "").strip():
        v["Beeldbeschrijving"] = nieuwe_beeldtekst(v.get("Beeldbeschrijving", ""), r["alinea_update"])
        wijz.append("Beeldbeschrijving")
    print(f"{w['mapnaam']:40} {', '.join(wijz)}")
    if DOE and wijz:
        textfile.schrijf(w["pad"], data)
        tel["geschreven"] += 1
print(tel)
if not DOE:
    print("Proefrun. Schrijven met --doe")
