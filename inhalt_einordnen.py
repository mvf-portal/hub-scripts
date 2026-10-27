#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zweiter Durchgang: die Funde einordnen und nach Schwere sortieren.

    py inhalt_einordnen.py              # alle Beanstandungen einordnen
    py inhalt_einordnen.py --probe 40   # erst einmal vierzig

Der erste Durchgang (`inhalt_pruefen.py`) hat am 26.10.2026 **3.006 von
5.309** Eintraegen beanstandet - 56 Prozent. Das ist keine Fehlerquote,
sondern ein zu enger Massstab: Er verlangt, dass jede Aussage im deutschen
Text im Abstract steht. Eine Zusammenfassung darf aber kuerzen, aus dem
Volltext schoepfen und im Aktiv titeln.

Dieser Durchgang trennt, was dort zusammenliegt:

  **sachfehler**  Eine Zahl, ein Begriff, eine Population, eine Studienart
                  stimmt nicht. "weniger Vorhofsohren" statt "weniger
                  LAA-Lappen". Gehoert berichtigt.
  **kausal**      Aktivsatz, wo die Quelle "assoziiert mit" sagt. Keine
                  Verwechslung, sondern Schlagzeilenkonvention - eine
                  redaktionelle Frage, und zwar EINE statt dreitausend.
  **ueberdehnt**  Die Aussage ist breiter als der Beleg, ohne kausal zu
                  sein (Teilgruppe als Ganzes, Einzelbefund als Regel).
  **kein_fehler** Beim zweiten Lesen gedeckt.

**Der Prueferer sieht die erste Begruendung NICHT.** Er bekommt denselben
Stoff noch einmal - deutscher Text und Abstract - und urteilt neu. Saehe er
das erste Urteil, nickte er es ab; dann waere dieser Durchgang kein zweiter
Blick, sondern eine Unterschrift unter den ersten. Wie viele er freigibt,
ist deshalb zugleich die Fehlalarmquote des ersten Durchgangs.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import os
import pathlib
import sys
import threading
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
from inhalt_pruefen import MODELL, PARALLEL, abstracts, archive  # noqa: E402

BEFUND = HIER / "inhalt-befund.json"
EINORDNUNG = HIER / "inhalt-einordnung.json"

AUFTRAG = """Du beurteilst, ob eine deutsche Zusammenfassung einer
wissenschaftlichen Arbeit eine Aussage enthaelt, die ihre Quelle nicht
hergibt. Du bekommst den Originaltitel, den Abstract und den deutschen Text
eines Fachportals.

Ordne in GENAU EINE Kategorie ein:

"sachfehler" - Eine Angabe ist schlicht falsch: eine Zahl, eine Menge, ein
  Begriff, eine Population, eine Studienart, eine Richtung. Beispiele: "468
  Patienten", wo 448 gepoolt wurden; "weniger Vorhofsohren", wo es weniger
  Lappen des Vorhofohrs sind; "randomisiert", wo es eine Beobachtung ist.

"kausal" - Der deutsche Text sagt im Aktiv, was die Quelle als Assoziation
  formuliert ("X senkt Y" statt "X war assoziiert mit niedrigerem Y").
  Die Zahlen und Begriffe stimmen, nur die Sprache ist staerker.

"ueberdehnt" - Die Aussage ist breiter als der Beleg, ohne kausal zu sein:
  eine Teilgruppe als Ganzes ausgegeben, ein Einzelbefund als Regel, eine
  Einschraenkung weggelassen, die das Ergebnis traegt.

"kein_fehler" - Der deutsche Text ist gedeckt. Kuerzen, Auslassen, freier
  formulieren und deutsche Fachsprache sind KEIN Fehler. Eine Angabe, die
  im Abstract fehlt, kann aus dem Volltext stammen - das allein ist kein
  Fehler.

Dazu die Schwere:

"hoch"    - steht im TITEL, oder es geht um das Hauptergebnis, eine Zahl
            oder die Studienart.
"mittel"  - steht in der Zusammenfassung oder der Ergebniszeile und
            veraendert, was der Leser mitnimmt.
"niedrig" - Nebensache; wer die Arbeit liest, merkt keinen Unterschied.

Antworte als JSON, sonst nichts:
{"art": "sachfehler"|"kausal"|"ueberdehnt"|"kein_fehler",
 "schwere": "hoch"|"mittel"|"niedrig",
 "stelle": "woertliches Zitat aus dem deutschen Text",
 "richtig": "was die Quelle stattdessen sagt"}

Bei "kein_fehler" bleiben stelle und richtig leer."""


def einordnen(client, eintrag: dict, quelle: dict) -> dict:
    text = (f"ORIGINALTITEL: {quelle['titel']}\n\n"
            f"ABSTRACT: {quelle['abstract'][:4000]}\n\n"
            f"---\n\nDEUTSCHER TITEL: {eintrag.get('title','')}\n\n"
            f"ZUSAMMENFASSUNG: {eintrag.get('sum','')}\n\n"
            f"ERGEBNIS: {eintrag.get('result','')}")
    antwort = client.messages.create(
        model=MODELL, max_tokens=2500,
        system=AUFTRAG,
        messages=[{"role": "user", "content": text}])
    roh = " ".join(b.text for b in antwort.content
                   if getattr(b, "type", "") == "text").strip()
    try:
        i, j = roh.index("{"), roh.rindex("}") + 1
        return json.loads(roh[i:j])
    except (ValueError, json.JSONDecodeError):
        return {"art": "unlesbar", "schwere": "", "stelle": "",
                "richtig": roh[:140]}


def main() -> int:
    p = argparse.ArgumentParser(description="Funde einordnen")
    p.add_argument("--probe", type=int, help="nur die ersten N")
    a = p.parse_args()

    if not BEFUND.exists():
        print(f"{BEFUND.name} fehlt.")
        return 1
    urteile = json.loads(BEFUND.read_text(encoding="utf-8"))["urteile"]
    offen_schluessel = [k for k, u in urteile.items()
                        if u.get("urteil") == "widerspruch"]
    if a.probe:
        offen_schluessel = offen_schluessel[:a.probe]

    # Die Eintraege aus den Archiven holen - der Pruefer braucht den Text
    # selbst, nicht mein erstes Urteil darueber.
    bestand = archive()
    nach_schluessel = {}
    for hub, liste in bestand.items():
        for x in liste:
            nach_schluessel[hub + "/" + str(x.get("pmid"))] = (hub, x)

    gewaehlt = [nach_schluessel[k] for k in offen_schluessel
                if k in nach_schluessel]
    fehlt = len(offen_schluessel) - len(gewaehlt)
    print(f"{len(gewaehlt)} Beanstandungen einzuordnen"
          + (f" ({fehlt} im Archiv nicht mehr gefunden)" if fehlt else ""))

    fertig: dict[str, dict] = {}
    if EINORDNUNG.exists():
        try:
            fertig = json.loads(EINORDNUNG.read_text(encoding="utf-8"))["einordnung"]
            fertig = {k: v for k, v in fertig.items() if v.get("art") != "unlesbar"}
            print(f"  {len(fertig)} aus einem frueheren Lauf uebernommen.")
        except (ValueError, KeyError):
            pass
    gewaehlt = [(h, x) for h, x in gewaehlt
                if (h + "/" + str(x.get("pmid"))) not in fertig]

    print("Hole die Abstracts ...")
    quellen = abstracts([str(x.get("pmid")) for _, x in gewaehlt])
    gewaehlt = [(h, x) for h, x in gewaehlt
                if quellen.get(str(x.get("pmid")), {}).get("abstract")]
    print(f"  {len(gewaehlt)} mit Abstract, es geht los.\n")

    schluessel_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not schluessel_key:
        print("ANTHROPIC_API_KEY nicht gesetzt.")
        return 1
    import anthropic
    client = anthropic.Anthropic(api_key=schluessel_key)

    sperre = threading.Lock()
    stand = {"n": 0}

    def sichern():
        EINORDNUNG.write_text(json.dumps(
            {"eingeordnet_am": time.strftime("%Y-%m-%d %H:%M"),
             "modell": MODELL, "einordnung": fertig},
            ensure_ascii=False, indent=1), encoding="utf-8")

    def eins(auftrag):
        hub, x = auftrag
        k = hub + "/" + str(x.get("pmid"))
        try:
            u = einordnen(client, x, quellen[str(x["pmid"])])
        except Exception as fehler:                    # noqa: BLE001
            u = {"art": "unlesbar", "schwere": "", "stelle": "",
                 "richtig": str(fehler)[:120]}
        u["hub"] = hub
        u["titel"] = x.get("title", "")
        with sperre:
            fertig[k] = u
            stand["n"] += 1
            if stand["n"] % 100 == 0:
                sichern()
                z = collections.Counter(v["art"] for v in fertig.values())
                print(f"  ... {stand['n']}/{len(gewaehlt)}  " + dict(z).__str__())

    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        list(pool.map(eins, gewaehlt))
    sichern()

    z = collections.Counter(v["art"] for v in fertig.values())
    gesamt = sum(z.values())
    print(f"\n{'='*74}")
    print(f"  eingeordnet     {gesamt}\n")
    for art, wort in (("sachfehler", "Sachfehler - gehoeren berichtigt"),
                      ("ueberdehnt", "ueberdehnt - Aussage breiter als der Beleg"),
                      ("kausal", "Kausalsprache - redaktionelle Frage"),
                      ("kein_fehler", "kein Fehler - erster Durchgang irrte"),
                      ("unlesbar", "ohne Urteil")):
        n = z.get(art, 0)
        print(f"  {wort:<46} {n:>4}  ({100*n//max(gesamt,1):>2} %)")

    print("\n  Nach Schwere, nur Sachfehler und ueberdehnt:")
    ernst = [v for v in fertig.values()
             if v["art"] in ("sachfehler", "ueberdehnt")]
    s = collections.Counter(v.get("schwere", "?") for v in ernst)
    for grad in ("hoch", "mittel", "niedrig"):
        print(f"    {grad:<10} {s.get(grad,0)}")
    print(f"\n  Befund: {EINORDNUNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
