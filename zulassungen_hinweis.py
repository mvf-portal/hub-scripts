#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Die Hinweiskarte zum Zulassungsradar - laeuft in JEDEM Hub.

Gegenstueck zu `radar_hinweis.py`, und bewusst ein eigenes Skript statt eines
zweiten Blocks darin: Die Quellen sind verschieden (EMA gegen vier
Foerdergeber), die Laufzeiten auch (die EMA-Tabelle wird naechtlich
aktualisiert, der Ausschreibungsradar sucht montags und donnerstags), und ein
Ausfall der einen Seite soll die andere nicht mitnehmen.

Gelesen wird `zulassungen.json` aus dem Versorgungsforschungs-Hub - die Datei
ist die Quelle, die Seite dort nur ihre Darstellung. Geschrieben wird allein
der ZULASSUNG-Block in `index.html`.

**Acht der fuenfzehn Hubs bekommen nie etwas.** Pflege, Gesundheitskompetenz,
Klima, KI, Geschlechtersensible Medizin, Patientensicherheit und
Versorgungsforschung haben kein Krankheitsbild, auf das eine
Arzneimittelzulassung zeigt; sie stehen in `zulassungen_themen.py` gar nicht
erst. Das Skript laeuft dort trotzdem mit und schreibt eine Null - die Seite
verbirgt die Karte dann. So muss der Workflow nicht wissen, welcher Hub
welchen Zuschnitt hat.

Aufruf im Portalverzeichnis:
    py scripts/gemeinsam/zulassungen_hinweis.py
    py scripts/gemeinsam/zulassungen_hinweis.py --probe
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import urllib.error
import urllib.request

UA = "MVF-Knowledge-Hubs/1.0 (+https://knowledge-hubs.m-vf.de)"
QUELLE = ("https://raw.githubusercontent.com/"
          "mvf-portal/versorgungsforschung-portal/main/zulassungen.json")

SEITE = "index.html"
PROFIL = "portal.json"
START = "// === ZULASSUNG-BLOCK-START (taeglich von GitHub Actions ersetzt) ==="
ENDE = "// === ZULASSUNG-BLOCK-ENDE ==="


def daten_holen() -> dict:
    """Die zentrale Datei - lokal, wenn dieser Hub sie selbst schreibt."""
    hier = pathlib.Path("zulassungen.json")
    if hier.exists():
        return json.loads(hier.read_text(encoding="utf-8"))
    req = urllib.request.Request(QUELLE, headers={"User-Agent": UA,
                                                  "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def zaehlen(eintraege: list[dict]) -> dict:
    """Je Stufe eine eigene Zahl - **keine Restmenge**.

    Bis zum 22.10.2026 bekam die Karte nur zwei Zahlen: alle und Gutachten.
    Den Rest rechnete die Seite als `eigene - gutachten` und nannte ihn
    "Zulassungen". Mit der dritten und vierten Stufe wurde das falsch: Eine
    DiGA-Aufnahme und eine amerikanische Erstzulassung standen dann in einem
    deutschen Hub als EU-Zulassung da. Derselbe Fehler, der in der
    Newsletter-Rubrik im Rueckfall der Stufentabelle steckte.

    Eine Restmenge ist bei Stufen immer die falsche Bauweise: Sie behauptet,
    alles Unbekannte gehoere in die bekannteste Schublade.
    """
    def wie_viele(pruefung) -> int:
        return sum(1 for e in eintraege if pruefung(str(e.get("stufe", ""))))
    return {
        "eigene": len(eintraege),
        "zulassung": wie_viele(lambda s: s == "zulassung"),
        "gutachten": wie_viele(lambda s: s == "gutachten"),
        "fda": wie_viele(lambda s: s.startswith("fda")),
        "diga": wie_viele(lambda s: s.startswith("diga")),
    }


def block(stand: str, z: dict) -> str:
    """Die fertigen Zahlen, mehr braucht die Karte nicht.

    Anders als beim Ausschreibungsradar steht hier **die fertige Zahl** und
    keine Fristenliste: Eine Zulassung laeuft nicht ab, es gibt im Browser
    nichts nachzurechnen. Die Zahl bleibt richtig, bis der naechste Lauf sie
    fortschreibt.
    """
    return "\n".join([
        START,
        f'const ZUL_STAND = "{stand}";',
        f'const ZUL_EIGENE = {z["eigene"]};',
        f'const ZUL_GUTACHTEN = {z["gutachten"]};',
        # Seit dem 22.10.2026. Die Seite liest sie mit `typeof`-Vorbehalt:
        # Ein Portal, dessen Block noch aus der Zeit davor stammt, faellt
        # dann auf die alte Darstellung zurueck, statt leer zu bleiben.
        f'const ZUL_ZULASSUNG = {z["zulassung"]};',
        f'const ZUL_FDA = {z["fda"]};',
        f'const ZUL_DIGA = {z["diga"]};',
        ENDE,
    ])


def main() -> int:
    p = argparse.ArgumentParser(description="Zulassungshinweis dieses Hubs")
    p.add_argument("--probe", action="store_true", help="nur zeigen")
    a = p.parse_args()

    profil = json.loads(pathlib.Path(PROFIL).read_text(encoding="utf-8"))
    slug = profil.get("SLUG")
    if not slug:
        raise SystemExit(f"SLUG fehlt in {PROFIL} - nichts geaendert.")

    try:
        daten = daten_holen()
    except (urllib.error.URLError, TimeoutError, ValueError) as fehler:
        # Der Block bleibt stehen, wie er ist: Die Zahl von gestern ist naeher
        # an der Wahrheit als eine geleerte Karte. Dasselbe Verhalten wie beim
        # Radar-Hinweis, und derselbe Grund.
        print(f"Zentrale Datei nicht lesbar ({fehler}) - {SEITE} unveraendert.")
        return 0

    eintraege = [e for e in daten.get("eintraege", []) if slug in (e.get("hubs") or [])]
    z = zaehlen(eintraege)
    stand = daten.get("stand", "")

    neu = block(stand, z)
    if eintraege:
        print(f"{slug}: {z['eigene']} Eintrag/Eintraege "
              f"({z['zulassung']} EU-Zulassungen, {z['gutachten']} CHMP-Empfehlungen, "
              f"{z['fda']} FDA-Zulassungen, {z['diga']} DiGA), "
              f"Stand {stand or '?'}.")
    else:
        # Keine Warnung: Fuer acht der fuenfzehn Hubs ist das der Normalfall.
        print(f"{slug}: keine Zulassungen zu diesem Themengebiet "
              f"(Stand {stand or '?'}) - Karte bleibt verborgen.")

    if a.probe:
        print("\n" + neu + f"\n\n[Probe] {SEITE} unveraendert.")
        return 0

    seite = pathlib.Path(SEITE)
    text = seite.read_text(encoding="utf-8")
    muster = re.compile(re.escape(START) + r".*?" + re.escape(ENDE), re.DOTALL)
    if not muster.search(text):
        raise SystemExit(
            f"Marker-Block fehlt in {SEITE} - nichts geaendert. Der Block kommt "
            "aus portal-vorlage/vorlage/index.html und wird mit "
            "vorlage-abgleich.py eingespielt; von Hand eingefuegt verschwindet "
            "er beim naechsten Abgleich wieder.")
    seite.write_text(muster.sub(lambda _: neu, text), encoding="utf-8")
    print(f"{SEITE} aktualisiert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
