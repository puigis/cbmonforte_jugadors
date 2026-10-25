"""
Cartell de resultats de la Lliga 3 Bandes (disseny nou, colors del club).

Llegeix dades/app/equips.json, agafa el partit de la setmana de cada equip
i genera imatges/lliga-AAAA-MM-DD.png (1080 x 1350, vertical d'Instagram).
Si aquella setmana no ha jugat cap equip, no genera res.

L'equip que juga a casa surt a l'esquerra; el que juga fora, a la dreta.
Un equip que no tenia partit (descansa) no surt al cartell. Si tenia partit al
calendari però no hi ha resultat, surt amb el segell AJORNAT.

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
    """C.B. 2000 CERDANYOLA “A” -> CB 2000 CERDANYOLA "A";  S.B.P.E. CENTELLES -> SBPE CENTELLES"""
    n = nom.replace("“", '"').replace("”", '"')
    n = re.sub(r"(?<![A-ZÀ-Ú])((?:[A-Z]\.\s?){2,})",
               lambda m: m.group(1).replace(".", "").replace(" ", "") + " ", n)
    n = re.sub(r"\b([A-Z]{2,5})\.(?=\s)", r"\1", n)   # SBPE. CENTELLES -> SBPE CENTELLES
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


PUBLICATS = ARREL / "dades" / "publicats.json"   # resultats ja sortits en algun cartell ("B-3", ...)


def llegeix_publicats():
    try:
        return set(json.loads(PUBLICATS.read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError):
        return set()


PUNTS = {"G": 2, "E": 1, "P": 0}


def marcador(m):
    """Resultat del partit en punts de les partides (2 per victòria, 1 per empat): p. ex. 6-2.
    Si la Federació no dona les partides individuals, el resultat oficial del match."""
    res = [r.get("res") for r in m.get("results") or []]
    if res and all(r in PUNTS for r in res):
        nos = sum(PUNTS[r] for r in res)
        return nos, 2 * len(res) - nos
    return m["punts_match"][0], m["punts_match"][1]


def converteix(equips_path, ref=None, dies=7, publicats=None):
    """Partits del cartell de la setmana, segons la data OFICIAL de cada jornada:
    - jornada oficial dins la setmana amb resultat -> resultat (encara que s'hagi jugat abans, avançat)
    - jornada oficial dins la setmana sense resultat -> AJORNAT
    - partit d'una jornada anterior que ja té resultat i encara no ha sortit en cap cartell
      (s'havia ajornat i s'ha jugat després) -> resultat amb la nota "Partit ajornat"."""
    ref = datetime.date.fromisoformat(ref) if ref else datetime.date.today()
    inici = ref - datetime.timedelta(days=dies - 1)
    dia = datetime.date.fromisoformat
    publicats = llegeix_publicats() if publicats is None else publicats
    app = json.load(open(equips_path, encoding="utf-8"))
    partits, jornades, dates, recuperats = [], Counter(), Counter(), Counter()
    for e in app["equips"]:
        lletra = re.search(r'"(\w)"', e["equip"].replace("“", '"').replace("”", '"')).group(1)
        base = {"equip": lletra, "divisio": divisio(e["competicio"])}
        resultats = {str(m["jornada"]): m for m in e["matches"] if m.get("punts_match")}
        for c in sorted(e.get("calendar", []), key=lambda c: c["date"]):
            oficial = dia(c["date"])
            m = resultats.get(str(c["jornada"]))
            if inici <= oficial <= ref:
                fila = {**base, "jornada": str(c["jornada"]), "casa": c["venue"] == "L",
                        "rival": nom_club(c["rival"])}
                if m:
                    fila.update(zip(("monforte", "contrari"), marcador(m)))
                else:
                    fila["ajornat"] = True
                partits.append(fila)
                jornades[str(c["jornada"])] += 1
                dates[c["date"]] += 1
            elif oficial < inici and m and f"{lletra}-{c['jornada']}" not in publicats:
                recuperats[m["date"]] += 1
                partits.append({**base, "jornada": str(c["jornada"]), "casa": c["venue"] == "L",
                                "rival": nom_club(c["rival"]), **dict(zip(("monforte", "contrari"), marcador(m))),
                                "nota": f"Partit ajornat · J{c['jornada']}"})
    # Si no hi ha cap resultat, o no hi ha partits o la Federació encara no els ha publicat:
    # millor no generar res que un cartell ple d'ajornats.
    if not any(not p.get("ajornat") for p in partits):
        return None
    partits.sort(key=lambda p: (p["equip"], "nota" in p))
    if not jornades:   # setmana sense jornada oficial: només partits ajornats que ja s'han jugat
        return {"jornada": "Partit ajornat" if len(partits) == 1 else "Partits ajornats",
                "data": data_llarga(max(recuperats)), "partits": partits}
    return {"jornada": f"Jornada {jornades.most_common(1)[0][0]}",
            "data": data_llarga(dates.most_common(1)[0][0]),
            "partits": partits}


def marca_publicats(dades):
    """Apunta els resultats que han sortit al cartell perquè no es tornin a posar."""
    fets = llegeix_publicats() | {f"{p['equip']}-{p['jornada']}" for p in dades["partits"] if not p.get("ajornat")}
    PUBLICATS.write_text(json.dumps(sorted(fets), ensure_ascii=False, indent=0), encoding="utf-8")


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
    marca_publicats(dades)
    (SORTIDA / f"lliga-{dia}.json").write_text(json.dumps(dades, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dades, ensure_ascii=False, indent=2))
    print(f"Cartell desat a {sortida.relative_to(ARREL)}")


if __name__ == "__main__":
    main()
