#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueft den Takthinweis im Newsletter, ohne Mailchimp anzufassen.

Aufruf aus einem Portalordner heraus, damit thema.py gefunden wird:

    cd ../pflege-portal
    PYTHONPATH=scripts:../hub-scripts py ../hub-scripts/takthinweis_probe.py

Geprueft wird dreierlei, und das Dritte ist das eigentliche:

1. Der Kasten steht in der fertigen Mail.
2. Der Fusslink zeigt auf unsere Newsletterseite und nicht mehr auf
   *|UPDATE_PROFILE|*. Jener Weg fuehrt auf eine Zwischenseite, die erst
   eine zweite Mail verschickt, und die Taktwahl steht dort gar nicht drin
   (gemessen am 20.11.2026).
3. DER KASTEN RAEUMT SICH SELBST AB. Ein Hinweis mit Frist, der die Frist
   nicht einhaelt, ist schlimmer als keiner: Er steht dann fuer immer da.
   Genau das prueft niemand von selbst nach, weil es erst in Wochen
   auffaellt - also hier, mit einem vorgestellten Datum.

Der Abmeldelink muss unangetastet bleiben. Ihn zu verlieren waere nicht
unschoen, sondern rechtswidrig.
"""
from __future__ import annotations

import datetime as dt
import sys

import mailchimp_entwurf as M

def studie() -> dict:
    """Ein ECHTER Eintrag aus dem Archiv dieses Portals.

    Ein von Hand gebautes Beispiel haette hier dreimal hintereinander ein
    anderes Feld vermissen lassen. Die Vorlage liest mehr Felder, als man
    sich merkt - also nimmt die Probe, was im Betrieb wirklich drinsteht.
    """
    import json
    import pathlib
    d = json.loads(pathlib.Path("studien-archiv.json").read_text(encoding="utf-8"))
    eintraege = d if isinstance(d, list) else d.get("studien", [])
    if not eintraege:
        raise SystemExit("studien-archiv.json ist leer - Probe nicht moeglich.")
    return eintraege[0]


def main() -> int:
    fehler = 0
    html = M.newsletter_html([studie()])

    pruefungen = [
        ("Kasten ist drin", "Neu: Sie bestimmen, wie oft" in html, True),
        ("Link auf die Newsletterseite", "/newsletter.html?" in html, True),
        ("Abmeldelink unangetastet", "*|UNSUB|*" in html, True),
        ("kein UPDATE_PROFILE mehr", "*|UPDATE_PROFILE|*" in html, False),
        ("keine Adresse im Link", "*|EMAIL|*" in html, False),
    ]
    for name, ist, soll in pruefungen:
        gut = (ist == soll)
        print(f"  {'OK ' if gut else 'FEHLER'} {name}")
        fehler += 0 if gut else 1

    # Die Frist. Einen Tag davor muss der Kasten da sein, einen Tag danach weg.
    p = "utm_source=probe"
    davor = M.takthinweis(p, M.HINWEIS_BIS - dt.timedelta(days=1))
    amtag = M.takthinweis(p, M.HINWEIS_BIS)
    danach = M.takthinweis(p, M.HINWEIS_BIS + dt.timedelta(days=1))
    for name, text, soll_leer in [("einen Tag vor der Frist", davor, False),
                                  ("am Tag der Frist", amtag, False),
                                  ("einen Tag nach der Frist", danach, True)]:
        gut = (text.strip() == "") == soll_leer
        print(f"  {'OK ' if gut else 'FEHLER'} {name}: "
              f"{'leer' if not text.strip() else str(len(text)) + ' Zeichen'}")
        fehler += 0 if gut else 1

    # Gegenprobe: Misst die Pruefung ueberhaupt? Ein Kasten ohne Frist
    # muesste hier auffallen.
    if M.takthinweis(p, dt.date(2099, 1, 1)).strip():
        print("  FEHLER Gegenprobe: der Kasten steht auch 2099 noch da.")
        fehler += 1
    else:
        print("  OK  Gegenprobe: 2099 ist er weg.")

    # Die Zeilen muessen aufgehen, sonst zerfaellt die Tabelle in Outlook.
    auf, zu = html.count("<tr"), html.count("</tr>")
    gut = auf == zu
    print(f"  {'OK ' if gut else 'FEHLER'} Tabellenzeilen: {auf} auf, {zu} zu")
    fehler += 0 if gut else 1

    print(f"\n{fehler} Abweichung(en).")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
