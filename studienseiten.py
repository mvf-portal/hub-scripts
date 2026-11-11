#!/usr/bin/env python3
"""Feste Seiten je Studie, Uebersicht, sitemap.xml und robots.txt fuer einen Hub.

Warum es das gibt (11.11.2026): Die Studien eines Hubs stehen nur in
studien-archiv.json und werden im Browser per JavaScript gezeigt; eine
einzelne Studie hat nur die Adresse /#studie-<PMID>. Suchmaschinen und
KI-Dienste (ChatGPT, Perplexity, Claude, Copilot) fuehren in der Regel kein
JavaScript aus und behandeln alles hinter "#" als dieselbe Seite. Fuer sie
gab es die Zusammenfassungen also nicht. Dieses Skript legt daneben reines
HTML ab:

    studie/<pmid>/index.html   eine Seite je Studie, mit schema.org-Angaben
    studie/index.html          Uebersicht nach Aufnahmemonat
    sitemap.xml                alle Seiten des Hubs
    robots.txt                 alles frei, Verweis auf die Sitemap

Liest nur portal.json und studien-archiv.json - kein Netz, kein Schluessel.
Aufruf im Wurzelverzeichnis eines Portals:

    python scripts/gemeinsam/studienseiten.py

**Deterministisch wie build_newsletter.py:** Kein Datum aus der Systemuhr.
Alle Daten stammen aus dem Archiv; zwei Laeufe erzeugen bitgleiche Dateien.
Sonst entstuende jeden Tag ein Commit samt Pages-Build.

**Kennzeichnung nach Art. 50 Abs. 4 KI-Verordnung:** Jede Studienseite traegt
denselben Wortlaut wie die Startseite ("Von KI ausgewaehlt und
zusammengefasst", festgelegt vom Herausgeber am 24.10.2026). Wer ihn aendert,
aendert ihn auf allen drei Seiten mit.

**Fremde Dateien bleiben unangetastet:** sitemap.xml und robots.txt werden nur
geschrieben, wenn es sie noch nicht gibt oder wenn sie die Kennzeile dieses
Skripts tragen. Eine von Hand gepflegte Datei (wie beim Innovationsfonds-Radar)
fuehrt zu einer Warnung, nicht zum Ueberschreiben.
"""

import html
import json
import re
import shutil
import sys
from pathlib import Path

KENNZEILE = "erzeugt von hub-scripts/studienseiten.py"
KI_KENNZEICHEN = "Von KI ausgewählt und zusammengefasst"
MVF_URL = "https://www.monitor-versorgungsforschung.de/"
IMPRESSUM = "https://knowledge-hubs.m-vf.de/impressum.html"
DATENSCHUTZ = "https://knowledge-hubs.m-vf.de/datenschutz.html"
HUBS = "https://knowledge-hubs.m-vf.de/"

# Seiten im Wurzelverzeichnis, die nicht in die Sitemap gehoeren: Bausteine,
# die in andere Seiten eingesetzt werden, und Seiten mit noindex.
NICHT_IN_SITEMAP = re.compile(r"^(teile-|_)|^index\.html$")

MONATE = {"jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "mai": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12}
MONATSNAMEN = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
               "August", "September", "Oktober", "November", "Dezember"]


def e(text):
    return html.escape(str(text or ""), quote=True)


def iso_datum(text):
    """'30.10.2026' -> '2026-10-30', 'Aug. 2026' -> '2026-08', '2026' -> '2026'.

    Nie ein erfundener Tag: Fehlt er in PubMed, fehlt er hier auch.
    """
    text = (text or "").strip()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    m = re.fullmatch(r"([A-Za-zÄÖÜäöü]+)\.?\s+(\d{4})", text)
    if m and m[1][:3].lower() in MONATE:
        return f"{m[2]}-{MONATE[m[1][:3].lower()]:02d}"
    m = re.fullmatch(r"\d{4}", text)
    return text if m else ""


def kurz(text, laenge=158):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= laenge:
        return text
    return text[:laenge].rsplit(" ", 1)[0] + " …"


def json_ld(daten):
    # "</" im Text darf das <script> nicht schliessen.
    roh = json.dumps(daten, ensure_ascii=False, separators=(",", ":"))
    return roh.replace("</", "<\\/")


def schreiben(pfad: Path, inhalt: str):
    """Nur schreiben, wenn sich etwas aendert - haelt die Dateizeiten ruhig."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if pfad.exists() and pfad.read_text(encoding="utf-8") == inhalt:
        return False
    pfad.write_text(inhalt, encoding="utf-8", newline="\n")
    return True


def eigene_datei(pfad: Path):
    return not pfad.exists() or KENNZEILE in pfad.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- Aussehen --

CSS = """
@font-face{font-family:"Lato";font-weight:400;src:url("/fonts/lato-400.woff2") format("woff2");font-display:swap}
@font-face{font-family:"Lato";font-weight:700;src:url("/fonts/lato-700.woff2") format("woff2");font-display:swap}
:root{--bg:#EDF2FA;--fl:#fff;--li:#D5DEEC;--tx:#14202E;--gr:#4A5668;--brand:#0051A1;--kopf:#0051A1;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#11151b;--fl:#181f28;--li:#2a323e;--tx:#e6ebf2;--gr:#9aa5b3;--brand:#6ea8ff;--kopf:#0E2C52;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#11151b;--fl:#181f28;--li:#2a323e;--tx:#e6ebf2;--gr:#9aa5b3;--brand:#6ea8ff;--kopf:#0E2C52;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:17px/1.6 Lato,"Segoe UI",system-ui,sans-serif}
a{color:var(--brand)}
.wrap{max-width:860px;margin:0 auto;padding:0 16px}
header{background:var(--kopf);color:#fff;padding:14px 0}
header a{color:#fff;text-decoration:none;font-weight:700}
header .wrap{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline;justify-content:space-between}
header small{opacity:.85;font-weight:400}
main{padding:28px 0 40px}
.krumen{font-size:14px;color:var(--gr);margin:0 0 10px}
h1{font-size:28px;line-height:1.25;margin:0 0 10px}
.meta{color:var(--gr);font-size:15px;margin:0 0 14px}
.ki{display:inline-block;font-size:13px;font-weight:700;border:1px solid var(--li);background:var(--fl);border-radius:999px;padding:2px 11px;margin:0 0 18px}
section{background:var(--fl);border:1px solid var(--li);border-radius:6px;padding:14px 18px;margin:0 0 14px}
section h2{font-size:15px;text-transform:uppercase;letter-spacing:.04em;color:var(--gr);margin:0 0 6px}
section p{margin:0}
.links{display:flex;flex-wrap:wrap;gap:10px 22px;margin:20px 0 0;font-weight:700}
.hinweis{font-size:14px;color:var(--gr);margin:22px 0 0}
ul.liste{list-style:none;margin:0 0 26px;padding:0}
ul.liste li{background:var(--fl);border:1px solid var(--li);border-radius:6px;padding:10px 14px;margin:0 0 8px}
ul.liste span{display:block;font-size:14px;color:var(--gr)}
h2.monat{font-size:20px;margin:26px 0 10px}
footer{border-top:1px solid var(--li);padding:18px 0 30px;font-size:14px;color:var(--gr)}
footer a{color:var(--gr)}
""".strip()

# Liest nur die Darstellungswahl, die der Besucher auf den Hub-Seiten selbst
# getroffen hat (Cookie mvf-theme, beschrieben in den Datenschutzhinweisen,
# Abschnitt "Darstellung"). Setzt nichts.
THEME_SKRIPT = ('<script>(function(){var m=document.cookie.match(/(?:^|;\\s*)mvf-theme=(light|dark)/);'
                'if(m)document.documentElement.setAttribute("data-theme",m[1]);})();</script>')


def seite(titel, beschreibung, kanonisch, ld, kopf_titel, home, inhalt):
    return f"""<!DOCTYPE html>
<!-- {KENNZEILE} - nicht von Hand aendern, der naechste Lauf ueberschreibt es -->
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titel)}</title>
<meta name="description" content="{e(beschreibung)}">
<link rel="canonical" href="{e(kanonisch)}">
<link rel="icon" href="/favicon.ico">
<link rel="alternate" type="application/rss+xml" title="{e(kopf_titel)}" href="{e(home)}studien-feed.xml">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(titel)}">
<meta property="og:description" content="{e(beschreibung)}">
<meta property="og:url" content="{e(kanonisch)}">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="{e(kopf_titel)}">
{THEME_SKRIPT}
<script type="application/ld+json">{json_ld(ld)}</script>
<style>{CSS}</style>
</head>
<body>
<header><div class="wrap"><a href="{e(home)}">{e(kopf_titel)}</a><small>ein Angebot von <a href="{MVF_URL}">Monitor Versorgungsforschung</a></small></div></header>
<main class="wrap">
{inhalt}
</main>
<footer><div class="wrap"><a href="{e(home)}">Zum Hub</a> · <a href="{HUBS}">Alle Knowledge-Hubs</a> · <a href="{IMPRESSUM}">Impressum</a> · <a href="{DATENSCHUTZ}">Datenschutz</a></div></footer>
</body>
</html>
"""


# ------------------------------------------------------------------ Seiten --

def studienseite(s, portal, home):
    pmid = s["pmid"]
    url = f"{home}studie/{pmid}/"
    pubmed = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    titel = s.get("title", "").strip()
    erschienen = iso_datum(s.get("pubdate")) or s.get("year", "")
    erstautor = re.sub(r"\s+et al\.?$", "", (s.get("author") or "").strip())

    original = {
        "@type": "MedicalScholarlyArticle",
        "identifier": {"@type": "PropertyValue", "propertyID": "PMID", "value": pmid},
        "url": pubmed,
        "sameAs": pubmed,
    }
    if s.get("journal"):
        original["isPartOf"] = {"@type": "Periodical", "name": s["journal"]}
    if erschienen:
        original["datePublished"] = erschienen
    if erstautor:
        original["author"] = {"@type": "Person", "name": erstautor}

    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "@id": url + "#zusammenfassung",
        "url": url,
        "mainEntityOfPage": url,
        "headline": kurz(titel, 110),
        "description": s.get("sum", ""),
        "abstract": s.get("result", ""),
        "inLanguage": "de",
        "datePublished": s.get("aufgenommen", ""),
        "isBasedOn": original,
        "about": original,
        "isPartOf": {"@type": "WebSite", "name": portal["TITEL"], "url": home},
        "publisher": {"@type": "Organization", "name": "Monitor Versorgungsforschung", "url": MVF_URL},
        "isAccessibleForFree": True,
    }

    meta = [x for x in (e(s.get("author")), f"<i>{e(s.get('journal'))}</i>" if s.get("journal") else "",
                        f"erschienen {e(s.get('pubdate') or s.get('year'))}") if x]
    if s.get("added") and s.get("added") != s.get("pubdate"):
        meta.append(f"in PubMed seit {e(s['added'])}")
    meta.append(f"PMID {e(pmid)}")

    abschnitte = [("Worum es geht", s.get("sum")), ("Ergebnis", s.get("result")),
                  ("Übertragbarkeit auf Deutschland", s.get("transfer"))]
    inhalt = "\n".join([
        f'<p class="krumen"><a href="{e(home)}">{e(portal["TITEL"])}</a> › <a href="{e(home)}studie/">Studien</a></p>',
        f"<article>",
        f"<h1>{e(titel)}</h1>",
        f'<p class="meta">{" · ".join(meta)}</p>',
        f'<p class="ki">{KI_KENNZEICHEN}</p>',
        *[f"<section><h2>{k}</h2><p>{e(v)}</p></section>" for k, v in abschnitte if v],
        f'<p class="links"><a href="{pubmed}">Originalstudie in PubMed</a>'
        f'<a href="{e(home)}#studie-{e(pmid)}">Im Hub ansehen</a>'
        f'<a href="{e(home)}newsletter.html">Neue Studien per E-Mail</a></p>',
        f'<p class="hinweis">Auswahl und deutsche Zusammenfassung stammen von einer KI und sind nicht redaktionell geprüft. '
        f"Maßgeblich ist die Originalpublikation.</p>",
        f"</article>",
    ])
    return seite(f"{titel} · {portal['TITEL']}", kurz(s.get("sum") or titel), url, ld,
                 portal["TITEL"], home, inhalt)


def uebersicht(studien, portal, home):
    url = f"{home}studie/"
    gruppen = {}
    for s in studien:
        gruppen.setdefault((s.get("aufgenommen") or "")[:7], []).append(s)

    teile = [f'<p class="krumen"><a href="{e(home)}">{e(portal["TITEL"])}</a> › Studien</p>',
             f"<h1>Alle Studien im Hub {e(portal['THEMA'])}</h1>",
             f'<p class="meta">{len(studien)} Studien aus PubMed mit deutscher Zusammenfassung, '
             f"ausgewählt nach Übertragbarkeit auf das deutsche Versorgungssystem.</p>",
             f'<p class="ki">{KI_KENNZEICHEN}</p>']
    for monat in sorted(gruppen, reverse=True):
        jahr, _, mm = monat.partition("-")
        name = f"{MONATSNAMEN[int(mm) - 1]} {jahr}" if mm.isdigit() else "Ohne Datum"
        teile.append(f'<h2 class="monat">Aufgenommen im {name}</h2>\n<ul class="liste">')
        for s in gruppen[monat]:
            teile.append(f'<li><a href="{e(s["pmid"])}/">{e(s.get("title"))}</a>'
                         f'<span>{e(s.get("journal"))} · {e(s.get("pubdate") or s.get("year"))}</span></li>')
        teile.append("</ul>")

    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "url": url, "inLanguage": "de",
          "name": f"Alle Studien im Hub {portal['THEMA']}",
          "isPartOf": {"@type": "WebSite", "name": portal["TITEL"], "url": home},
          "publisher": {"@type": "Organization", "name": "Monitor Versorgungsforschung", "url": MVF_URL},
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(studien)}}
    return seite(f"Alle Studien · {portal['TITEL']}",
                 kurz(f"{len(studien)} Studien zu {portal['THEMA']} aus PubMed, jeweils mit deutscher "
                      f"Zusammenfassung, Ergebnis und Einordnung der Übertragbarkeit auf Deutschland."),
                 url, ld, portal["TITEL"], home, "\n".join(teile))


def sitemap(studien, wurzel, home):
    zeilen = ['<?xml version="1.0" encoding="UTF-8"?>', f"<!-- {KENNZEILE} -->",
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    neuester = max((s.get("aufgenommen") or "" for s in studien), default="")
    lm = lambda d: f"<lastmod>{d}</lastmod>" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "") else ""
    zeilen.append(f"<url><loc>{e(home)}</loc>{lm(neuester)}</url>")
    zeilen.append(f"<url><loc>{e(home)}studie/</loc>{lm(neuester)}</url>")
    for datei in sorted(wurzel.glob("*.html")):
        if NICHT_IN_SITEMAP.search(datei.name):
            continue
        if re.search(r'<meta[^>]+noindex', datei.read_text(encoding="utf-8", errors="replace")[:5000]):
            continue
        zeilen.append(f"<url><loc>{e(home)}{e(datei.name)}</loc></url>")
    for s in studien:
        zeilen.append(f"<url><loc>{e(home)}studie/{e(s['pmid'])}/</loc>{lm(s.get('aufgenommen'))}</url>")
    zeilen.append("</urlset>")
    return "\n".join(zeilen) + "\n"


def robots(home):
    return (f"# {KENNZEILE}\n"
            "# Alles frei: Suchmaschinen und KI-Dienste sollen die Studienseiten finden.\n"
            "User-agent: *\n"
            "Allow: /\n\n"
            f"Sitemap: {home}sitemap.xml\n")


# -------------------------------------------------------------------- Lauf --

def main():
    wurzel = Path.cwd()
    portal = json.loads((wurzel / "portal.json").read_text(encoding="utf-8"))
    archiv = json.loads((wurzel / "studien-archiv.json").read_text(encoding="utf-8"))
    home = f"https://{portal['DOMAIN']}/"

    studien = [s for s in archiv if re.fullmatch(r"\d+", str(s.get("pmid", ""))) and s.get("title")]
    # Neueste zuerst, bei gleichem Tag nach PMID - nie nach Zufall oder Uhrzeit.
    studien.sort(key=lambda s: (s.get("aufgenommen") or "", s["pmid"]), reverse=True)

    ordner = wurzel / "studie"
    geaendert = 0
    for s in studien:
        geaendert += schreiben(ordner / s["pmid"] / "index.html", studienseite(s, portal, home))
    geaendert += schreiben(ordner / "index.html", uebersicht(studien, portal, home))

    # Seiten von Studien, die nicht mehr im Archiv stehen (archiv_bereinigen.py),
    # verschwinden mit. Geloescht werden nur Ordner mit reiner Ziffernfolge.
    gueltig = {s["pmid"] for s in studien}
    entfernt = 0
    if ordner.is_dir():
        for alt in ordner.iterdir():
            if alt.is_dir() and alt.name.isdigit() and alt.name not in gueltig:
                shutil.rmtree(alt)
                entfernt += 1

    for name, inhalt in (("sitemap.xml", sitemap(studien, wurzel, home)), ("robots.txt", robots(home))):
        if eigene_datei(wurzel / name):
            geaendert += schreiben(wurzel / name, inhalt)
        else:
            print(f"::warning::{name} wird von Hand gepflegt (ohne Kennzeile) - nicht ueberschrieben.")

    print(f"Studienseiten: {len(studien)} Studien, {geaendert} Dateien geschrieben, {entfernt} entfernt.")


if __name__ == "__main__":
    sys.exit(main())
