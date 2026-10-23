# -*- coding: utf-8 -*-
"""Probe der Newsletter-Rubrik "Neu zugelassen und empfohlen".

    py rubrik_probe.py

Ruft nur `zulassung_eintraege()` und `rubriken_html()` auf und zeigt, was in
der Ausgabe stuende - **ohne Mailchimp anzufassen**. Geprueft wird in drei
Hubs: einem mit Arzneimitteln (Onkologie), einem mit DiGA (KI) und einem
ohne alles (Pflege), wo die Rubrik entfallen muss.

Drei Dinge, auf die dabei zu sehen ist:

  - Steht die richtige Stufenmarke dabei? Eine FDA-Zulassung als
    "Zugelassen" in der Hausfarbe waere eine europaeische - der teuerste
    Fehler dieser Rubrik.
  - Steht ein Rohfeld im HTML? `gebiet_mesh` ist der englische MeSH-Begriff
    und hat in Lesertext nichts zu suchen.
  - Bleibt die Rubrik leer, wo nichts zu melden ist?
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# Sieht absichtlich AUS dem Repo heraus: Die Portale liegen als
# Schwesterordner neben hub-scripts. Abgeleitet aus dem eigenen Ort, nicht
# fest eingetragen - sonst laeuft die Probe nur auf einem Rechner.
HUBS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HUBS / "hub-scripts"))

for portal in ("onkologie-portal", "ki-gesundheit-portal", "pflege-portal"):
    import os
    os.chdir(HUBS / portal)
    # scripts/ des Portals fuer thema.py, hub-scripts fuer den Rest
    for pfad in (str(HUBS / portal / "scripts"), str(HUBS / "hub-scripts")):
        if pfad in sys.path: sys.path.remove(pfad)
        sys.path.insert(0, pfad)
    for modul in ("mailchimp_entwurf", "zulassungen_hinweis"):
        sys.modules.pop(modul, None)
    import mailchimp_entwurf as m

    eintraege = m.zulassung_eintraege()
    print(f"\n=== {portal} : {len(eintraege)} Eintrag/Eintraege ===")
    for e in eintraege:
        marke = m.STUFEN.get(e["stufe"], ("?", ""))[0]
        print(f"  [{marke}] {e['datum']}  {e['name'][:34]}")
        print(f"      {e['satz'][:110]}")
    html = m.rubriken_html([], [], eintraege)
    nur_text = re.sub(r"<[^>]+>", " ", html)
    nur_text = " ".join(nur_text.split())
    print(f"  HTML: {len(html)} Zeichen" + (" (leer)" if not eintraege else ""))
    if eintraege:
        anfang = nur_text.find("Neu zugelassen")
        print("  Im Text:", nur_text[anfang:anfang + 240])
        # Gegenprobe: Der englische Rohbegriff darf NICHT drinstehen.
        verboten = [w for w in ("Neoplasm", "Carcinoma", "gebiet_mesh",
                                "indikation_en") if w in html]
        print("  Rohfelder im HTML:", verboten or "keine (richtig)")
