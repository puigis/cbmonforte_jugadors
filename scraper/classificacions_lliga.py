"""
Classificacions de la Lliga 3 Bandes dels equips del CB Monforte (disseny nou).

Llegeix dades/app/equips.json i genera una imatge per equip (carrusel d'Instagram):
  imatges/classificacio-AAAA-MM-DD-A.png ... -E.png   (1080 x 1350)

Opcions (variables d'entorn):
  DATA=2026-10-12   Dia que surt al nom dels fitxers (per defecte avui).
"""
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cartell_lliga import ARREL, EQUIPS, SORTIDA, data_llarga, divisio, nom_club  # noqa: E402

PLANTILLA = Path(__file__).resolve().parent / "cartell_lliga" / "classificacio.html"


def lletra(equip):
    return equip.replace("“", '"').replace("”", '"').split('"')[1]


def dades_equips():
    app = json.load(open(EQUIPS, encoding="utf-8"))
    sortida = []
    for e in app["equips"]:
        files = e.get("classificacio") or []
        if not files:
            continue
        jugades = [c for c in e.get("calendar", []) if c.get("played")]
        if jugades:
            darrera = max(jugades, key=lambda c: c["date"])
            jornada, data = f"Jornada {darrera['jornada']}", data_llarga(darrera["date"])
        else:
            jornada, data = "Inici de lliga", data_llarga(datetime.date.today().isoformat())
        sortida.append({
            "equip": lletra(e["equip"]),
            "divisio": divisio(e["competicio"]),
            "jornada": jornada,
            "data": data,
            "files": [{"pos": f["pos"], "equip": "CB MONFORTE " + lletra(e["equip"]) if f.get("mon") else nom_club(f["equip"]),
                       "j": f["j"], "pp": f["pp"], "pm": f["pm"], "mon": bool(f.get("mon"))} for f in files],
        })
    return sorted(sortida, key=lambda x: x["equip"])


def main():
    dia = os.environ.get("DATA") or datetime.date.today().isoformat()
    equips = dades_equips()
    if not equips:
        print("No hi ha classificacions: no es genera res.")
        return
    from playwright.sync_api import sync_playwright
    SORTIDA.mkdir(exist_ok=True)
    (SORTIDA / f"classificacio-{dia}.json").write_text(json.dumps(equips, ensure_ascii=False, indent=2), encoding="utf-8")
    with sync_playwright() as p:
        nav = p.chromium.launch()
        for d in equips:
            pag = nav.new_page(viewport={"width": 1080, "height": 1350})
            pag.add_init_script(f"window.DADES = {json.dumps(d, ensure_ascii=False)};")
            pag.goto(PLANTILLA.as_uri())
            pag.wait_for_load_state("networkidle")
            pag.evaluate("document.fonts.ready")
            fitxer = SORTIDA / f"classificacio-{dia}-{d['equip']}.png"
            pag.screenshot(path=str(fitxer))
            pag.close()
            print(f"Desada {fitxer.relative_to(ARREL)}")
        nav.close()


if __name__ == "__main__":
    main()
