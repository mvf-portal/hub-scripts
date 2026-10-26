#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sind die deutschen Zusammenfassungen inhaltlich richtig?

    py inhalt_pruefen.py --faelle 42690077 42777290   # einzelne PMIDs ansehen
    py inhalt_pruefen.py --hub onkologie --probe 20   # Stichprobe eines Hubs
    py inhalt_pruefen.py --alle                       # alle 15 Archive

Die **andere** Baustelle als der PMID-Abgleich. Der prueft, ob die Nummer zur
Arbeit gehoert - und das tut sie seit dem 11.10.2026 verlaesslich
(`pmid_abgleich()` in update_studies.py, Massstab ist der abgeschriebene
Originaltitel). Hier geht es um den Fall, in dem die **Nummer stimmt und der
deutsche Text trotzdem etwas anderes sagt als die Arbeit**.

Warum das der schwerere Fall ist
--------------------------------
Es gibt keinen mechanischen Massstab. Journal, Jahr und Titel passen alle;
der Fehler steckt in einer Zahl, einer Richtung oder einer Einschraenkung,
die der Abstract so nicht hergibt. Am 12.10.2026 wurden zwei Faelle von Hand
gefunden (42690077, 42777290) - gesucht wurde nicht danach, sie fielen auf.

Geprueft wird deshalb mit einem Modell, gegen den **Abstract**, und mit einer
engen Frage: Steht im deutschen Text eine Aussage, die der Abstract nicht
hergibt oder der er widerspricht? Nicht: Ist der Text gut. Nicht: Fehlt
etwas. Wir werten nicht - wir suchen Widerspruch.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import sys
import threading
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HIER = pathlib.Path(__file__).resolve().parent
# Die Portale liegen als Schwesterordner neben hub-scripts.
WURZEL = HIER.parent

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
UA = "MVF-Knowledge-Hubs/1.0 (https://knowledge-hubs.m-vf.de)"
TAKT = 0.4
MODELL = "claude-haiku-5-5"
# Acht gleichzeitig: Die Aufrufe sind voneinander unabhaengig, und
# nacheinander waeren 5.358 Eintraege rund zwei Stunden. Nicht mehr - die
# Grenzen des Kontos teilen sich mit den naechtlichen Laeufen der Hubs.
PARALLEL = 8
BEFUND = HIER / "inhalt-befund.json"


def sichern(urteile: dict) -> None:
    """Zwischenstand schreiben. Wird waehrend des Laufs alle 50 Urteile
    aufgerufen - nicht erst am Ende, sonst kostet jeder Abbruch alles."""
    BEFUND.write_text(json.dumps(
        {"geprueft_am": time.strftime("%Y-%m-%d %H:%M"),
         "modell": MODELL, "urteile": urteile},
        ensure_ascii=False, indent=1), encoding="utf-8")


def archive() -> dict[str, list[dict]]:
    raus = {}
    for ordner in sorted(WURZEL.glob("*-portal")):
        datei = ordner / "studien-archiv.json"
        if not datei.exists():
            continue
        try:
            d = json.loads(datei.read_text(encoding="utf-8"))
        except ValueError:
            continue
        raus[ordner.name.replace("-portal", "")] = (
            d if isinstance(d, list) else d.get("studien", []))
    return raus


def abstracts(pmids: list[str]) -> dict[str, dict]:
    """Titel und Abstract zu PMIDs, in Bloecken von 100.

    `efetch` mit rettype=abstract liefert Text; das ist robuster als die
    XML-Felder, weil strukturierte Abstracts (BACKGROUND/METHODS/...) dort
    in einem Stueck stehen.
    """
    raus: dict[str, dict] = {}
    for i in range(0, len(pmids), 100):
        teil = [p for p in pmids[i:i + 100] if str(p).isdigit()]
        if not teil:
            continue
        adresse = (EUTILS + "efetch.fcgi?db=pubmed&rettype=abstract&retmode=xml&id="
                   + ",".join(teil))
        req = urllib.request.Request(adresse, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=90) as r:
            roh = r.read().decode("utf-8", "replace")
        # Ohne XML-Bibliothek: die Artikel am Markierer trennen. Die
        # Abstracts sind der einzige Teil, den wir brauchen.
        import re
        for stueck in roh.split("<PubmedArticle>")[1:]:
            m = re.search(r"<PMID[^>]*>(\d+)</PMID>", stueck)
            if not m:
                continue
            pmid = m.group(1)
            titel = re.search(r"<ArticleTitle[^>]*>(.*?)</ArticleTitle>",
                              stueck, re.S)
            teile = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>",
                               stueck, re.S)
            saeubern = lambda t: " ".join(
                re.sub(r"<[^>]+>", " ", t or "").split())
            raus[pmid] = {
                "titel": saeubern(titel.group(1) if titel else ""),
                "abstract": saeubern(" ".join(teile)),
            }
        time.sleep(TAKT)
    return raus


AUFTRAG = """Du pruefst, ob eine deutsche Zusammenfassung zu einer
wissenschaftlichen Arbeit passt. Du bekommst den englischen Originaltitel und
den Abstract, dazu den deutschen Titel, die Zusammenfassung und die
Ergebniszeile, die in einem Fachportal stehen.

**Gesucht ist allein der Widerspruch**: eine Aussage im deutschen Text, die
der Abstract nicht hergibt oder der er widerspricht. Also etwa:

- eine Zahl, die im Abstract anders steht oder gar nicht vorkommt
- eine umgekehrte Richtung (Zunahme statt Abnahme, besser statt schlechter)
- eine Studienart, die nicht stimmt (Kohorte statt Protokoll, RCT statt
  Beobachtung)
- eine Population, Dosis oder ein Zeitraum, der nicht passt
- ein Ergebnis, wo die Arbeit noch keines hat

**Nicht gesucht** ist alles andere. Kuerzen ist erlaubt, Auslassen ist
erlaubt, eine freiere Formulierung ist erlaubt, deutsche Fachsprache ist
erwuenscht. Was im Abstract steht und im deutschen Text fehlt, ist KEIN
Fehler. Stil ist kein Fehler.

Kommt eine Angabe im Abstract nicht vor, kann sie aus dem Volltext stammen -
melde sie nur, wenn sie dem Abstract WIDERSPRICHT oder wenn es eine zentrale
Aussage ist (Hauptergebnis, Studienart).

Antworte als JSON, sonst nichts:
{"urteil": "passt" | "widerspruch", "stelle": "...", "begruendung": "..."}

Bei "passt" bleiben stelle und begruendung leer. Bei "widerspruch" zitiere in
"stelle" die deutsche Formulierung woertlich und sage in "begruendung" in
einem Satz, was der Abstract stattdessen sagt."""


def urteilen(client, eintrag: dict, quelle: dict) -> dict:
    text = (f"ORIGINALTITEL: {quelle['titel']}\n\n"
            f"ABSTRACT: {quelle['abstract'][:4000]}\n\n"
            f"---\n\nDEUTSCHER TITEL: {eintrag.get('title','')}\n\n"
            f"ZUSAMMENFASSUNG: {eintrag.get('sum','')}\n\n"
            f"ERGEBNIS: {eintrag.get('result','')}")
    # **max_tokens muss das Nachdenken MITtragen.** Haiku 5.5 liefert zuerst
    # einen ThinkingBlock; bei 700 Token war das Budget davon aufgebraucht,
    # und es kam mal gar kein Text zurueck, mal ein mitten abgeschnittenes
    # JSON. Am 26.10.2026 waren so 15 von 23 Urteilen unlesbar - es sah aus
    # wie ein Modellproblem und war eine Zahl im Aufruf.
    antwort = client.messages.create(
        model=MODELL, max_tokens=2500,
        system=AUFTRAG,
        messages=[{"role": "user", "content": text}])
    # **Haiku 5.5 liefert zuerst einen ThinkingBlock.** Der Text muss ueber
    # den Typ geholt werden, nicht ueber content[0] - sonst steht dort das
    # Nachdenken und nicht das Urteil.
    roh = " ".join(b.text for b in antwort.content
                   if getattr(b, "type", "") == "text").strip()
    try:
        i, j = roh.index("{"), roh.rindex("}") + 1
        return json.loads(roh[i:j])
    except (ValueError, json.JSONDecodeError):
        return {"urteil": "unlesbar", "stelle": "", "begruendung": roh[:160]}


# --------------------------------------------------------------- Gegentest
# **Ein Pruefer, der nichts findet, ist noch kein Pruefer.** Beide bekannten
# Faelle urteilte er am 26.10.2026 als "passt" - und bei einem davon
# (42690077) komme ich beim eigenen Lesen zum selben Schluss. Ob er zu lasch
# ist oder die Eintraege in Ordnung sind, laesst sich nur entscheiden, indem
# man ihm Fehler vorlegt, die er finden MUSS.
#
# Die sechs Verderbnisse sind die Fehlerarten, die beim Zusammenfassen
# wirklich vorkommen - nicht erfundene Extremfaelle. Jede veraendert genau
# eine Sache und laesst den Rest stehen.
VERDERBEN = [
    ("Richtung gedreht", "result",
     lambda t: t.replace("verbesserte", "verschlechterte")
                .replace("verschlechterten", "verbesserten")
                .replace("senkt", "steigert").replace("niedrig", "hoch")
                .replace("laenger", "kuerzer").replace("länger", "kürzer")),
    ("Zahl verschoben", "result",
     lambda t: re_ersetze_erste_zahl(t)),
    ("Studienart getauscht", "sum",
     lambda t: ("Randomisierte kontrollierte Studie: " + t
                if "andomisiert" not in t else "Beobachtungsstudie: " + t)),
    ("Ergebnis erfunden", "result",
     lambda t: t + " Die Sterblichkeit sank um 41 Prozent (p<0,001)."),
    ("Population vertauscht", "sum",
     lambda t: t.replace("Erwachsen", "Kinder").replace("Kinder", "Erwachsen")
                if ("Erwachsen" in t or "Kinder" in t)
                else t + " Untersucht wurden ausschliesslich Saeuglinge."),
    ("Zeitraum verdreifacht", "sum",
     lambda t: re_jahre_mal_drei(t)),
]


def re_ersetze_erste_zahl(t: str) -> str:
    """Die erste Zahl im Text deutlich veraendern - aber nur, wenn es eine
    gibt. Sonst waere der Fall keine Verderbnis, sondern unveraendert, und
    der Gegentest zaehlte einen Fehlschlag, den es nicht gab."""
    import re as _re
    m = _re.search(r"\d+[,.]?\d*", t)
    if not m:
        return ""
    alt = m.group(0)
    try:
        neu = str(round(float(alt.replace(",", ".")) * 2.7, 1)).replace(".", ",")
    except ValueError:
        return ""
    return t[:m.start()] + neu + t[m.end():]


def re_jahre_mal_drei(t: str) -> str:
    import re as _re
    m = _re.search(r"(\d+)\s*(Monate|Monaten|Jahre|Jahren|Wochen)", t)
    if not m:
        return ""
    return t[:m.start(1)] + str(int(m.group(1)) * 3) + t[m.end(1):]


def gegentest(client, gewaehlt, quellen, wieviel: int) -> int:
    """Verdirbt echte Eintraege und sieht nach, ob der Pruefer es merkt."""
    brauchbar = [(h, x) for h, x in gewaehlt
                 if quellen.get(str(x.get("pmid")), {}).get("abstract")]
    print(f"\n{'='*74}\nGEGENTEST: {wieviel} echte Eintraege, je sechs Arten "
          "verdorben\n" + "=" * 74)
    gefunden = verpasst = uebersprungen = 0
    fehlalarm = 0
    for hub, x in brauchbar[:wieviel]:
        q = quellen[str(x["pmid"])]
        # Erst die unveraenderte Fassung: Sie MUSS durchgehen. Ein Pruefer,
        # der alles beanstandet, findet die Fehler auch - und taugt nichts.
        u = urteilen(client, x, q)
        if u.get("urteil") == "widerspruch":
            fehlalarm += 1
            print(f"  FEHLALARM {x['pmid']}: {u.get('stelle','')[:70]}")
        time.sleep(0.2)
        for name, feld, machen in VERDERBEN:
            schlecht = dict(x)
            neu = machen(str(x.get(feld) or ""))
            if not neu or neu == x.get(feld):
                uebersprungen += 1
                continue
            schlecht[feld] = neu
            u = urteilen(client, schlecht, q)
            if u.get("urteil") == "widerspruch":
                gefunden += 1
            else:
                verpasst += 1
                print(f"  VERPASST  {x['pmid']} [{name}]: {neu[:88]}")
            time.sleep(0.2)
    gesamt = gefunden + verpasst
    print(f"\n  verdorbene Faelle   {gesamt}  ({uebersprungen} nicht herstellbar)")
    print(f"  davon gefunden      {gefunden}"
          + (f"  ({100*gefunden//gesamt} %)" if gesamt else ""))
    print(f"  verpasst            {verpasst}")
    print(f"  Fehlalarm (echt!)   {fehlalarm} von {len(brauchbar[:wieviel])}")
    return verpasst


def main() -> int:
    p = argparse.ArgumentParser(description="Inhaltliche Pruefung der Zusammenfassungen")
    p.add_argument("--faelle", nargs="*", help="einzelne PMIDs")
    p.add_argument("--hub", help="nur dieser Hub")
    p.add_argument("--probe", type=int, help="nur die juengsten N je Hub")
    p.add_argument("--alle", action="store_true", help="alle Archive")
    p.add_argument("--zeigen", action="store_true",
                   help="Abstract und deutschen Text ausgeben, nicht urteilen")
    p.add_argument("--gegentest", type=int, metavar="N",
                   help="N echte Eintraege verderben und sehen, ob es auffaellt")
    a = p.parse_args()

    bestand = archive()
    gewaehlt: list[tuple[str, dict]] = []
    for hub, liste in bestand.items():
        if a.hub and hub != a.hub:
            continue
        liste = sorted(liste, key=lambda x: x.get("aufgenommen", ""), reverse=True)
        if a.faelle:
            liste = [x for x in liste if str(x.get("pmid")) in set(a.faelle)]
        elif a.probe:
            liste = liste[:a.probe]
        elif not a.alle and not a.hub:
            p.error("Bitte --faelle, --hub, --probe oder --alle angeben.")
        gewaehlt += [(hub, x) for x in liste]

    if not gewaehlt:
        print("Nichts ausgewaehlt.")
        return 1
    print(f"{len(gewaehlt)} Eintraege ausgewaehlt. Hole die Abstracts ...")
    quellen = abstracts([str(x.get("pmid")) for _, x in gewaehlt])
    ohne = [x for _, x in gewaehlt if str(x.get("pmid")) not in quellen]
    print(f"  {len(quellen)} Abstracts geholt"
          + (f", {len(ohne)} ohne (PubMed kennt sie nicht mehr)" if ohne else ""))

    if a.zeigen:
        for hub, x in gewaehlt:
            q = quellen.get(str(x.get("pmid")), {})
            print(f"\n{'='*74}\n{x.get('pmid')}  [{hub}]  {x.get('journal','')}")
            print(f"\nORIGINAL: {q.get('titel','(fehlt)')}")
            print(f"\nABSTRACT: {q.get('abstract','(fehlt)')[:1400]}")
            print(f"\nDEUTSCH : {x.get('title','')}")
            print(f"SUM     : {x.get('sum','')}")
            print(f"ERGEBNIS: {x.get('result','')}")
        return 0

    schluessel = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not schluessel:
        print("ANTHROPIC_API_KEY nicht gesetzt.")
        return 1
    import anthropic
    client = anthropic.Anthropic(api_key=schluessel)

    if a.gegentest:
        return 1 if gegentest(client, gewaehlt, quellen, a.gegentest) else 0

    # **Fortgeschrieben wird waehrend des Laufs, nicht danach.** 5.358
    # Eintraege sind rund zwei Stunden; wer sie am Ende in einem Rutsch
    # schriebe, verloere bei jedem Abbruch alles. Die Datei ist zugleich die
    # Wiederaufnahme: Was darin steht, wird nicht noch einmal gefragt.
    ergebnisse: dict[str, dict] = {}
    if BEFUND.exists():
        try:
            ergebnisse = json.loads(BEFUND.read_text(encoding="utf-8"))["urteile"]
            print(f"  {len(ergebnisse)} Urteile aus einem frueheren Lauf "
                  "uebernommen - die werden nicht noch einmal gefragt.")
        except (ValueError, KeyError):
            pass

    # **Uebersprungen wird nur, was ein ECHTES Urteil hat.** Ein "unlesbar"
    # aufzubewahren hiesse, eine ungepruefte Studie als erledigt zu fuehren -
    # und beim naechsten Lauf bliebe sie es fuer immer.
    fertig = {k for k, u in ergebnisse.items()
              if u.get("urteil") in ("passt", "widerspruch")}
    offen = [(h, x) for h, x in gewaehlt
             if (h + "/" + str(x.get("pmid"))) not in fertig
             and quellen.get(str(x.get("pmid")), {}).get("abstract")]
    print(f"  {len(offen)} zu pruefen.\n")

    sperre = threading.Lock()
    stand = {"fertig": 0, "widerspruch": 0, "unlesbar": 0}

    def eins(auftrag):
        hub, x = auftrag
        pmid = str(x["pmid"]); schluessel = f"{hub}/{pmid}"
        try:
            u = urteilen(client, x, quellen[pmid])
        except Exception as fehler:                    # noqa: BLE001
            u = {"urteil": "fehler", "stelle": "", "begruendung": str(fehler)[:120]}
        u["hub"] = hub
        u["titel"] = x.get("title", "")
        with sperre:
            ergebnisse[schluessel] = u
            stand["fertig"] += 1
            if u["urteil"] == "widerspruch":
                stand["widerspruch"] += 1
                print(f"  ! {pmid} [{hub}] {x.get('title','')[:56]}")
                print(f"      {u.get('stelle','')[:100]}")
                print(f"      Abstract: {u.get('begruendung','')[:100]}")
            elif u["urteil"] in ("unlesbar", "fehler"):
                stand["unlesbar"] += 1
            if stand["fertig"] % 50 == 0:
                sichern(ergebnisse)
                print(f"  ... {stand['fertig']}/{len(offen)} geprueft, "
                      f"{stand['widerspruch']} Widersprueche, "
                      f"{stand['unlesbar']} ohne Urteil")

    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        list(pool.map(eins, offen))
    sichern(ergebnisse)

    w = [(p, u) for p, u in ergebnisse.items() if u["urteil"] == "widerspruch"]
    ohne = [(p, u) for p, u in ergebnisse.items()
            if u["urteil"] in ("unlesbar", "fehler")]
    print(f"\n{'='*74}")
    print(f"  geprueft        {len(ergebnisse)}")
    print(f"  Widersprueche   {len(w)}"
          + (f"  ({100*len(w)/len(ergebnisse):.2f} %)" if ergebnisse else ""))
    print(f"  ohne Urteil     {len(ohne)}   <- NICHT als 'passt' gezaehlt")
    print(f"\n  Befund: {BEFUND}")
    if ohne:
        print("  Die ohne Urteil noch einmal laufen lassen: Das Skript "
              "ueberspringt, was schon beurteilt ist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
