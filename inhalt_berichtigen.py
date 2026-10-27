#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dritter Durchgang: die Funde berichtigen - aber erst zum Ansehen.

    py inhalt_berichtigen.py                    # 20 Vorher/Nachher zum Lesen
    py inhalt_berichtigen.py --probe 60         # mehr davon
    py inhalt_berichtigen.py --art kausal       # nur die Kausalsprache
    py inhalt_berichtigen.py --alle             # alle Faelle rechnen
    py inhalt_berichtigen.py --uebernehmen      # erst DANN wird geschrieben

**Ohne `--uebernehmen` wird kein Archiv angefasst.** Der Lauf rechnet die
Neufassungen, prueft sie nach und legt eine Seite ab - nichts geht ins
Portal. Das ist Absicht: eine Berichtigung, die keiner gelesen hat, ist nur
eine zweite Behauptung ueber derselben Stelle.

Wie berichtigt wird
-------------------
Die Neufassung entsteht aus dem Abstract, nicht aus dem deutschen Text.
Verlangt ist die **kleinste** Aenderung, die den Fund aufhebt: eine Zahl
richtigstellen, eine Teilgruppe benennen, ein Verb zuruecknehmen. Kein
Umschreiben, kein Glaetten - wer den ganzen Satz neu baut, bringt neue
Fehler mit und macht den Vergleich unlesbar.

Bei der Kausalsprache ist die Regel eine Hausregel und keine Erfindung
dieses Skripts: *wir werten nicht*, jede Wertung kommt aus der Quelle. Sagt
die Arbeit "war assoziiert mit", sagt der deutsche Text das auch.

Was der Gegentest beweist - und was nicht
-----------------------------------------
Jede Neufassung geht durch `urteilen()` aus dem ersten Durchgang.

**Die Frage ist nicht, ob der Pruefer danach schweigt, sondern ob er noch
dieselbe Stelle ruegt.** Das war der Fehler in der ersten Fassung dieses
Skripts: Sie zaehlte jede neue Beanstandung als gescheiterte Berichtigung
und meldete am 27.10.2026 "11 von 20 weiter beanstandet". Nachgesehen
waren es **null von elf**: Der Pruefer nannte jedes Mal eine ANDERE Stelle
im selben Eintrag.

Das ist kein Zufall, sondern die Struktur des Bestands. Der erste Durchgang
beanstandete 56 Prozent aller Eintraege und meldet pro Eintrag **eine**
Stelle - viele Eintraege haben mehr als eine. Wer eine davon berichtigt,
bekommt die naechste zu sehen. Eine neue Beanstandung ist deshalb ein
**weiterer Fund**, der zurueck in die Liste gehoert, und kein Beweis, dass
die Berichtigung nicht gegriffen hat.

Und auch wenn er schweigt, ist das kein Freispruch: Es ist dasselbe Modell
mit demselben Auftrag, das den Fund gemeldet hat. Es bestaetigt, dass die
Aenderung aufhebt, was dieses Instrument gesehen hat - nicht, dass der neue
Satz gut ist. Dafuer gibt es die Seite und ein Paar Augen.

Ob zwei Stellen dieselbe sind, entscheidet `gleiche_stelle()` ueber die
gemeinsamen langen Woerter. Das ist eine Schaetzung, keine Messung, und
genau deshalb steht auf der Seite immer **beides** nebeneinander: die alte
Beanstandung und die neue. Wer zweifelt, liest zwei Zeilen.
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import os
import pathlib
import random
import sys
import threading
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
from inhalt_pruefen import (MODELL, PARALLEL, WURZEL, abstracts,  # noqa: E402
                            archive, urteilen)

EINORDNUNG = HIER / "inhalt-einordnung.json"
FASSUNGEN = HIER / "inhalt-fassungen.json"
SEITE = HIER / "inhalt-berichtigung.html"

FELDER = ("title", "sum", "result")

AUFTRAG = """Du berichtigst eine deutsche Zusammenfassung einer
wissenschaftlichen Arbeit. Du bekommst den Originaltitel, den Abstract, den
deutschen Text eines Fachportals und einen Befund: eine Stelle, die die
Quelle nicht hergibt.

Deine Aufgabe ist die KLEINSTE Aenderung, die den Befund aufhebt.

Regeln:

1. **Nur die beanstandete Stelle anfassen.** Alles andere bleibt Wort fuer
   Wort stehen - auch wenn du es anders schreiben wuerdest. Kein Glaetten,
   kein Umstellen, kein Kuerzen.
2. **Die Quelle entscheidet, nicht der deutsche Text.** Was im Abstract
   steht, gilt. Erfinde nichts dazu; steht die richtige Angabe nicht im
   Abstract, formuliere die Aussage so, dass sie ohne sie stimmt.
3. **Wir werten nicht.** Sagt die Arbeit "war assoziiert mit", "ging einher
   mit", "Hinweise auf", dann sagt der deutsche Text das auch - nicht
   "senkt", "verbessert", "fuehrt zu". Die Staerke der Quelle wird
   uebernommen, nicht verschaerft und nicht abgeschwaecht.
4. **Kein Vorbehalt dazuschreiben.** Keine Einschuebe wie "moeglicherweise",
   "die Autoren vermuten", "in dieser Studie" - es sei denn, die Quelle
   sagt genau das.
5. Deutsche Fachsprache bleibt. Zahlenformat bleibt (Komma als
   Dezimaltrennzeichen, Prozentzeichen wie gesetzt).

Antworte als JSON, sonst nichts:
{"title": "...", "sum": "...", "result": "...",
 "geaendert": ["title"|"sum"|"result", ...],
 "was": "in einem Satz: was du geaendert hast und warum"}

Gib alle drei Felder vollstaendig zurueck, auch die unveraenderten. In
"geaendert" stehen nur die Felder, die du wirklich angefasst hast. Haelt
der Befund deiner Pruefung nicht stand, gib alle drei Felder unveraendert
zurueck und lass "geaendert" leer."""


def neu_fassen(client, eintrag: dict, quelle: dict, fund: dict) -> dict:
    text = (f"ORIGINALTITEL: {quelle['titel']}\n\n"
            f"ABSTRACT: {quelle['abstract'][:4000]}\n\n"
            f"---\n\nDEUTSCHER TITEL: {eintrag.get('title','')}\n\n"
            f"ZUSAMMENFASSUNG: {eintrag.get('sum','')}\n\n"
            f"ERGEBNIS: {eintrag.get('result','')}\n\n"
            f"---\n\nBEFUND ({fund.get('art','')}, Schwere "
            f"{fund.get('schwere','')}):\n"
            f"  beanstandete Stelle: {fund.get('stelle','')}\n"
            f"  die Quelle sagt:     {fund.get('richtig','')}")
    # max_tokens traegt das Nachdenken MIT - siehe inhalt_pruefen.py. Hier
    # kommen dazu drei Felder im Volltext zurueck, also reichlich Luft.
    antwort = client.messages.create(
        model=MODELL, max_tokens=4000,
        system=AUFTRAG,
        messages=[{"role": "user", "content": text}])
    roh = " ".join(b.text for b in antwort.content
                   if getattr(b, "type", "") == "text").strip()
    try:
        i, j = roh.index("{"), roh.rindex("}") + 1
        d = json.loads(roh[i:j])
    except (ValueError, json.JSONDecodeError):
        return {"fehler": "unlesbar", "roh": roh[:160]}
    # Dem Modell nicht glauben, was es geaendert haben will - nachsehen.
    d["geaendert"] = [f for f in FELDER
                      if (d.get(f) or "") != (eintrag.get(f) or "")]
    return d


def auswaehlen(d: dict, a) -> list:
    if a.art:
        faelle = [(k, v) for k, v in d.items() if v["art"] == a.art]
    else:
        faelle = [(k, v) for k, v in d.items()
                  if v["art"] in ("sachfehler", "ueberdehnt")
                  and v.get("schwere") == "hoch"]
    if not a.alle:
        random.seed(a.saat)
        faelle = random.sample(faelle, min(a.probe, len(faelle)))
    return sorted(faelle)


def unterschied(alt: str, neu: str) -> tuple[str, str]:
    """Die beiden Fassungen so ausgeben, dass das Auge die Stelle findet:
    gemeinsamer Anfang und gemeinsames Ende grau, die Mitte hervorgehoben."""
    i = 0
    while i < min(len(alt), len(neu)) and alt[i] == neu[i]:
        i += 1
    j = 0
    while (j < min(len(alt), len(neu)) - i
           and alt[len(alt)-1-j] == neu[len(neu)-1-j]):
        j += 1
    i = max(0, alt.rfind(" ", 0, i) + 1)          # auf Wortgrenzen ruecken
    rechts_alt = len(alt) - j
    rechts_alt = alt.find(" ", rechts_alt)
    rechts_alt = len(alt) if rechts_alt < 0 else rechts_alt
    rechts_neu = len(neu) - j
    rechts_neu = neu.find(" ", rechts_neu)
    rechts_neu = len(neu) if rechts_neu < 0 else rechts_neu

    def bauen(t, bis, farbe):
        return (f'<span class="gleich">{html.escape(t[:i])}</span>'
                f'<mark class="{farbe}">{html.escape(t[i:bis])}</mark>'
                f'<span class="gleich">{html.escape(t[bis:])}</span>')
    return bauen(alt, rechts_alt, "weg"), bauen(neu, rechts_neu, "hin")


def gleiche_stelle(alt: str, neu: str) -> bool:
    """Schaetzt, ob zwei beanstandete Stellen dieselbe meinen - ueber die
    gemeinsamen langen Woerter. Eine Schaetzung, bewusst grosszuegig: im
    Zweifel lieber "dieselbe Stelle" melden und einen Fall zum Lesen
    vorlegen, als eine nicht gegriffene Berichtigung durchwinken."""
    a = {w.strip(".,;:()„“\"'").lower() for w in (alt or "").split()
         if len(w) > 4}
    b = {w.strip(".,;:()„“\"'").lower() for w in (neu or "").split()
         if len(w) > 4}
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.4


def zustand(v: dict) -> str:
    """Einer von vier Zustaenden - die Seite und die Zahlen nutzen beide
    diese Funktion, damit Beschriftung und Zaehlung nicht auseinanderlaufen."""
    if v.get("fehler"):
        return "unlesbar"
    if not v.get("geaendert"):
        return "unveraendert"
    n = v.get("nachher", {})
    if n.get("urteil") != "widerspruch":
        return "aufgehoben"
    if gleiche_stelle(v.get("fund", {}).get("stelle", ""), n.get("stelle", "")):
        return "offen"
    return "weiterer"


FARBE = {"sachfehler": "#8A2D2D", "ueberdehnt": "#8A5608",
         "kausal": "#0E5A5E", "kein_fehler": "#1C6B3C"}
WORT = {"sachfehler": "Sachfehler", "ueberdehnt": "überdehnt",
        "kausal": "Kausalsprache", "kein_fehler": "kein Fehler"}
FELDWORT = {"title": "Titel", "sum": "Zusammenfassung", "result": "Ergebnis"}


def seite(fertig: dict, kopf: str) -> str:
    t = ["""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Berichtigungen zum Ansehen</title><style>
body{margin:0;background:#EDF2FA;color:#111;
  font:400 15px/1.65 Lato,-apple-system,Segoe UI,sans-serif}
.h{max-width:1020px;margin:0 auto;padding:0 20px 70px}
header{background:#0051A1;color:#fff;padding:26px 0}
header h1{margin:0 0 6px;font-size:25px}
header p{margin:0;color:#C9DCF2;max-width:78ch;font-size:14.5px}
.hinweis{background:#FFF8E6;border-left:3px solid #BE9E53;padding:13px 17px;
  margin:22px 0 26px;font-size:14px;color:#5C4A17;border-radius:0 4px 4px 0}
.zahlen{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0 0}
.z{background:#fff;border:1px solid #E3EAF3;border-radius:7px;
  padding:11px 15px;border-top:3px solid var(--f)}
.z b{display:block;font-size:24px;color:var(--f);
  font-variant-numeric:tabular-nums;line-height:1.1}
.z span{font-size:12.5px;color:#545C63}
.f{background:#fff;border:1px solid #E3EAF3;border-radius:7px;
  padding:16px 18px;margin:0 0 14px;border-left:3px solid var(--f)}
.f.offen{border-left-width:7px;background:#FFFBF5}
.kopf{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px}
.marke{background:#F0F4F9;color:var(--f);font-size:11px;font-weight:700;
  padding:2px 9px;border-radius:3px;text-transform:uppercase;
  letter-spacing:.04em}
.warn{background:#8A2D2D;color:#fff}
.hub{font-size:12px;color:#545C63}
.pm{font-size:12px;margin-left:auto}
.pm a{color:#0051A1}
.feld{margin:0 0 12px}
.feld>b{display:block;font-size:11.5px;color:#545C63;text-transform:uppercase;
  letter-spacing:.05em;margin:0 0 4px}
.paar{display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:14px}
.paar>div{padding:9px 11px;border-radius:5px;background:#FAFBFD;
  border:1px solid #E3EAF3}
.paar .vor{border-left:2px solid #C2A0A0}
.paar .nach{border-left:2px solid #93BBA2}
.paar em{display:block;font-size:11px;color:#767E85;font-style:normal;
  margin:0 0 4px;text-transform:uppercase;letter-spacing:.05em}
.gleich{color:#767E85}
mark{padding:0 2px;border-radius:2px}
mark.weg{background:#F6D9D9}
mark.hin{background:#D7EEE0}
.was{font-size:13px;color:#545C63;margin:10px 0 0;padding:8px 0 0;
  border-top:1px solid #E3EAF3}
.urteil{font-size:13px;margin:9px 0 0}
.urteil label{margin-right:18px;cursor:pointer;color:#545C63}
@media(max-width:760px){.paar{grid-template-columns:1fr}}
</style></head><body><header><div class="h">
<h1>Berichtigungen zum Ansehen</h1><p>""" + kopf + "</p></div></header>"
         '<div class="h">']

    z = collections.Counter(zustand(v) for v in fertig.values())
    t.append('<div class="zahlen">')
    for schluessel, wort, farbe in (
            ("aufgehoben", "Stelle berichtigt, Prüfer still", "#1C6B3C"),
            ("weiterer", "berichtigt, weiterer Fund daneben", "#8A5608"),
            ("offen", "dieselbe Stelle weiter gerügt", "#8A2D2D"),
            ("unveraendert", "Modell liess stehen", "#545C63"),
            ("unlesbar", "ohne Antwort", "#545C63")):
        t.append(f'<div class="z" style="--f:{farbe}"><b>{z[schluessel]}</b>'
                 f'<span>{wort}</span></div>')
    t.append("</div>")

    t.append('<div class="hinweis"><b>Nichts davon steht im Portal.</b> '
             'Der Lauf hat nur gerechnet.<br><br>'
             '<b>Die Frage ist nicht, ob der Prüfer danach schweigt, '
             'sondern ob er noch dieselbe Stelle rügt.</b> Viele Einträge '
             'haben mehr als eine strittige Stelle — der erste Durchgang '
             'meldet pro Eintrag nur eine. Wer sie berichtigt, bekommt die '
             'nächste zu sehen. Eine neue Beanstandung ist deshalb ein '
             '<b>weiterer Fund</b> für die Liste, kein Beweis, dass die '
             'Berichtigung nicht gegriffen hat. Beide Stellen stehen unten '
             'nebeneinander; die Zuordnung ist geschätzt, zwei Zeilen Lesen '
             'entscheidet sie.<br><br>'
             'Und auch Schweigen ist kein Freispruch: Es ist dasselbe '
             'Modell, das den Fund gemeldet hat — es bestätigt, dass die '
             'Stelle weg ist, nicht dass der neue Satz gut ist. Oben stehen '
             'die Fälle, bei denen dieselbe Stelle weiter gerügt wird.'
             '</div>')

    RANG = {"offen": 0, "unlesbar": 1, "unveraendert": 2,
            "weiterer": 3, "aufgehoben": 4}

    for k, v in sorted(fertig.items(), key=lambda p: RANG[zustand(p[1])]):
        wie = zustand(v)
        art = v.get("art", "")
        f = FARBE.get(art, "#545C63")
        pmid = k.split("/")[-1]
        t.append(f'<div class="f{" offen" if wie == "offen" else ""}" '
                 f'style="--f:{f}"><div class="kopf"><span class="marke">'
                 f'{WORT.get(art, art)}</span>')
        for nur, klasse, wort in (
                ("offen", "warn", "dieselbe Stelle weiter gerügt"),
                ("unlesbar", "warn", "ohne Antwort"),
                ("unveraendert", "", "unverändert zurück"),
                ("weiterer", "", "weiterer Fund daneben")):
            if wie == nur:
                t.append(f'<span class="marke {klasse}">{wort}</span>')
        t.append(f'<span class="hub">{html.escape(v.get("hub",""))}</span>'
                 f'<span class="pm"><a href="https://pubmed.ncbi.nlm.nih.gov/'
                 f'{pmid}/" target="_blank" rel="noopener">Abstract '
                 f'{pmid} ↗</a></span></div>')
        for feld in FELDER:
            if feld not in (v.get("geaendert") or []):
                continue
            vor, nach = unterschied(v["vorher"].get(feld) or "",
                                    v.get(feld) or "")
            t.append(f'<div class="feld"><b>{FELDWORT[feld]}</b>'
                     f'<div class="paar"><div class="vor"><em>bisher</em>'
                     f'{vor}</div><div class="nach"><em>neu</em>{nach}</div>'
                     f'</div></div>')
        if v.get("was"):
            t.append(f'<p class="was">{html.escape(v["was"])}</p>')
        if wie in ("offen", "weiterer"):
            n = v.get("nachher", {})
            t.append(
                '<p class="was"><b>'
                + ("Der Prüfer rügt danach dieselbe Stelle:"
                   if wie == "offen" else
                   "Der Prüfer nennt danach eine andere Stelle:")
                + "</b><br>bisher beanstandet: „"
                + html.escape(v.get("fund", {}).get("stelle", ""))
                + "“<br>jetzt beanstandet: „"
                + html.escape(n.get("stelle", ""))
                + "“<br>" + html.escape(n.get("begruendung", "")) + "</p>")
        if v.get("fehler"):
            t.append(f'<p class="was">{html.escape(v.get("roh",""))}</p>')
        t.append('<div class="urteil"><label><input type="checkbox"> so '
                 'übernehmen</label><label><input type="checkbox"> nein, '
                 'von Hand</label></div></div>')
    t.append("</div></body></html>")
    return "\n".join(t)


def uebernehmen(fertig: dict) -> None:
    """Die abgenommenen Fassungen in die Archive schreiben.

    Pro Hub EINMAL lesen und EINMAL schreiben. Und nur Felder ersetzen, die
    im Archiv noch genau so stehen wie beim Rechnen - die Archive wachsen
    jede Nacht, und eine Berichtigung, die auf einem alten Stand sitzt,
    duerfte nichts ueberschreiben."""
    nach_hub: dict[str, list] = collections.defaultdict(list)
    for k, v in fertig.items():
        # "weiterer" geht MIT: dort ist die genannte Stelle berichtigt, und
        # der neue Fund ist eine eigene Sache. Nur wo dieselbe Stelle weiter
        # geruegt wird, bleibt es beim alten Text.
        if zustand(v) not in ("aufgehoben", "weiterer"):
            continue
        nach_hub[k.split("/")[0]].append((k.split("/")[-1], v))

    for hub, posten in sorted(nach_hub.items()):
        datei = WURZEL / f"{hub}-portal" / "studien-archiv.json"
        if not datei.exists():
            print(f"  {hub}: Archiv fehlt, uebersprungen")
            continue
        roh = json.loads(datei.read_text(encoding="utf-8"))
        liste = roh if isinstance(roh, list) else roh.get("studien", [])
        nach_pmid = {str(x.get("pmid")): x for x in liste}
        gesetzt = veraltet = 0
        for pmid, v in posten:
            x = nach_pmid.get(pmid)
            if x is None:
                veraltet += 1
                continue
            for feld in v["geaendert"]:
                if (x.get(feld) or "") != (v["vorher"].get(feld) or ""):
                    veraltet += 1       # der Nachtlauf war schneller
                    continue
                x[feld] = v[feld]
                gesetzt += 1
        datei.write_text(json.dumps(roh, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        print(f"  {hub}: {gesetzt} Felder ersetzt"
              + (f", {veraltet} uebersprungen (Stand hat sich geaendert)"
                 if veraltet else ""))


def main() -> int:
    p = argparse.ArgumentParser(description="Funde berichtigen")
    p.add_argument("--probe", type=int, default=20, help="wie viele (20)")
    p.add_argument("--saat", type=int, default=0, help="Zufallssaat")
    p.add_argument("--alle", action="store_true", help="alle Faelle rechnen")
    p.add_argument("--art", choices=list(WORT), help="nur diese Art")
    p.add_argument("--uebernehmen", action="store_true",
                   help="die sauberen Fassungen in die Archive schreiben")
    p.add_argument("--nur-seite", action="store_true",
                   help="Seite aus dem gerechneten Stand neu bauen, "
                        "ohne das Modell noch einmal zu fragen")
    a = p.parse_args()

    if a.nur_seite:
        if not FASSUNGEN.exists():
            print(f"{FASSUNGEN.name} fehlt - erst rechnen lassen.")
            return 1
        d = json.loads(FASSUNGEN.read_text(encoding="utf-8"))
        fertig = d["fassungen"]
        SEITE.write_text(seite(fertig, f"{len(fertig)} Fälle, gerechnet am "
                                       f"{d.get('gerechnet_am','?')}."),
                         encoding="utf-8")
        z = collections.Counter(zustand(v) for v in fertig.values())
        print(f"{SEITE}\n  " + "  ".join(f"{k} {n}" for k, n in z.items()))
        return 0

    if a.uebernehmen:
        if not FASSUNGEN.exists():
            print(f"{FASSUNGEN.name} fehlt - erst rechnen lassen.")
            return 1
        d = json.loads(FASSUNGEN.read_text(encoding="utf-8"))
        print(f"Uebernehme aus {FASSUNGEN.name} "
              f"(gerechnet {d.get('gerechnet_am','?')}):")
        uebernehmen(d["fassungen"])
        return 0

    if not EINORDNUNG.exists():
        print(f"{EINORDNUNG.name} fehlt - erst inhalt_einordnen.py.")
        return 1
    eingeordnet = json.loads(EINORDNUNG.read_text(encoding="utf-8"))["einordnung"]
    faelle = auswaehlen(eingeordnet, a)
    print(f"{len(faelle)} Faelle zu rechnen"
          f"{'' if a.alle or a.art else f' (Probe aus {a.probe})'}")

    bestand = archive()
    nach_schluessel = {}
    for hub, liste in bestand.items():
        for x in liste:
            nach_schluessel[hub + "/" + str(x.get("pmid"))] = x
    faelle = [(k, v) for k, v in faelle if k in nach_schluessel]

    print("Hole die Abstracts ...")
    quellen = abstracts([k.split("/")[-1] for k, _ in faelle])
    faelle = [(k, v) for k, v in faelle
              if quellen.get(k.split("/")[-1], {}).get("abstract")]
    print(f"  {len(faelle)} mit Abstract.\n")

    schluessel = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not schluessel:
        print("ANTHROPIC_API_KEY nicht gesetzt.")
        return 1
    import anthropic
    client = anthropic.Anthropic(api_key=schluessel)

    fertig: dict[str, dict] = {}
    sperre = threading.Lock()
    stand = {"n": 0}

    def eins(paar):
        k, fund = paar
        alt = nach_schluessel[k]
        quelle = quellen[k.split("/")[-1]]
        try:
            neu = neu_fassen(client, alt, quelle, fund)
        except Exception as fehler:                       # noqa: BLE001
            neu = {"fehler": "Abbruch", "roh": str(fehler)[:160]}
        neu["art"] = fund.get("art", "")
        neu["schwere"] = fund.get("schwere", "")
        neu["hub"] = fund.get("hub", k.split("/")[0])
        neu["fund"] = {"stelle": fund.get("stelle", ""),
                       "richtig": fund.get("richtig", "")}
        neu["vorher"] = {f: alt.get(f, "") for f in FELDER}
        # Gegentest: dasselbe Instrument noch einmal ueber die neue Fassung.
        if not neu.get("fehler") and neu.get("geaendert"):
            geaendert = dict(alt)
            geaendert.update({f: neu[f] for f in FELDER if f in neu})
            try:
                neu["nachher"] = urteilen(client, geaendert, quelle)
            except Exception as fehler:                   # noqa: BLE001
                neu["nachher"] = {"urteil": "unlesbar",
                                  "begruendung": str(fehler)[:120]}
        with sperre:
            fertig[k] = neu
            stand["n"] += 1
            if stand["n"] % 20 == 0:
                print(f"  ... {stand['n']}/{len(faelle)}")

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        list(pool.map(eins, faelle))

    FASSUNGEN.write_text(json.dumps(
        {"gerechnet_am": time.strftime("%Y-%m-%d %H:%M"), "modell": MODELL,
         "fassungen": fertig}, ensure_ascii=False, indent=1), encoding="utf-8")

    kopf = (f"{len(fertig)} Fälle, gerechnet am "
            f"{time.strftime('%d.%m.%Y')}. "
            + ("Alle Fälle der Art „" + WORT[a.art] + "“."
               if a.art else "Zufällige Probe aus den schweren Fällen "
               "(Sachfehler und überdehnte Aussagen im Titel oder am "
               "Hauptergebnis)."))
    SEITE.write_text(seite(fertig, kopf), encoding="utf-8")

    z = collections.Counter(zustand(v) for v in fertig.values())
    print(f"\n{'='*70}")
    for schluessel, wort in (
            ("aufgehoben", "Stelle berichtigt, Pruefer still"),
            ("weiterer", "berichtigt, weiterer Fund daneben"),
            ("offen", "dieselbe Stelle weiter geruegt"),
            ("unveraendert", "Modell liess stehen"),
            ("unlesbar", "ohne Antwort")):
        print(f"  {wort:<38} {z[schluessel]:>4}")
    print(f"\n  Zum Ansehen: {SEITE}")
    print(f"  Fassungen:   {FASSUNGEN}")
    print("\n  Geschrieben wurde nichts. Erst nach dem Lesen:"
          "\n    py inhalt_berichtigen.py --uebernehmen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
