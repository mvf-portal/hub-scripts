#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Raeumt die Rand-Leerzeichen und die daraus entstandenen Dubletten auf.

Bis zum 15.09.2026 uebernahm `update_studies.py` die Antwort des Modells
ungeprueft. Das Modell schreibt gelegentlich ein Leerzeichen vor den Wert - im
Kardio-Hub kamen sechs PMIDs als " 42726202" statt "42726202". Der Commit
`cad68bd` behebt die Ursache und steht seit dem 15.09.2026 auch auf `stabil`,
laeuft also in allen Hubs. Was bereits im Archiv steht, raeumt er aber nicht
weg - dafuer ist dieses Skript da. Es ist ein einmaliger Lauf; danach kann es
liegen bleiben, es findet dann nichts mehr.

Zwei Dinge passieren:

1. **Rand-Leerzeichen weg**, in jedem Textfeld jedes Eintrags. Nicht nur in der
   PMID: Auch die Titel begannen mit einem Leerzeichen, was in der Liste des
   Hubs sichtbar war.

2. **Dubletten zusammenfuehren.** Die Entdoppelung in `update_archive()`
   vergleicht auf das Zeichen genau, also galt " 42731841" als neu, obwohl
   "42731841" schon im Archiv stand. Dieselbe Studie steht dann zweimal da, mit
   zwei verschiedenen deutschen Uebersetzungen.

   **Welche Fassung bleibt:** die zuerst aufgenommene. Das ist dieselbe Regel,
   nach der `update_archive()` ohnehin arbeitet ("das zuerst gesehene
   Aufnahmedatum bleibt erhalten, damit eine Studie nicht bei jedem Lauf nach
   vorne rutscht"), und es ist die Fassung, die tatsaechlich im Newsletter und
   im RSS-Feed hinausging. Die spaetere zu behalten hiesse, die Historie
   nachtraeglich zu veraendern.

Aufruf im Portal-Ordner:
    python archiv_bereinigen.py                # zeigt nur, was passieren wuerde
    python archiv_bereinigen.py --schreiben    # aendert studien-archiv.json
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ARCHIV = "studien-archiv.json"


def nur_ziffern(wert) -> str:
    return re.sub(r"\D", "", str(wert))


def main() -> int:
    p = argparse.ArgumentParser(description="Rand-Leerzeichen und Dubletten im Studienarchiv beheben")
    p.add_argument("--datei", default=ARCHIV)
    p.add_argument("--schreiben", action="store_true",
                   help="Aenderungen wirklich in die Datei schreiben")
    a = p.parse_args()

    pfad = pathlib.Path(a.datei)
    if not pfad.exists():
        print(f"{pfad} gibt es nicht - nichts zu tun.")
        return 0

    eintraege = json.loads(pfad.read_text(encoding="utf-8"))
    if isinstance(eintraege, dict):
        print("Unerwartetes Format (Objekt statt Liste) - nichts geaendert.")
        return 1

    # ---- 1. Rand-Leerzeichen -------------------------------------------
    felder_beschnitten = 0
    eintraege_beschnitten = 0
    for e in eintraege:
        beruehrt = False
        for feld, wert in list(e.items()):
            if isinstance(wert, str) and wert != wert.strip():
                e[feld] = wert.strip()
                felder_beschnitten += 1
                beruehrt = True
        if beruehrt:
            eintraege_beschnitten += 1

    # ---- 2. Dubletten ---------------------------------------------------
    # Nach dem Beschneiden sind die PMIDs vergleichbar. Aeltestes
    # Aufnahmedatum gewinnt; bei gleichem Datum der fruehere Listenplatz.
    nach_pmid: dict[str, list[int]] = collections.defaultdict(list)
    for i, e in enumerate(eintraege):
        nach_pmid[nur_ziffern(e.get("pmid", ""))].append(i)

    raus: set[int] = set()
    for pmid, plaetze in nach_pmid.items():
        if len(plaetze) < 2:
            continue
        behalten = min(plaetze, key=lambda i: (eintraege[i].get("aufgenommen", "9999"), i))
        print(f"  PMID {pmid}: {len(plaetze)} Eintraege")
        for i in plaetze:
            e = eintraege[i]
            marke = "BLEIBT " if i == behalten else "entfaellt"
            print(f"    {marke}  aufgenommen {e.get('aufgenommen','?')}  {e.get('title','')[:58]}")
            if i != behalten:
                raus.add(i)

    if raus:
        eintraege = [e for i, e in enumerate(eintraege) if i not in raus]

    print(f"\n{pfad}: {felder_beschnitten} Felder beschnitten "
          f"(in {eintraege_beschnitten} Eintraegen), {len(raus)} Dubletten entfernt, "
          f"{len(eintraege)} Eintraege bleiben.")

    if not (felder_beschnitten or raus):
        print("Nichts zu tun.")
        return 0

    if not a.schreiben:
        print("Probelauf - nichts geschrieben. Mit --schreiben wirklich aendern.")
        return 0

    # Dieselbe Schreibweise wie update_archive(), damit der Unterschied im
    # Commit nur die echten Aenderungen zeigt und nicht die ganze Datei.
    pfad.write_text(
        json.dumps(eintraege, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
