#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Macht aus den Funden eine Seite, die ein Mensch lesen kann.

    py inhalt_bericht.py                  # Handprobe: 20 zufaellige schwere Faelle
    py inhalt_bericht.py --alle           # alle Sachfehler und ueberdehnten
    py inhalt_bericht.py --art kausal     # nur die Kausalsprache

Warum nicht einfach die JSON weitergeben
----------------------------------------
Weil eine Fundliste, die irgendwo liegt, niemand liest - das ist in diesem
Haus fuenfmal passiert. Und weil **1.276 Sachfehler keine Zahl sind, der man
glaubt**: Zwei Modelldurchgaenge sind sich einig, aber sie teilen den
Massstab. Ob die Liste traegt, entscheidet eine Handprobe, und dafuer muss
jeder Fall mit seiner Quelle nebeneinander stehen.

Die Vorgabe ist deshalb die **Probe von zwanzig**, nicht die ganze Liste:
Erst lesen, dann aendern. Jeder Fall traegt den Link zu PubMed - wer
zweifelt, liest den Abstract selbst.
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import pathlib
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
from inhalt_pruefen import archive  # noqa: E402

EINORDNUNG = HIER / "inhalt-einordnung.json"
ZIEL = HIER / "inhalt-bericht.html"

FARBE = {"sachfehler": ("#8A2D2D", "#FAEAEA"),
         "ueberdehnt": ("#8A5608", "#F5EBD9"),
         "kausal": ("#0E5A5E", "#DCEDEC"),
         "kein_fehler": ("#1C6B3C", "#E6F4EC")}
WORT = {"sachfehler": "Sachfehler", "ueberdehnt": "überdehnt",
        "kausal": "Kausalsprache", "kein_fehler": "kein Fehler"}


def seite(faelle: list, kopf: str, zahlen: dict) -> str:
    teile = ["""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inhaltsprüfung der Hub-Zusammenfassungen</title><style>
body{margin:0;background:#EDF2FA;color:#111;
  font:400 15px/1.65 Lato,-apple-system,Segoe UI,sans-serif}
.h{max-width:980px;margin:0 auto;padding:0 20px 70px}
header{background:#0051A1;color:#fff;padding:26px 0}
header h1{margin:0 0 6px;font-size:25px}
header p{margin:0;color:#C9DCF2;max-width:76ch;font-size:14.5px}
.zahlen{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0 26px}
.z{background:#fff;border:1px solid #E3EAF3;border-radius:7px;
  padding:11px 15px;border-top:3px solid var(--f)}
.z b{display:block;font-size:24px;color:var(--f);
  font-variant-numeric:tabular-nums;line-height:1.1}
.z span{font-size:12.5px;color:#545C63}
.hinweis{background:#FFF8E6;border-left:3px solid #BE9E53;padding:13px 17px;
  margin:0 0 26px;font-size:14px;color:#5C4A17;border-radius:0 4px 4px 0}
.f{background:#fff;border:1px solid #E3EAF3;border-radius:7px;
  padding:16px 18px;margin:0 0 14px;border-left:3px solid var(--f)}
.kopf{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 9px}
.marke{background:var(--t);color:var(--f);font-size:11px;font-weight:700;
  padding:2px 9px;border-radius:3px;text-transform:uppercase;
  letter-spacing:.04em}
.hub{font-size:12px;color:#545C63}
.pm{font-size:12px;margin-left:auto}
.pm a{color:#0051A1}
.f h3{margin:0 0 8px;font-size:16.5px;line-height:1.35}
.zeile{display:grid;grid-template-columns:86px 1fr;gap:10px;
  margin:0 0 6px;font-size:14px;align-items:start}
.zeile b{font-size:12px;color:#545C63;text-transform:uppercase;
  letter-spacing:.04em;padding-top:2px}
.stelle{background:#FAEAEA;padding:1px 4px;border-radius:3px}
.quelle{color:#1C6B3C}
.urteil{margin:12px 0 0;padding:9px 0 0;border-top:1px solid #E3EAF3;
  font-size:13px;color:#545C63}
.urteil label{margin-right:18px;cursor:pointer}
@media(max-width:640px){.zeile{grid-template-columns:1fr;gap:2px}}
</style></head><body><header><div class="h">
<h1>Inhaltsprüfung der Hub-Zusammenfassungen</h1>
<p>""" + kopf + "</p></div></header><div class=\"h\">"]

    teile.append('<div class="zahlen">')
    for art in ("sachfehler", "ueberdehnt", "kausal", "kein_fehler"):
        f, t = FARBE[art]
        teile.append(f'<div class="z" style="--f:{f}"><b>{zahlen.get(art,0)}'
                     f'</b><span>{WORT[art]}</span></div>')
    teile.append("</div>")

    teile.append('<div class="hinweis"><b>Bitte zuerst lesen, dann ändern.</b> '
                 'Zwei Modelldurchgänge sind sich einig, aber sie teilen den '
                 'Maßstab — ob die Liste trägt, entscheidet diese Handprobe. '
                 'Jeder Fall verlinkt den Abstract; wer zweifelt, liest '
                 'selbst nach.</div>')

    for k, v in faelle:
        art = v["art"]
        f, t = FARBE.get(art, ("#545C63", "#EEE"))
        pmid = k.split("/")[-1]
        teile.append(
            f'<div class="f" style="--f:{f};--t:{t}">'
            f'<div class="kopf"><span class="marke">{WORT.get(art, art)}'
            f'</span><span class="marke">{html.escape(v.get("schwere",""))}'
            f'</span><span class="hub">{html.escape(v.get("hub",""))}</span>'
            f'<span class="pm"><a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/"'
            f' target="_blank" rel="noopener">PubMed {pmid} ↗</a></span></div>'
            f'<h3>{html.escape(v.get("titel",""))}</h3>'
            f'<div class="zeile"><b>Im Text</b><span class="stelle">'
            f'{html.escape(v.get("stelle",""))}</span></div>'
            f'<div class="zeile"><b>Die Quelle</b><span class="quelle">'
            f'{html.escape(v.get("richtig",""))}</span></div>'
            f'<div class="zeile"><b>Deutsch</b><span>'
            f'{html.escape(v.get("sum",""))}</span></div>'
            '<div class="urteil"><label><input type="checkbox"> stimmt, '
            'berichtigen</label><label><input type="checkbox"> stimmt nicht, '
            'Fehlalarm</label></div></div>')
    teile.append("</div></body></html>")
    return "\n".join(teile)


def main() -> int:
    p = argparse.ArgumentParser(description="Bericht der Inhaltspruefung")
    p.add_argument("--probe", type=int, default=20,
                   help="wie viele zufaellige Faelle (Vorgabe 20)")
    p.add_argument("--alle", action="store_true",
                   help="alle Sachfehler und ueberdehnten, nicht nur eine Probe")
    p.add_argument("--art", choices=list(WORT),
                   help="nur diese Art")
    a = p.parse_args()

    if not EINORDNUNG.exists():
        print(f"{EINORDNUNG.name} fehlt - erst inhalt_einordnen.py laufen lassen.")
        return 1
    d = json.loads(EINORDNUNG.read_text(encoding="utf-8"))["einordnung"]
    zahlen = collections.Counter(v["art"] for v in d.values())

    # Den deutschen Text dazuholen - ohne ihn ist ein Fund nicht nachzulesen.
    bestand = archive()
    text = {}
    for hub, liste in bestand.items():
        for x in liste:
            text[hub + "/" + str(x.get("pmid"))] = x
    for k, v in d.items():
        v["sum"] = (text.get(k, {}).get("sum") or "")[:420]

    if a.art:
        faelle = [(k, v) for k, v in d.items() if v["art"] == a.art]
        kopf = f"Alle Fälle der Art „{WORT[a.art]}“."
    else:
        faelle = [(k, v) for k, v in d.items()
                  if v["art"] in ("sachfehler", "ueberdehnt")
                  and v.get("schwere") == "hoch"]
        kopf = ("Sachfehler und überdehnte Aussagen mit der Schwere „hoch“ — "
                "sie stehen im Titel oder betreffen das Hauptergebnis.")
    if not a.alle and not a.art:
        random.seed()
        faelle = random.sample(faelle, min(a.probe, len(faelle)))
        kopf = (f"Zufällige Probe von {len(faelle)} aus "
                f"{zahlen['sachfehler'] + zahlen['ueberdehnt']} Fällen. " + kopf)

    ZIEL.write_text(seite(sorted(faelle), kopf, zahlen), encoding="utf-8")
    print(f"{len(faelle)} Fälle -> {ZIEL}")
    for art in ("sachfehler", "ueberdehnt", "kausal", "kein_fehler"):
        print(f"  {WORT[art]:<16} {zahlen.get(art,0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
