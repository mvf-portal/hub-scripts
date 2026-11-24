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

**Drei Arten von Unterstuetzung** (ideell seit 24.11.2026). Ein Eintrag
traegt optional `art`:

    {n:"...", logo:"...", u:"..."}                   Sponsor
    {n:"...", logo:"...", u:"...", art:"koop"}       Medienpartner
    {n:"...", logo:"...", u:"...", art:"ideell"}     Ideeller Foerderer

Der Unterschied ist keine Formsache, sondern der Wortlaut der Kennzeichnung.
Ein Sponsor traegt Betrieb und Hosting; eine Medienkooperation praesentiert
den Hub, und dann muss der Satz zur Unabhaengigkeit aus dem Kleingedruckten
heraus. Ein ideeller Foerderer zahlt NICHTS - wer ihn in eine der beiden
anderen Arten setzt, laesst das Portal eine Geldleistung behaupten, die es
nicht gibt. Alle Wortlaute stehen hier und nirgends sonst - wer sie an einer
Stelle aendert, aendert sie ueberall.

**Ein Hub kann zwei Eintraege haben** (Peter, 24.11.2026): einen ideellen
Foerderer und einen zahlenden Partner. Jede Art bekommt deshalb ihre eigene
Zeile, auf der Seite wie im Newsletter.

**Startdatum.** Freiwillig `seit:"JJJJ-MM-TT"` - der Eintrag zaehlt erst ab
diesem Tag. `lade()` liefert ihn trotzdem, damit man sieht, was ansteht;
`gruppen()` und alles, was daraus einen Text macht, lassen ihn bis dahin weg.
Der Grund ist Erfahrung: Ein Handgriff, der an einem bestimmten Tag faellig
ist, ist ein Handgriff, den jemand vergisst.
"""
from __future__ import annotations

import datetime
import pathlib
import re

BLOCK = re.compile(r"SPONSOR-BLOCK-START.*?SPONSOR-BLOCK-ENDE", re.S)
# Ein Eintrag: {n:"...", logo:"...", u:"...", art:"koop", seit:"2026-12-01"} -
# Schluessel ohne Anfuehrungszeichen, wie ueberall in dieser Datei. Gelesen wird
# als Schluessel-Wert-Paare und NICHT in fester Feldreihenfolge: Mit zwei
# freiwilligen Feldern waere die Reihenfolge eine Falle, die beim naechsten
# Feld wieder zuschlaegt - sie fiele nicht als Fehler auf, sondern als
# stillschweigend verschwundener Sponsor.
EINTRAG = re.compile(r"\{[^{}]*\}")
FELD = re.compile(r'(\w+)\s*:\s*"([^"]*)"')

SPONSOR, KOOP, IDEELL = "sponsor", "koop", "ideell"
# Die Reihenfolge, in der die Arten erscheinen: die weitergehende Zusage zuerst.
ARTEN = (KOOP, SPONSOR, IDEELL)

# Die Wortlaute. Einmal hier, damit Seite, Newsletter und Downloads dasselbe
# sagen - und damit eine Aenderung nicht an drei Stellen nachgezogen werden muss.
VOR = {SPONSOR: "Gesponsert von",
       KOOP: "In einer Medienkooperation praesentiert von",
       IDEELL: "Ideeller Foerderer des Portals"}
ZUSATZ = {SPONSOR: "ohne Einfluss auf die Inhalte",
          KOOP: "Auswahl und Darstellung der Studien, der Datenbanken und aller "
                "weiteren Inhalte erfolgen redaktionell unabhaengig. "
                "Der Medienpartner nimmt darauf keinen Einfluss.",
          IDEELL: "ohne finanzielle Beteiligung an Betrieb und Hosting und ohne "
                  "Einfluss auf die Inhalte"}
# Die Fassungen mit Umlauten - Python-Quelltext bleibt in diesem Haus ASCII,
# ausgeliefert wird natuerlich deutsch.
VOR[KOOP] = VOR[KOOP].replace("praesentiert", "pr\u00e4sentiert")
VOR[IDEELL] = VOR[IDEELL].replace("Foerderer", "F\u00f6rderer")
ZUSATZ[KOOP] = ZUSATZ[KOOP].replace("unabhaengig", "unabh\u00e4ngig")


def lade(basis: str | pathlib.Path = ".") -> list[dict]:
    """Alle Sponsoren des Portals, auch die noch nicht begonnenen.

    Wer nur die laufenden will, nimmt `gruppen()` - oder filtert selbst mit
    `laeuft()`. Hier wird bewusst nichts weggelassen, damit ein Blick in die
    Liste zeigt, was ansteht.
    """
    seite = pathlib.Path(basis) / "index.html"
    if not seite.exists():
        return []
    m = BLOCK.search(seite.read_text(encoding="utf-8"))
    if not m:
        return []
    alle = []
    for roh in EINTRAG.findall(m.group(0)):
        f = dict(FELD.findall(roh))
        if not f.get("n"):
            continue
        alle.append({"n": f["n"], "logo": f.get("logo", ""), "u": f.get("u", ""),
                     "art": f.get("art") or SPONSOR, "seit": f.get("seit", "")})
    return alle


def laeuft(s: dict, stichtag: str = "") -> bool:
    """Gilt dieser Eintrag heute schon?

    Verglichen wird als Zeichenkette, was beim Format JJJJ-MM-TT der
    Datumsvergleich ist - und ohne die Zeitzonenfalle, die ein echtes
    Datumsobjekt hier mitbraechte.
    """
    if not s.get("seit"):
        return True
    return (stichtag or datetime.date.today().isoformat()) >= s["seit"]


def gruppen(basis: str | pathlib.Path = ".") -> list[tuple[str, list[dict]]]:
    """Die Eintraege nach Art, Medienkooperation zuerst - leere Arten fallen weg.

    Gemischt ist seit dem 24.11.2026 der vorgesehene Fall: Ein Hub kann einen
    ideellen Foerderer UND einen zahlenden Partner haben. Jede Art bekommt dann
    ihre eigene Zeile; sie in einen Satz zu zwingen hiesse, eine der beiden
    Zusagen falsch wiederzugeben.

    Eintraege mit einem noch nicht erreichten `seit` bleiben weg.
    """
    alle = [s for s in lade(basis) if laeuft(s)]
    return [(art, [s for s in alle if s["art"] == art])
            for art in ARTEN if any(s["art"] == art for s in alle)]


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
        # Kein zweiter Punkt hinter einem Namen, der schon auf einem endet:
        # "Retina plus e.V.." waere sonst die Folge, und zwar in jedem
        # Newsletter und jeder Download-Datei.
        return f"{VOR[KOOP]} {n}{'' if n.endswith('.') else '.'} {ZUSATZ[KOOP]}"
    if art == IDEELL:
        return f"{VOR[IDEELL]}: {n} ({ZUSATZ[IDEELL]})."
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
    KENNUNG = {KOOP: "Medienpartner", SPONSOR: "Sponsor",
               IDEELL: "Ideeller Foerderer"}
    for s in lade(ort):
        kennung = KENNUNG.get(s["art"], s["art"])
        stand = "" if laeuft(s) else f'   (erst ab {s["seit"]})'
        print(f'{kennung:<20}{s["n"]:<30} {s["logo"]:<28} {s["u"]}{stand}')
    print("Fusszeile:", zeile(ort) or "(kein Unterstuetzer - Hinweis entfaellt)")
