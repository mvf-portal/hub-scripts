#!/usr/bin/env python3
"""Prueft eine fertige Newsletter-Ausgabe, bevor sie terminiert wird.

Warum es diese Datei gibt: Der Versand ist der einzige Schritt der ganzen
Kette, der sich nicht zuruecknehmen laesst. Seit dem 18.08.2026 terminiert
`mailchimp_entwurf.py` die Kampagne selbst, statt auf eine Freigabe von Hand zu
warten - der Preis dafuer ist diese Pruefung.

**Was sie leistet und was nicht.** Sie faengt *mechanischen* Unfug: fehlende
Felder, stehengebliebene Platzhalter, erfundene Zeitschriften, englisch
gebliebene Zusammenfassungen, doppelte Studien, ein leeres Empfaengersegment.
Sie faengt *nicht* die Zusammenfassung, die fluessig klingt und die Studie
falsch wiedergibt - dafuer gibt es das Veto-Fenster zwischen Terminierung und
Versand. Wer hier eine Pruefung ergaenzt, sollte sich vorher fragen, in welche
der beiden Klassen sie faellt; die zweite ist maschinell nicht zu haben.

Schlaegt auch nur eine Pruefung an, wird **nicht terminiert**. Der Entwurf
bleibt liegen, und der Grund steht in versand-status.json. Lieber ein Tag ohne
Newsletter als ein falscher - so hat der Herausgeber es am 18.08.2026 entschieden.

**Zwei Stufen, seit dem 24.08.2026.** Ein Formfehler an einer einzelnen Studie
soll nicht sieben einwandfreie mitnehmen: `vorpruefung()` sortiert solche
Studien aus, bevor die Ausgabe gebaut wird, und `pruefe()` entscheidet danach
ueber die Ausgabe als Ganzes. Wer eine Pruefung ergaenzt, gehoert in
`pruefe_studie()`, wenn sie eine Studie betrifft, und in `pruefe()`, wenn sie
die Ausgabe betrifft - Empfaengersegment, HTML, Dubletten und die Abgleiche
gegen PubMed sind Letzteres und stoppen weiterhin hart.

Alleine aufrufbar, dann prueft sie den aktuellen Archivstand ohne Mailchimp:
    py scripts/torwaechter.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request

ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Gesucht wird nicht das Deutsche, sondern das Englische.
#
# Der erste Anlauf verlangte, dass die Zusammenfassung eines von fuenfzehn
# deutschen Funktionswoertern enthaelt. Das ging am 18.08.2026 im ersten
# Echtlauf schief: "Systematische Uebersicht identifizierte 81 Publikationen
# mit 53 Interventionen zur Foerderung kritischer Gesundheitskompetenz;
# Schwerpunkt lag auf Appraisal-Faehigkeiten fuer informierte Entscheidungen in
# Bildungseinrichtungen." - tadelloses Deutsch, aber ohne der/die/das/und/bei.
# Eine Wortliste kann Deutsch nicht beweisen; ein deutscher Satz darf jedes
# einzelne Wort vermeiden.
#
# Der Fehlerfall ist ohnehin ein anderer: nicht "zu wenig Deutsch", sondern ein
# stehengebliebener englischer Abstract. Den erkennt man sicher an englischen
# Funktionswoertern, die im Deutschen praktisch nicht vorkommen. Ab drei
# Treffern ist es kein Zufall mehr - einzelne Fachwendungen wie "shared
# decision making" oder "teach-back" bleiben damit unbeanstandet.
#
# Gezaehlt wird ueber Titel, Zusammenfassung UND Ergebnis zusammen. Bis zum
# 09.09.2026 sah die Pruefung nur die Zusammenfassung, und an diesem Morgen
# lieferte das Modell dem Versorgungsforschungs-Portal die GANZE Ausgabe auf
# Englisch: sieben englische Titel, sieben englische Zusammenfassungen, sieben
# englische Ergebnisse. Beanstandet wurden drei - die uebrigen vier hatten in
# ihrer Zusammenfassung zufaellig nur zwei Funktionswoerter. Dass die Ausgabe
# trotzdem stoppte, lag allein daran, dass drei von sieben ueber ANTEIL_AUS_MAX
# liegen; bei zwei Beanstandungen waeren fuenf englische Studien versendet
# worden. Ueber alle drei Felder gezaehlt reissen sechs der sieben die
# Schwelle, waehrend der deutsche Bestand (152 Studien, nachgemessen) nie ueber
# zwei Treffer kommt.
ENGLISCH = re.compile(r"\b(the|of|and|was|were|with|that|this|from|"
                      r"have|has|been|their|its|which|among|between)\b",
                      re.IGNORECASE)
ENGLISCH_FELDER = ("title", "sum", "result")
ENGLISCH_SCHWELLE = 3
# Zweite, niedrigere Schwelle - sie gilt nicht der einzelnen Studie, sondern
# der Ausgabe: Reisst sie JEDE Studie, ist nicht eine Zusammenfassung
# missglueckt, sondern der Lauf als Ganzes auf Englisch herausgekommen.
# Einzeln waere sie zu scharf (vier von 152 deutschen Studien kommen auf zwei
# Treffer, meist durch Eigennamen wie "China Health and Retirement
# Longitudinal Study"); dass ausnahmslos alle Studien einer deutschen Ausgabe
# darauf kommen, ist praktisch ausgeschlossen.
ENGLISCH_AUSGABE_SCHWELLE = 2
# Das Ergebnisfeld muss etwas aussagen - aber NICHT zwingend eine Zahl
# enthalten. Qualitative Interviewstudien und Expertenpapiere sind seit dem
# 18.08.2026 ausdruecklich zugelassen (Entscheidung des Herausgebers); eine
# Ziffernpflicht haette an diesem Tag zwei von fuenf Hubs gestoppt, obwohl mit
# den Ausgaben nichts verkehrt war. Geprueft wird deshalb auf Substanz, nicht
# auf Zahlen: Ein Ergebnisfeld mit "n. a." oder drei Woertern faellt durch,
# eine ausformulierte qualitative Kernaussage nicht.
MIN_ERGEBNIS = 60
PFLICHT = ("pmid", "title", "sum", "result", "journal", "year")


def _esummary(pmids: list[str]) -> dict:
    """Zeitschrift und Jahr direkt bei PubMed nachschlagen."""
    daten = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(pmids),
                                    "retmode": "json"}).encode()
    with urllib.request.urlopen(ESUMMARY, data=daten, timeout=60) as r:
        return json.load(r).get("result", {})


# Anteil der Gesamtliste, ab dem eine Ausgabe nicht mehr als Segment gelten
# kann. Ein Studien-Newsletter richtet sich an die Abonnenten EINES Hubs; wer
# fast die ganze Hausliste erreicht, hat sein Segment verloren - etwa weil eine
# Gruppenkennung nicht mehr stimmt und Mailchimp auf "alle" zurueckfaellt.
# Bewusst hoch angesetzt: Ein falscher Stopp kostet eine Ausgabe, ein
# versehentlicher Vollversand an ueber 10.000 Menschen ist nicht zurueckholbar.
ANTEIL_MAX = 0.9


def _englisch(e: dict) -> int:
    """Englische Funktionswoerter in Titel, Zusammenfassung und Ergebnis."""
    text = " ".join(str(e.get(f, "")) for f in ENGLISCH_FELDER)
    return len(ENGLISCH.findall(text))


def pruefe_studie(e: dict, kopf: str) -> list[str]:
    """Was an einer EINZELNEN Studie zu beanstanden ist - ohne Netz.

    Herausgeloest am 24.08.2026, damit `vorpruefung()` dieselben Regeln zum
    Aussortieren nutzen kann, die `pruefe()` zum Stoppen nutzt. Zwei getrennte
    Regelsaetze waeren mit Sicherheit irgendwann auseinandergelaufen.
    """
    m: list[str] = []
    for feld in PFLICHT:
        if not str(e.get(feld, "")).strip():
            m.append(f"{kopf}: Feld '{feld}' ist leer")
    if not str(e.get("pmid", "")).isdigit():
        # Den Wert mit repr() zeigen, nicht nur behaupten, er sei keine Zahl.
        # Am 15.09.2026 lautete die Meldung "Studie 20 (PMID 42726202): PMID
        # ist keine Zahl" - der Kopf druckt bereinigt, und so sah die Ursache
        # aus wie ein Widerspruch. Mit repr() steht da ' 42726202', und das
        # fuehrende Leerzeichen ist auf einen Blick zu sehen.
        m.append(f"{kopf}: PMID ist keine Zahl: "
                 f"{str(e.get('pmid', ''))!r}")
    text = " ".join(str(e.get(f, "")) for f in ("title", "sum", "result"))
    if "{{" in text or "}}" in text:
        m.append(f"{kopf}: unersetzter Platzhalter im Text")
    # Eckige Klammern am Feldanfang sind die Notbremse des Modells: Statt
    # eine unbrauchbare Arbeit zu ueberspringen, schreibt es hinein, warum
    # sie unbrauchbar ist - "[Nicht verwertbar - Berichtigung ohne eigene
    # Ergebnisse]". Das gehoert nie in eine Ausgabe.
    if any(str(e.get(f, "")).strip().startswith("[")
           for f in ("title", "sum", "result", "transfer")):
        m.append(f"{kopf}: Feld beginnt mit einer Klammerbemerkung statt "
                 f"mit Inhalt")
    if len(str(e.get("result", "")).strip()) < MIN_ERGEBNIS:
        m.append(f"{kopf}: Ergebnisfeld ist mit "
                 f"{len(str(e.get('result', '')).strip())} Zeichen zu duenn")
    if len(str(e.get("sum", ""))) < 80:
        m.append(f"{kopf}: Zusammenfassung ist verdaechtig kurz "
                 f"({len(str(e.get('sum', '')))} Zeichen)")
    treffer = _englisch(e)
    if treffer >= ENGLISCH_SCHWELLE:
        m.append(f"{kopf}: Titel, Zusammenfassung und Ergebnis enthalten "
                 f"{treffer} englische Funktionswoerter - vermutlich der "
                 f"englische Abstract")
    if not 20 <= len(str(e.get("title", ""))) <= 200:
        m.append(f"{kopf}: Titellaenge ausserhalb 20-200 Zeichen "
                 f"({len(str(e.get('title', '')))})")
    return m


# Wie viel einer Ausgabe hoechstens still verschwinden darf, bevor stattdessen
# die ganze Ausgabe stoppt. Faellt mehr weg, ist nicht eine Studie missglueckt,
# sondern der Lauf - und dann soll ein Mensch hinsehen.
ANTEIL_AUS_MAX = 1 / 3
MIN_BEHALTEN = 2


def vorpruefung(studien: list[dict]) -> tuple[list[dict], list[str]]:
    """Einzelne missglueckte Studien aussortieren, bevor die Ausgabe gebaut wird.

    Warum es das gibt: Am 24.08.2026 stoppte das Pflege-Portal, weil EIN
    deutscher Titel 205 statt der erlaubten 200 Zeichen hatte. Sieben
    einwandfreie Studien gingen deshalb nicht raus - und weil der offene
    Bestand sich am letzten *versendeten* Entwurf ausrichtet, waere derselbe
    Titel am naechsten Morgen wieder dabei gewesen. Ein Formfehler an einer
    Studie hatte das Portal dauerhaft blockiert.

    Aussortieren statt stoppen ist die konservative Richtung: Es geht nie etwas
    Falsches raus, nur weniger. Geprueft wird hier bewusst **ohne Netz** - die
    Abgleiche gegen PubMed (Zeitschrift, Jahr, Berichtigungen) bleiben in
    `pruefe()` und stoppen weiterhin hart. Sie sind kein Formfehler an einer
    Studie, sondern der Hinweis auf einen Rueckfall im Mechanismus.

    Rueckgabe: (was bleibt, Meldungen ueber das Aussortierte). Bleibt zu wenig
    uebrig, kommt die Liste unveraendert zurueck - dann stoppt `pruefe()`.
    """
    behalten: list[dict] = []
    weg: list[str] = []
    for i, e in enumerate(studien, 1):
        m = pruefe_studie(e, f"Studie {i} (PMID {e.get('pmid', '?')})")
        if m:
            weg.append("; ".join(m))
        else:
            behalten.append(e)
    if not weg:
        return studien, []
    if len(behalten) < MIN_BEHALTEN or len(weg) > len(studien) * ANTEIL_AUS_MAX:
        return studien, []
    return behalten, weg


def pruefe(studien: list[dict], html: str = "", empfaenger: int | None = None,
           gegen_pubmed: bool = True, listengroesse: int | None = None,
           gleichnamige: list[tuple[str, str]] | None = None) -> list[str]:
    """Alle Beanstandungen als Liste. Leere Liste heisst: terminieren."""
    m: list[str] = []
    if not studien:
        return ["keine Studien in der Ausgabe"]

    for i, e in enumerate(studien, 1):
        m += pruefe_studie(e, f"Studie {i} (PMID {e.get('pmid', '?')})")

    # Die ganze Ausgabe auf Englisch - der Fall vom 09.09.2026. Er gehoert
    # hierher und nicht in vorpruefung(): Was jede einzelne Studie betrifft,
    # ist kein Formfehler an einer Studie, den man aussortieren koennte,
    # sondern ein misslungener Lauf. Da bleibt nur der harte Stopp.
    if all(_englisch(e) >= ENGLISCH_AUSGABE_SCHWELLE for e in studien):
        m.append(f"jede der {len(studien)} Studien enthaelt mindestens "
                 f"{ENGLISCH_AUSGABE_SCHWELLE} englische Funktionswoerter - "
                 f"die Ausgabe ist vermutlich insgesamt englisch geblieben")

    pmids = [str(e.get("pmid", "")) for e in studien]
    doppelt = {p for p in pmids if pmids.count(p) > 1}
    if doppelt:
        m.append(f"dieselbe Studie mehrfach in der Ausgabe: {', '.join(sorted(doppelt))}")

    # Zeitschrift und Jahr gegen PubMed. Bis August 2026 stammten beide aus der
    # Modellantwort und waren entsprechend geraten - aus NPJ Prim Care Respir
    # Med wurde Nat Commun. Die Quelle ist seither fetch_meta(); diese Pruefung
    # sorgt dafuer, dass ein Rueckfall auffaellt, bevor er versendet wird.
    if gegen_pubmed and all(p.isdigit() for p in pmids):
        try:
            res = _esummary(pmids)
            for e in studien:
                d = res.get(str(e["pmid"]))
                if not d or "error" in d:
                    m.append(f"PMID {e['pmid']}: bei PubMed nicht auffindbar")
                    continue
                echt = (d.get("source") or "").strip().lower()
                ist = str(e.get("journal", "")).strip().lower()
                if echt and ist and echt != ist:
                    m.append(f"PMID {e['pmid']}: Zeitschrift '{e['journal']}' "
                             f"stimmt nicht mit PubMed ('{d.get('source')}')")
                # Zulaessig ist JEDES Jahr, das PubMed selbst fuehrt - das des
                # Hefts (pubdate) und das der Vorabveroeffentlichung
                # (epubdate).
                #
                # Am 11.09.2026 stoppte der KI-Hub an PMID 42717858: pubdate
                # "2026 Sep", epubdate "2025 Jul 26". Der Torwaechter verglich
                # gegen das Heftjahr und meldete "Jahr 2025 statt 2026" - ein
                # Fehlalarm, und zwar ein harter Stopp, der die ganze Ausgabe
                # mitnahm.
                #
                # Die Ursache ist ein Regelwiderspruch: fetch_meta() leitet
                # `year` aus der GENAUESTEN der beiden Angaben ab, hier also
                # aus dem 26.07.2025 mit Tag. Diese Pruefung verglich dann die
                # eine PubMed-Angabe gegen die andere. Sie stammt aus der Zeit,
                # als `year` noch aus der Modellantwort kam; seit das Feld
                # maschinell aus esummary entsteht, kann sie dort ueberhaupt
                # keinen Modellfehler mehr finden - nur noch den normalen
                # Abstand zwischen Online-first und Heft.
                #
                # Was bleibt, ist der Fall, um den es ging: ein Jahr, das
                # PubMed ueberhaupt nicht kennt. Das ist weiter ein harter
                # Stopp.
                jahre = {j for j in ((d.get("pubdate") or "")[:4],
                                     (d.get("epubdate") or "")[:4]) if j.isdigit()}
                if jahre and str(e.get("year", "")) not in jahre | {""}:
                    m.append(f"PMID {e['pmid']}: Jahr {e.get('year')} statt "
                             f"{' oder '.join(sorted(jahre))}")
                # Berichtigungen und Ruecknahmen tragen keine eigenen
                # Ergebnisse. Die Abfrage schliesst sie aus; falls doch eine
                # durchkommt, faellt sie hier auf - und zwar unter ihrem
                # richtigen Namen, nicht als "Zusammenfassung zu kurz".
                typen = {t.lower() for t in (d.get("pubtype") or [])}
                schlecht = typen & {"published erratum", "retraction of publication",
                                    "retracted publication", "duplicate publication"}
                if schlecht:
                    m.append(f"PMID {e['pmid']}: ist laut PubMed "
                             f"{', '.join(sorted(schlecht))} - keine eigene Studie")
        except Exception as fehler:              # Netz weg, PubMed langsam
            m.append(f"Abgleich mit PubMed nicht moeglich: {fehler}")

    if html:
        if "{{" in html:
            m.append("unersetzter Platzhalter im Newsletter-HTML")
        if len(html) < 2000:
            m.append(f"Newsletter-HTML ist mit {len(html)} Zeichen zu kurz")
        fehlend = [e["pmid"] for e in studien if str(e.get("pmid", "")) not in html]
        if fehlend:
            m.append(f"im HTML fehlen Studien: {', '.join(map(str, fehlend))}")

    if empfaenger is not None and empfaenger < 1:
        m.append("das Empfaengersegment ist leer - niemand wuerde die Ausgabe bekommen")
    if empfaenger and listengroesse and empfaenger >= ANTEIL_MAX * listengroesse:
        m.append(f"das Empfaengersegment umfasst {empfaenger} von {listengroesse} "
                 f"Adressen der ganzen Zielgruppe - das ist kein Segment mehr")

    # Hoechstens EINE Ausgabe je Hub und Tag - die haerteste Regel dieser
    # Datei, denn ein Doppelversand trifft jeden Empfaenger unmittelbar.
    #
    # Am 31.08.2026 ist genau das passiert: Die Doppelpruefung in
    # mailchimp_entwurf.py holte nur Kampagnen im Zustand "Entwurf", eine
    # bereits TERMINIERTE war fuer sie unsichtbar, und drei Laeufe desselben
    # Morgens legten drei Kampagnen mit demselben Titel an. Alle drei gingen
    # um 10:00 hinaus. Jene Luecke ist geschlossen; diese Pruefung ist die
    # zweite Linie dahinter und prueft nicht die Absicht, sondern den Zustand
    # bei Mailchimp: Steht dort schon etwas fuer heute, wird nicht terminiert.
    #
    # Uebergeben wird (Kennung, Zustand) je gleichnamiger Kampagne, die
    # terminiert ist, gerade hinausgeht oder schon draussen ist. Entwuerfe
    # zaehlen nicht - die verschicken nichts.
    if gleichnamige:
        wo = ", ".join(f"{kid} ({stand})" for kid, stand in gleichnamige)
        m.append(f"fuer heute liegt bei Mailchimp schon eine Ausgabe dieses Hubs "
                 f"vor: {wo} - eine zweite waere ein Doppelversand")

    return m


def main() -> int:
    try:
        alle = json.load(open("studien-archiv.json", encoding="utf-8"))
    except FileNotFoundError:
        print("studien-archiv.json nicht gefunden - im Portalverzeichnis aufrufen.")
        return 2
    tage = sorted({e.get("aufgenommen") or e.get("added") for e in alle}, reverse=True)
    neueste = [e for e in alle
               if (e.get("aufgenommen") or e.get("added")) == tage[0]] if tage else []
    m = pruefe(neueste)
    print(f"{len(neueste)} Studien vom {tage[0] if tage else '?'} geprueft.")
    for x in m:
        print("  ! " + x)
    print("Ergebnis:", "TERMINIEREN" if not m else "GESTOPPT")
    return 0 if not m else 1


if __name__ == "__main__":
    sys.exit(main())
