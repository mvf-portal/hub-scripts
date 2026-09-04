# hub-scripts

Die gemeinsamen Skripte der MVF-Knowledge-Hubs. Sie lagen bis zum 04.09.2026 in
jedem der zwoelf Portal-Repos als eigene Kopie - 96 Dateien, die von Hand
synchron gehalten werden mussten.

## Wie sie in die Portale kommen

Die Workflows der Portale holen dieses Repo zur Laufzeit:

```yaml
- name: Gemeinsame Skripte auschecken
  uses: actions/checkout@v4
  with:
    repository: mvf-portal/hub-scripts
    ref: stabil
    path: scripts/gemeinsam
```

und rufen danach `python scripts/gemeinsam/<skript>.py` auf, mit
`PYTHONPATH: scripts`, damit `thema.py` des Portals importierbar bleibt.

## Zwei Branches, mit Absicht

- **`main`** - hier wird entwickelt.
- **`stabil`** - das, was die zwoelf Portale jeden Morgen ausfuehren.

Ausgerollt wird mit einem Befehl:

```
git push origin main:stabil
```

Das ist der ganze Unterschied zum frueheren `vorlage-abgleich.py --uebernehmen`
ueber zwoelf Repos - aber es bleibt ein **bewusster** Schritt. Ein Checkout von
`main` haette geheissen: Jeder Commit laeuft am naechsten Morgen in zwoelf
Produktivsystemen, ohne dass jemand dazwischen zustimmt.

## Was hier NICHT hineingehoert

`thema.py` - das ist die einzige Datei, die sich von Portal zu Portal
inhaltlich unterscheidet, und sie bleibt dort. Ebenso die drei Workflows und
die HTML-Dateien: Sie tragen Platzhalter, die je Portal ersetzt werden.

Die drei Skripte, die es nur im Versorgungsforschungs-Portal gibt
(`ausschreibungen.py`, `radar_themen.py`), bleiben ebenfalls dort - sie laufen
zentral und nur einmal.
