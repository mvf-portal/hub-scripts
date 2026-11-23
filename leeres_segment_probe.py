#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueft, dass ein leeres Empfaengersegment KEINE Testausgabe ausloest.

Aufruf aus einem Portalordner, damit thema.py gefunden wird:

    cd ..\\pflege-portal
    PYTHONPATH=scripts;..\\hub-scripts py ..\\hub-scripts\\leeres_segment_probe.py

WARUM
-----
Seit dem 23.11.2026 unterdrueckt mailchimp_entwurf.py die Testausgabe,
wenn das leere Segment die EINZIGE Beanstandung ist. Diese Vorkehrung
zuendet nur an Tagen, an denen ein Hub keinen einzigen Empfaenger hat -
im Normalbetrieb also nie. Ob sie taugt, wuerde man sonst erst an dem
Morgen merken, an dem sie gebraucht wird, und dann falsch herum.

DIE STELLE, AN DER SIE LAUTLOS VERSAGT, ist nicht die Unterdrueckung
selbst, sondern die Annahme dahinter: dass `pruefe()` bei leerem Segment
GENAU EINE Beanstandung meldet. Kommt aus irgendeinem Grund eine zweite
dazu, ist die Liste nicht mehr gleich, die Bedingung greift nie, und
niemand merkt es - die Mails kaemen einfach weiter.

Deshalb prueft diese Probe gegen eine ECHTE Ausgabe aus dem Archiv des
Portals und nicht gegen ein gebautes Beispiel.
"""
from __future__ import annotations

import json
import pathlib
import sys

import mailchimp_entwurf as M
import torwaechter


def echte_studien(wie_viele: int = 3) -> list[dict]:
    d = json.loads(pathlib.Path("studien-archiv.json").read_text(encoding="utf-8"))
    e = d if isinstance(d, list) else d.get("studien", [])
    if len(e) < wie_viele:
        raise SystemExit("studien-archiv.json ist zu kurz fuer die Probe.")
    return e[:wie_viele]


def main() -> int:
    fehler = 0
    studien = echte_studien()
    html = M.newsletter_html(studien)

    # 1. Leeres Segment, sonst alles in Ordnung.
    b = torwaechter.pruefe(studien, html=html, empfaenger=0,
                           listengroesse=5845, gleichnamige=[])
    print(f"  leeres Segment: {len(b)} Beanstandung(en)")
    for x in b:
        print(f"      {x}")
    if b != [torwaechter.SEGMENT_LEER]:
        print("  FEHLER Die Unterdrueckung greift hier NICHT, weil die Liste "
              "nicht genau aus der einen Beanstandung besteht.")
        fehler += 1
    else:
        print("  OK  genau eine Beanstandung, die Unterdrueckung greift")

    # 2. Gegenprobe: ein voller Verteiler darf gar nichts melden.
    b2 = torwaechter.pruefe(studien, html=html, empfaenger=42,
                            listengroesse=5845, gleichnamige=[])
    if b2:
        print(f"  HINWEIS bei vollem Verteiler: {b2}")
    print(f"  {'OK ' if not b2 else 'FEHLER'} voller Verteiler: "
          f"{len(b2)} Beanstandung(en)")
    fehler += 1 if b2 else 0

    # 3. Gegenprobe, die das Eigentliche misst: Kommt EINE weitere
    #    Beanstandung dazu, muss die Testausgabe wieder hinausgehen.
    #    Ohne diese Haelfte bestuende die Probe auch dann, wenn jemand die
    #    Mail ersatzlos abgeschaltet haette.
    b3 = torwaechter.pruefe(studien, html="zu kurz", empfaenger=0,
                            listengroesse=5845, gleichnamige=[])
    unterdrueckt = (b3 == [torwaechter.SEGMENT_LEER])
    print(f"  {'FEHLER' if unterdrueckt else 'OK '} leeres Segment PLUS "
          f"kaputtes HTML: {len(b3)} Beanstandung(en), Testausgabe "
          f"{'unterdrueckt' if unterdrueckt else 'geht hinaus'}")
    fehler += 1 if unterdrueckt else 0

    print(f"\n{fehler} Abweichung(en).")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
