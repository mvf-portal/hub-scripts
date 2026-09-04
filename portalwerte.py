#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Die Werte dieses Portals - zur Laufzeit aus portal.json.

Bis zum 04.09.2026 standen diese Werte als Platzhalter in drei Skripten und
wurden von `neues-portal.py` beim Erzeugen des Portals eingesetzt: 24 Stellen
mit `{{DOMAIN}}`, `{{TITEL}}`, `{{MC_PRAEFIX}}` und so fort. Genau das hat die
drei daran gehindert, gemeinsam genutzt zu werden - eine Datei mit
Platzhaltern ist keine gemeinsame Datei.

Die Werte selbst mussten dafuer nirgends neu erfunden werden: `portal.json`
liegt in jedem Portal und enthaelt sie alle. Sie werden jetzt von dort gelesen,
statt einmal beim Erzeugen eingesetzt zu werden.

**Das aendert auch, was ein Portal ist.** Wer bisher den Newsletter-Praefix
aendern wollte, musste das Skript anfassen; jetzt genuegt `portal.json`. Und
ein Tippfehler dort faellt sofort auf, statt erst in der naechsten Ausgabe.

Gelesen wird gegen das Arbeitsverzeichnis - dieselbe Annahme, unter der alle
Skripte der Reihe `index.html` und `studien-archiv.json` ansprechen. Laeuft ein
Skript von woanders, sagt die Fehlermeldung genau das.
"""
from __future__ import annotations

import json
import pathlib

_DATEI = pathlib.Path("portal.json")

try:
    _W: dict = json.loads(_DATEI.read_text(encoding="utf-8"))
except FileNotFoundError:
    raise SystemExit(
        "portal.json nicht gefunden. Die Skripte der Reihe laufen im "
        "Wurzelverzeichnis des Portals - dort liegen auch index.html und "
        "studien-archiv.json. Aufruf also z. B. "
        "`python scripts/gemeinsam/build_newsletter.py` aus dem Portal heraus, "
        "nicht aus scripts/."
    ) from None


def wert(name: str, standard=None):
    """Ein Feld aus portal.json. Fehlt es ohne Standardwert, bricht der Lauf ab.

    Ein fehlender Wert ist kein Fall fuer einen leeren String: Ein Newsletter
    mit leerem Praefix erkennt seine eigenen Kampagnen nicht wieder, und das
    faellt erst auf, wenn zwei Portale sich gegenseitig die Ausgaben
    ueberschreiben.
    """
    if name in _W:
        return _W[name]
    if standard is not None:
        return standard
    raise SystemExit(f"portal.json: Feld {name} fehlt. Ohne diesen Wert laesst "
                     f"sich die Ausgabe nicht eindeutig diesem Portal zuordnen.")


DOMAIN = wert("DOMAIN")
REPO = wert("REPO")
TITEL = wert("TITEL")
TITEL_KURZ = wert("TITEL_KURZ")
THEMA_ASCII = wert("THEMA_ASCII")
DATEI_PRAEFIX = wert("DATEI_PRAEFIX")
MC_PRAEFIX = wert("MC_PRAEFIX")
MC_GRUPPE_NAME = wert("MC_GRUPPE_NAME")
# In portal.json steht die Tag-Nummer als Zeichenkette ("0", wenn kein Tag
# angelegt ist); das Skript rechnet mit einer Zahl.
MC_TAG_ID = int(wert("MC_TAG_ID", 0) or 0)
