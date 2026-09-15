#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Die Sponsoren dieses Portals - eine Quelle fuer Seite, Newsletter und Downloads.

Gepflegt werden sie an genau einer Stelle: im SPONSOR-Block der `index.html`.
Dieses Modul liest sie von dort, damit Newsletter und Download-Dateien
dieselbe Liste verwenden wie die Seite. Zwei Listen waeren eine Liste zu viel -
die zweite ist irgendwann die veraltete.

Dass ein Python-Skript die Angaben aus der `index.html` nachliest, ist im Haus
bereits ueblich: `vorschaltseite.py` zaehlt die Datenbanken genauso, statt sie
abzuschreiben.

Fehlt der Block oder ist die Liste leer, kommt eine leere Liste zurueck - und
jede aufrufende Stelle laesst den Hinweis dann einfach weg.

**Zwei Arten von Unterstuetzung** (seit 15.09.2026). Ein Eintrag traegt
optional `art:"koop"`:

    {n:"...", logo:"...", u:"..."}                 Sponsor
    {n:"...", logo:"...", u:"...", art:"koop"}     Medienpartner

Der Unterschied ist keine Formsache, sondern der Wortlaut der Kennzeichnung.
Ein Sponsor traegt Betrieb und Hosting; eine Medienkooperation praesentiert
den Hub, und dann muss der Satz zur Unabhaengigkeit aus dem Kleingedruckten
heraus. Beide Wortlaute stehen hier und nirgends sonst - wer sie an einer
Stelle aendert, aendert sie ueberall.
"""
from __future__ import annotations

import pathlib
import re

BLOCK = re.compile(r"SPONSOR-BLOCK-START.*?SPONSOR-BLOCK-ENDE", re.S)
# Ein Eintrag: {n:"...", logo:"...", u:"...", art:"koop"} - Schluessel ohne
# Anfuehrungszeichen, wie ueberall in dieser Datei. Die Reihenfolge der Felder
# liegt fest, weil neues-portal.py sie erzeugt; `art` ist freiwillig und fehlt
# bei den allermeisten Eintraegen.
EINTRAG = re.compile(r'\{\s*n:"([^"]*)"\s*,\s*logo:"([^"]*)"\s*,\s*u:"([^"]*)"'
                     r'(?:\s*,\s*art:"([^"]*)")?\s*\}')

SPONSOR, KOOP = "sponsor", "koop"

# Die Wortlaute. Einmal hier, damit Seite, Newsletter und Downloads dasselbe
# sagen - und damit eine Aenderung nicht an drei Stellen nachgezogen werden muss.
VOR = {SPONSOR: "Gesponsert von",
       KOOP: "In einer Medienkooperation praesentiert von"}
ZUSATZ = {SPONSOR: "ohne Einfluss auf die Inhalte",
          KOOP: "Auswahl und Darstellung der Studien, der Datenbanken und aller "
                "weiteren Inhalte erfolgen redaktionell unabhaengig. "
                "Der Medienpartner nimmt darauf keinen Einfluss."}
# Die Fassungen mit Umlauten - Python-Quelltext bleibt in diesem Haus ASCII,
# ausgeliefert wird natuerlich deutsch.
VOR[KOOP] = VOR[KOOP].replace("praesentiert", "pr\u00e4sentiert")
ZUSATZ[KOOP] = ZUSATZ[KOOP].replace("unabhaengig", "unabh\u00e4ngig")


def lade(basis: str | pathlib.Path = ".") -> list[dict]:
    """Alle Sponsoren des Portals. Leere Liste, wenn es keine gibt."""
    seite = pathlib.Path(basis) / "index.html"
    if not seite.exists():
        return []
    m = BLOCK.search(seite.read_text(encoding="utf-8"))
    if not m:
        return []
    return [{"n": n, "logo": logo, "u": u, "art": art or SPONSOR}
            for n, logo, u, art in EINTRAG.findall(m.group(0))]


def gruppen(basis: str | pathlib.Path = ".") -> list[tuple[str, list[dict]]]:
    """Die Eintraege nach Art, Medienkooperation zuerst - leere Arten fallen weg.

    Gemischt ist selten, aber moeglich: ein Hub kann einen Medienpartner UND
    einen Sponsor haben. Jede Art bekommt dann ihre eigene Zeile; sie in einen
    Satz zu zwingen hiesse, eine der beiden Zusagen falsch wiederzugeben.
    """
    alle = lade(basis)
    return [(art, [s for s in alle if s["art"] == art])
            for art in (KOOP, SPONSOR) if any(s["art"] == art for s in alle)]


def namen(basis: str | pathlib.Path = ".", liste: list[dict] | None = None) -> str:
    """Die Namen als Fliesstext: 'A', 'A und B', 'A, B und C'."""
    n = [s["n"] for s in (lade(basis) if liste is None else liste)]
    if not n:
        return ""
    if len(n) == 1:
        return n[0]
    return ", ".join(n[:-1]) + " und " + n[-1]


def satz(art: str, liste: list[dict]) -> str:
    """Der fertige Satz einer Art - die Zusage, die das Portal oeffentlich macht."""
    n = namen(liste=liste)
    if not n:
        return ""
    if art == KOOP:
        return f"{VOR[KOOP]} {n}. {ZUSATZ[KOOP]}"
    return f"{VOR[SPONSOR]} {n} ({ZUSATZ[SPONSOR]})."


def zeile(basis: str | pathlib.Path = ".") -> str:
    """Der Hinweis fuer Fusszeilen und Dateikoepfe - leer ohne Unterstuetzer.

    Der Zusatz ist keine Hoeflichkeit, sondern die Zusage, die die Seite gibt.
    Wer sie dort macht, muss sie ueberall machen.
    """
    return " ".join(satz(art, liste) for art, liste in gruppen(basis)).strip()


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ort = sys.argv[1] if len(sys.argv) > 1 else "."
    for s in lade(ort):
        kennung = "Medienpartner" if s["art"] == KOOP else "Sponsor"
        print(f'{kennung:<14}{s["n"]:<30} {s["logo"]:<28} {s["u"]}')
    print("Fusszeile:", zeile(ort) or "(kein Unterstuetzer - Hinweis entfaellt)")
