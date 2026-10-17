"""
Cartell de resultats de la Lliga 3 Bandes (disseny nou, colors del club).

Llegeix dades/app/equips.json, agafa el partit de la setmana de cada equip
i genera imatges/lliga-AAAA-MM-DD.png (1080 x 1350, vertical d'Instagram).
Si aquella setmana no ha jugat cap equip, no genera res.

L'equip que juga a casa surt a l'esquerra; el que juga fora, a la dreta.
Un equip que no ha jugat (descansa) no surt al cartell.

Opcions (variables d'entorn):
  DATA=2026-10-11   Dia de referència (per defecte avui).
  DIES=7            Quants dies enrere es miren.
"""
import datetime
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ARREL = Path(__file__).resolve().parent.parent
EQUIPS = ARREL / "dades" / "app" / "equips.json"
SORTIDA = ARREL / "imatges"
PLANTILLA = Path(__file__).resolve().parent / "cartell_lliga" / "plantilla.html"

MESOS = ["gener", "febrer", "març", "abril", "maig", "juny", "juliol",
         "agost", "setembre", "octubre", "novembre", "desembre"]


def data_llarga(iso):
    d = datetime.date.fromisoformat(iso)
    mes = MESOS[d.month - 1]
    de = "d'" if mes[0] in "aeiou" else "de "
    return f"{d.day} {de}{mes} de {d.year}"


def nom_club(nom):
    """C.B. 2000 CERDANYOLA “A” -> CB 2000 CERDANYOLA "A" """
    n = nom.replace("“", '"').replace("”", '"')
    n = re.sub(r"\b([A-Z])\.\s?(?=[A-Z]\.)", r"\1", n)   # C.B. -> CB.
    n = re.sub(r"\b([A-Z]{2})\.", r"\1", n)                # CB. -> CB
    n = re.sub(r"\s+", " ", n).strip()
    return n.upper()


def divisio(competicio):
    parts = [p.strip() for p in competicio.split("·")]
    div = parts[1] if len(parts) > 1 else ""
    grup = parts[2] if len(parts) > 2 else ""
    noms = {"Honor": "Divisió d'Honor", "1a Divisió": "Primera Divisió",
            "2a Divisió": "Segona Divisió", "3a Divisió": "Tercera Divisió",
            "4a Divisió": "Quarta Divisió"}
    text = noms.get(div, div)
    return f"{text} · {grup}" if grup else text


def converteix(equips_path, ref=None, dies=7):
    ref = datetime.date.fromisoformat(ref) if ref else datetime.date.today()
    inici = ref - datetime.timedelta(days=dies - 1)
    app = json.load(open(equips_path, encoding="utf-8"))
    partits, jornades, dates = [], Counter(), Counter()
    for e in app["equips"]:
        lletra = re.search(r'"(\w)"', e["equip"].replace("“", '"').replace("”", '"')).group(1)
        jugats = [m for m in e["matches"]
                  if m.get("punts_match") and inici <= datetime.date.fromisoformat(m["date"]) <= ref]
        if not jugats:
            continue
        m = max(jugats, key=lambda x: x["date"])
        pm, pr = m["punts_match"]
        partits.append({"equip": lletra, "divisio": divisio(e["competicio"]),
                        "casa": m["venue"] == "L", "rival": nom_club(m["rival"]),
                        "monforte": pm, "contrari": pr})
        jornades[m["jornada"]] += 1
        dates[m["date"]] += 1
    if not partits:
        return None
    partits.sort(key=lambda p: p["equip"])
    return {"jornada": f"Jornada {jornades.most_common(1)[0][0]}",
            "data": data_llarga(dates.most_common(1)[0][0]),
            "partits": partits}


def genera_png(dades, sortida):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pag = nav.new_page(viewport={"width": 1080, "height": 1350})
        pag.add_init_script(f"window.DADES = {json.dumps(dades, ensure_ascii=False)};")
        pag.goto(PLANTILLA.as_uri())
        pag.wait_for_load_state("networkidle")
        pag.evaluate("document.fonts.ready")
        pag.screenshot(path=str(sortida))
        nav.close()


def main():
    ref = os.environ.get("DATA") or None
    dies = int(os.environ.get("DIES") or 7)
    dades = converteix(EQUIPS, ref, dies)
    if dades is None:
        print("Aquesta setmana no hi ha partits de lliga: no es genera cartell.")
        return
    dia = ref or datetime.date.today().isoformat()
    SORTIDA.mkdir(exist_ok=True)
    sortida = SORTIDA / f"lliga-{dia}.png"
    genera_png(dades, sortida)
    print(json.dumps(dades, ensure_ascii=False, indent=2))
    print(f"Cartell desat a {sortida.relative_to(ARREL)}")


if __name__ == "__main__":
    main()
