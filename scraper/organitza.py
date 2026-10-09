"""
Converteix les pàgines en brut de dades/brut/ en taules netes (CSV) i en fitxers
JSON preparats per a l'app del CB Monforte.

Sortida:
  dades/competicions.csv              Totes les competicions (lligues i individuals)
  dades/jugadors.csv                  Tots els jugadors amb el seu club
  dades/partides.csv                  Totes les partides jugador contra jugador
  dades/encontres.csv                 Encontres de lliga equip contra equip
  dades/classificacions_lliga.csv     Classificacions dels grups de lliga
  dades/classificacions_individuals.csv  Classificacions finals dels individuals
  dades/rankings.csv                  Rànquings de la Federació (tot l'historial)
  dades/monforte/index.json           Índex de tot el que hi ha a dades/monforte/
  dades/monforte/lligues/<lliga>/<equip>.json   Un fitxer per equip, temporada actual (format app Monforte C)
  dades/monforte/modalitats/<modalitat>.json    Jugadors del Monforte per modalitat, temporada actual
"""

import csv
import datetime
import glob
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ARREL = Path(__file__).resolve().parent.parent
BRUT = ARREL / "dades" / "brut"
DADES = ARREL / "dades"
MONFORTE = DADES / "monforte"

MODALITATS_RANKING = {"1": "Tres bandes", "2": "Lliure", "3": "Quadre 47/2", "4": "Banda", "6": "Quadre 71/2"}
DATA = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
PARELL = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


# ---------------------------------------------------------------- utilitats

def norm(t):
    t = (t or "").replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"').replace("''", '"')
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", norm(t).lower()).strip("-")[:70]


def bonic(nom):
    return re.sub(r"\s+", " ", nom or "").strip().title()


def data_de(text):
    m = DATA.search(text or "")
    if not m or m.group(1) == "0000":
        return ""
    return m.group(0)


def temporada(data):
    if not data:
        return ""
    a, m = int(data[:4]), int(data[5:7])
    inici = a if m >= 8 else a - 1
    return f"{inici}-{(inici + 1) % 100:02d}"


def enter(t):
    try:
        return int(str(t).strip())
    except (TypeError, ValueError):
        return None


def decimal(t):
    try:
        return float(str(t).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def parell(t):
    m = PARELL.match(t or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def modalitat(text):
    n = norm(text)
    if "QUILLES" in n:
        return "5 quilles"
    if "BIATH" in n or "BIATL" in n:
        return "Biathló"
    if "ARTISTIC" in n:
        return "Artístic"
    if "71/2" in n:
        return "Quadre 71/2"
    if "47/2" in n or "QUADRE" in n:
        return "Quadre 47/2"
    if "3 BANDES" in n or "TRES BANDES" in n or "3B" in n.split():
        return "Tres bandes"
    if "BANDA" in n:
        return "Banda"
    if "LLIURE" in n:
        return "Lliure"
    if "4 MOD" in n:
        return "4 Modalitats"
    if "JOC CURT" in n:
        return "Joc curt"
    return "Altres"


def club_clau(nom):
    """'C.B. MONFORTE "C"' -> 'MONFORTE';  'MOLINS A' -> 'MOLINS'."""
    n = norm(nom).replace('"', " ")
    n = re.sub(r"\b(C\s*\.?\s*B|S\s*\.?\s*B(\s*\.?\s*P\s*\.?\s*E)?|B\s*\.?\s*C|S\s*\.?\s*C|S\s*\.?\s*E|CLUB|BILLAR)\b\.?", " ", n)
    n = re.sub(r"[^A-Z0-9' ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    n = re.sub(r"\s[A-H]$", "", n)
    return n.strip()


def lletra_equip(nom):
    n = norm(nom)
    m = re.search(r'"\s*([A-H])\s*"\s*$', n) or re.search(r"\s([A-H])$", n)
    return m.group(1) if m else ""


def es_monforte(nom):
    return "MONFORTE" in norm(nom)


def files(pagina, capcalera):
    """Files de la primera taula que té aquesta columna, com a llistes de cel·les."""
    for t in pagina["taules"]:
        if capcalera in t["capcaleres"]:
            return [r for r in t["files"] if len(r) > 1]
    return []


def textos(fila):
    return [c["text"] for c in fila]


def enllac_id(fila, patro):
    for c in fila:
        m = re.search(patro, c.get("enllac", ""))
        if m:
            return m.group(1)
    return None


def escriu_csv(nom, camps, files_):
    with open(DADES / nom, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=camps, extrasaction="ignore")
        w.writeheader()
        w.writerows(files_)
    print(f"  {nom}: {len(files_)} files")


def escriu_json(cami, dades):
    cami.parent.mkdir(parents=True, exist_ok=True)
    with open(cami, "w", encoding="utf-8") as f:
        json.dump(dades, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- càrrega

def carrega():
    pagines = {}
    for f in glob.glob(str(BRUT / "*" / "*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for linia in fh:
                d = json.loads(linia)
                pagines[d["url"].split("/frontend/", 1)[1]] = d
    return pagines


def de_tipus(pagines, prefix):
    for clau, p in pagines.items():
        if clau.startswith(prefix):
            ids = [int(x) for x in re.findall(r"\d+", clau.split("?")[0])]
            yield clau, ids, p


# ---------------------------------------------------------------- lligues

def processa_lligues(pagines):
    lligues, grups, encontres, partides, classificacions = {}, {}, [], [], []

    for _, (l,), p in de_tipus(pagines, "lligues/divisions/"):
        lligues[l] = {"nom": p["titols"][-1] if p["titols"] else f"Lliga {l}", "divisions": {}}
    for _, (l, d), p in de_tipus(pagines, "lligues/grups/"):
        if l in lligues:
            lligues[l]["divisions"][d] = p["titols"][-1] if p["titols"] else ""

    # jornades de cada grup
    jornada_de = {}
    for _, (l, d, g), p in de_tipus(pagines, "lligues/jornades/"):
        grups[(l, d, g)] = {"nom": p["titols"][-1] if p["titols"] else "", "jornades": []}
        for fila in files(p, "Jornada"):
            t = textos(fila)
            e = enllac_id(fila, r"/encontres/\d+/\d+/\d+/(\d+)")
            num = re.search(r"\d+", t[0])
            info = {"id": e, "num": str(int(num.group())) if num else t[0], "data": data_de(t[1] if len(t) > 1 else "")}
            grups[(l, d, g)]["jornades"].append(info)
            if e:
                jornada_de[(l, d, g, int(e))] = info

    # temporada de cada lliga = data més antiga de les seves jornades
    for l, lliga in lligues.items():
        dates = sorted(j["data"] for (gl, _, _), g in grups.items() if gl == l for j in g["jornades"] if j["data"])
        lliga["temporada"] = temporada(dates[0]) if dates else ""
        lliga["modalitat"] = modalitat(lliga["nom"])

    # encontres i partides
    for _, (l, d, g, j), p in de_tipus(pagines, "lligues/encontres/"):
        lliga = lligues.get(l, {"nom": "", "divisions": {}, "temporada": "", "modalitat": ""})
        jinfo = jornada_de.get((l, d, g, j), {"num": "", "data": ""})
        comuns = {
            "lliga_id": l, "competicio": lliga["nom"], "temporada": lliga["temporada"],
            "divisio": lliga["divisions"].get(d, ""), "grup": grups.get((l, d, g), {}).get("nom", ""),
            "jornada": jinfo["num"], "data": jinfo["data"],
        }
        for fila in files(p, "Encontre"):
            t = textos(fila)
            if " - " not in t[0]:
                continue
            local, visitant = [x.strip() for x in t[0].split(" - ", 1)]
            ppl, ppv = parell(t[1])
            pml, pmv = parell(t[2])
            pid = enllac_id(fila, r"/partides/\d+/\d+/\d+/\d+/(\d+)")
            enc = dict(comuns, encontre_id=pid or "", grup_id=g, equip_local=local, equip_visitant=visitant,
                       punts_parcials_local=ppl, punts_parcials_visitant=ppv,
                       punts_match_local=pml, punts_match_visitant=pmv, estat=t[3] if len(t) > 3 else "")
            encontres.append(enc)
            if not pid:
                continue
            pp = pagines.get(f"lligues/partides/{l}/{d}/{g}/{j}/{pid}")
            if not pp:
                continue
            for taula in pp["taules"]:
                if "Entrades" not in taula["capcaleres"]:
                    continue
                cap = taula["capcaleres"]
                eq_l, eq_v = (cap[0] or local), (cap[1] or visitant)
                for ordre, fila2 in enumerate(taula["files"], 1):
                    c = textos(fila2)
                    if len(c) < 8:
                        continue
                    sml, carl = parell(c[2])
                    smv, carv = parell(c[3])
                    ptl, ptv = parell(c[7])
                    if carl is None or carv is None:
                        continue
                    partides.append(dict(
                        comuns, font="lliga", competicio_id=f"L{l}", fase=comuns["grup"], encontre_id=pid,
                        ordre=ordre, modalitat=modalitat(c[5]) if c[5] else lliga["modalitat"],
                        jugador_local=c[0], equip_local=eq_l, serie_major_local=sml, caramboles_local=carl,
                        jugador_visitant=c[1], equip_visitant=eq_v, serie_major_visitant=smv, caramboles_visitant=carv,
                        entrades=enter(c[4]), punts_local=ptl, punts_visitant=ptv, estat=c[6]))

    for _, (l, d, g), p in de_tipus(pagines, "lligues/classificacio/"):
        lliga = lligues.get(l, {"nom": "", "divisions": {}, "temporada": ""})
        for fila in files(p, "Equip"):
            t = textos(fila)
            if len(t) < 5:
                continue
            classificacions.append({
                "lliga_id": l, "competicio": lliga["nom"], "temporada": lliga["temporada"],
                "divisio": lliga["divisions"].get(d, ""), "grup": grups.get((l, d, g), {}).get("nom", ""),
                "grup_id": g, "posicio": enter(t[0]), "equip": t[1], "punts_match": enter(t[2]),
                "punts_parcials": enter(t[3]), "jugats": enter(t[4])})

    # clubs de jugadors inscrits (temporada actual)
    inscrits = []
    for _, (l, _club), p in de_tipus(pagines, "lligues/participants/"):
        titol = p["titols"][-1] if p["titols"] else ""
        club = titol.split(" del club ")[-1] if " del club " in titol else ""
        for fila in files(p, "Jugador"):
            t = textos(fila)
            inscrits.append({"jugador": t[1], "club": club, "temporada": lligues.get(l, {}).get("temporada", "")})

    return lligues, grups, encontres, partides, classificacions, inscrits


# ---------------------------------------------------------------- individuals

def processa_individuals(pagines):
    comps, partides, classificacions = {}, [], []
    for _, (c,), p in de_tipus(pagines, "individuals/divisions/"):
        nom = p["titols"][-1] if len(p["titols"]) > 1 else f"Individual {c}"
        divs = {}
        for fila in files(p, "Divisió"):
            d = enllac_id(fila, r"/fases/\d+/(\d+)")
            if d:
                divs[int(d)] = fila[0]["text"]
        comps[c] = {"nom": nom, "modalitat": modalitat(nom), "divisions": divs, "dates": []}

    # fases: noms i dates de grups i eliminatòries
    fase_info = {}
    for _, (c, d), p in de_tipus(pagines, "individuals/fases/"):
        for col, patro in (("Fase", r"/grups/\d+/\d+/(\d+)"), ("Eliminatòria", r"/partides-eliminatories/\d+/\d+/(\d+)")):
            for fila in files(p, col):
                f = enllac_id(fila, patro)
                t = textos(fila)
                if f:
                    fase_info[(col, c, d, int(f))] = {"nom": t[0], "data": data_de(t[1] if len(t) > 1 else "")}
    grup_info = {}
    for _, (c, d, f), p in de_tipus(pagines, "individuals/grups/"):
        fase = fase_info.get(("Fase", c, d, f), {"nom": "", "data": ""})
        for fila in files(p, "Club organitzador"):
            g = enllac_id(fila, r"/partides-grup/\d+/\d+/\d+/(\d+)")
            t = textos(fila)
            if g:
                grup_info[(c, d, f, int(g))] = {"nom": f"{fase['nom']} · {t[0]}".strip(" ·"),
                                                "data": data_de(t[3] if len(t) > 3 else "") or fase["data"]}

    def afegeix(c, d, nom_fase, data, pagina):
        comp = comps.get(c, {"nom": f"Individual {c}", "modalitat": "Altres", "divisions": {}, "dates": []})
        if data:
            comp["dates"].append(data)
        for ordre, fila in enumerate(files(pagina, "Visitant"), 1):
            t = textos(fila)
            if len(t) < 7:
                continue
            jl, jv = t[0], t[3]
            carl, carv, ent = enter(t[2]), enter(t[5]), enter(t[6])
            if not jl or not jv or norm(jl) == norm(jv) or carl is None or carv is None:
                continue
            if not ent and not carl and not carv:
                continue
            ptl, ptv = (2, 0) if carl > carv else (0, 2) if carl < carv else (1, 1)
            partides.append({
                "font": "individual", "competicio_id": f"I{c}", "competicio": comp["nom"], "temporada": "",
                "divisio": comp["divisions"].get(d, ""), "fase": nom_fase, "grup": nom_fase, "jornada": "",
                "data": data, "encontre_id": "", "ordre": ordre, "modalitat": comp["modalitat"],
                "jugador_local": jl, "equip_local": "", "serie_major_local": enter(t[1]), "caramboles_local": carl,
                "jugador_visitant": jv, "equip_visitant": "", "serie_major_visitant": enter(t[4]),
                "caramboles_visitant": carv, "entrades": ent, "punts_local": ptl, "punts_visitant": ptv,
                "estat": t[8] if len(t) > 8 else "", "_c": c})

    for _, (c, d, f, g), p in de_tipus(pagines, "individuals/partides-grup/"):
        info = grup_info.get((c, d, f, g), {"nom": "", "data": fase_info.get(("Fase", c, d, f), {}).get("data", "")})
        afegeix(c, d, info["nom"], info["data"], p)
    for _, (c, d, e), p in de_tipus(pagines, "individuals/partides-eliminatories/"):
        info = fase_info.get(("Eliminatòria", c, d, e), {"nom": "Eliminatòria", "data": ""})
        afegeix(c, d, info["nom"], info["data"], p)

    for c, comp in comps.items():
        comp["temporada"] = temporada(sorted(comp["dates"])[0]) if comp["dates"] else ""
    for pt in partides:
        pt["temporada"] = temporada(pt["data"]) or comps.get(pt.pop("_c"), {}).get("temporada", "")

    for _, (c, d), p in de_tipus(pagines, "individuals/divisio-classificacio-final/"):
        comp = comps.get(c, {"nom": "", "modalitat": "", "divisions": {}, "temporada": ""})
        for fila in files(p, "Club"):
            t = textos(fila)
            if len(t) < 9:
                continue
            classificacions.append({
                "competicio_id": f"I{c}", "competicio": comp["nom"], "modalitat": comp["modalitat"],
                "temporada": comp.get("temporada", ""), "divisio": comp["divisions"].get(d, ""),
                "posicio": enter(t[0]), "jugador": t[1], "club": t[2], "punts": enter(t[3]),
                "partides": enter(t[4]), "caramboles": enter(t[5]), "entrades": enter(t[6]),
                "mitjana_general": decimal(t[7]), "mitjana_particular": decimal(t[8])})
    return comps, partides, classificacions


# ---------------------------------------------------------------- rànquings

def processa_rankings(pagines):
    out = []
    for clau, _, p in de_tipus(pagines, "rankings/"):
        if not ("llistat-dades" in clau or "historial-dades" in clau):
            continue
        qs = parse_qs(urlparse("x://y/" + clau).query)
        mod = MODALITATS_RANKING.get(qs.get("idmodalitat", [""])[0], "Altres")
        data = data_de(" ".join(p["titols"]))
        for fila in files(p, "Jugador"):
            t = textos(fila)
            if len(t) < 7 or enter(t[0]) is None:
                continue
            idj = enllac_id(fila, r"idjugador=(\d+)")
            if len(t) >= 10:   # format amb columnes MR i Rang
                mj, c, e, ppt, dfin = t[2], t[5], t[6], t[7], t[8]
            else:
                mj, c, e, ppt, dfin = t[2], t[3], t[4], t[5], t[6]
            p_, pt_ = parell(ppt)
            out.append({"data": data, "modalitat": mod, "posicio": enter(t[0]), "jugador": t[1],
                        "jugador_fcb_id": idj or "", "mitjana": decimal(mj), "caramboles": enter(c),
                        "entrades": enter(e), "partides": p_, "partides_total": pt_, "definitiu": dfin})
    out.sort(key=lambda r: (r["data"], r["modalitat"], r["posicio"] or 0))
    return out


def dedueix_modalitat(comps, partides_ind):
    """Molts opens no diuen la modalitat al nom. Es dedueix per la mitjana de les seves partides:
    a tres bandes la mitjana típica és 0,3-1,0; a banda 1-2,5; a lliure, sobre 150 caramboles, molt més alta."""
    mitjanes = defaultdict(list)
    for pt in partides_ind:
        if pt["modalitat"] == "Altres" and pt["entrades"]:
            mitjanes[pt["competicio_id"]].append((pt["caramboles_local"] + pt["caramboles_visitant"]) / 2 / pt["entrades"])
    for cid, v in mitjanes.items():
        if len(v) < 5:
            continue
        med = sorted(v)[len(v) // 2]
        mod = "Tres bandes" if med < 1.1 else "Banda" if med < 2.2 else "Lliure" if med > 8 else None
        if mod:
            comps[int(cid[1:])]["modalitat"] = mod
            comps[int(cid[1:])]["deduida"] = True
    for pt in partides_ind:
        pt["modalitat"] = comps.get(int(pt["competicio_id"][1:]), {}).get("modalitat", pt["modalitat"])


# ---------------------------------------------------------------- clubs per jugador

def clubs_per_temporada(partides_lliga, class_ind, inscrits):
    """{slug: {temporada: club}}, triant el club més vist en cada temporada."""
    comptes = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for p in partides_lliga:
        for costat in ("local", "visitant"):
            comptes[slug(p[f"jugador_{costat}"])][p["temporada"]][club_clau(p[f"equip_{costat}"])] += 1
    for c in class_ind:
        if c["club"]:
            comptes[slug(c["jugador"])][c["temporada"]][club_clau(c["club"])] += 1
    for i in inscrits:
        if i["club"]:
            comptes[slug(i["jugador"])][i["temporada"]][club_clau(i["club"])] += 3
    return {j: {t: max(cl, key=cl.get) for t, cl in temps.items() if t} for j, temps in comptes.items()}


def club_en(clubs, jugador, temp):
    temps = clubs.get(slug(jugador), {})
    if not temps:
        return ""
    if temp in temps:
        return temps[temp]
    anteriors = [t for t in temps if t < temp]
    posteriors = [t for t in temps if t > temp]
    if anteriors:
        return temps[max(anteriors)]
    return temps[min(posteriors)] if posteriors else ""


# ---------------------------------------------------------------- sortides Monforte

def mitjana_inicial(rankings_idx, jugador, mod, abans_de):
    """Mitjana del darrer rànquing anterior a la data indicada."""
    millor = None
    for r in rankings_idx.get((slug(jugador), mod), []):
        if not abans_de or r["data"] <= abans_de:
            millor = r
    if millor is None and rankings_idx.get((slug(jugador), mod)):
        millor = rankings_idx[(slug(jugador), mod)][0]
    return f"{millor['mitjana']:.3f}" if millor and millor["mitjana"] is not None else ""


def resultat(propis, rival):
    if propis is None or rival is None:
        return ""
    return "G" if propis > rival else "P" if propis < rival else "E"


def equips_monforte(lligues, grups, encontres, partides_lliga, rankings_idx, ara):
    """Un JSON per equip del Monforte i temporada, amb el mateix format que l'app Monforte C."""
    per_equip = defaultdict(list)
    for e in encontres:
        for costat in ("local", "visitant"):
            if es_monforte(e[f"equip_{costat}"]):
                per_equip[(e["lliga_id"], e["grup_id"], norm(e[f"equip_{costat}"]))].append((costat, e))
    partides_de = defaultdict(list)
    for p in partides_lliga:
        partides_de[p["encontre_id"]].append(p)

    index = []
    usats = set()
    ordenats = sorted(per_equip.items(), key=lambda kv: -len(kv[1]))   # el grup principal (més jornades) primer
    for (l, g, _), llista in ordenats:
        lliga = lligues.get(l, {})
        costat0, e0 = llista[0]
        nom_equip = e0[f"equip_{costat0}"]
        lletra = lletra_equip(nom_equip) or "unic"
        dates = sorted(e["data"] for _, e in llista if e["data"])
        inici = dates[0] if dates else ""
        jugadors, matches, calendari = {}, [], []
        for costat, e in sorted(llista, key=lambda x: (enter(x[1]["jornada"]) or 0)):
            venue = "L" if costat == "local" else "F"
            rival = e["equip_visitant"] if costat == "local" else e["equip_local"]
            ps = partides_de.get(e["encontre_id"], []) if e["encontre_id"] else []
            jugat = bool(ps) or "FINALITZ" in norm(e["estat"])
            calendari.append({"jornada": e["jornada"], "date": e["data"], "rival": rival, "venue": venue, "played": jugat})
            if not ps:
                continue
            resultats = []
            for p in sorted(ps, key=lambda x: x["ordre"]):
                jo, ell = ("local", "visitant") if venue == "L" else ("visitant", "local")
                nom = p[f"jugador_{jo}"]
                pid = slug(nom)
                jugadors.setdefault(pid, {"id": pid, "name": bonic(nom), "_nom": nom, "_mods": set()})
                jugadors[pid]["_mods"].add(p["modalitat"])
                resultats.append({"pid": pid, "car": p[f"caramboles_{jo}"], "ent": p["entrades"],
                                  "sm": p[f"serie_major_{jo}"], "res": resultat(p[f"punts_{jo}"], p[f"punts_{ell}"]),
                                  "mod": p["modalitat"], "rival": bonic(p[f"jugador_{ell}"]),
                                  "car_rival": p[f"caramboles_{ell}"]})
            mpl = e["punts_match_local"] if venue == "L" else e["punts_match_visitant"]
            mpr = e["punts_match_visitant"] if venue == "L" else e["punts_match_local"]
            matches.append({"id": "j" + str(e["jornada"]).zfill(2), "jornada": e["jornada"], "date": e["data"],
                            "rival": rival, "venue": venue, "punts_match": [mpl, mpr], "results": resultats})
        for j in jugadors.values():
            mods = sorted(j.pop("_mods"))
            nom = j.pop("_nom")
            j["initials"] = {m: mitjana_inicial(rankings_idx, nom, m, inici) for m in mods if m in MODALITATS_RANKING.values()}
            princ = lliga.get("modalitat") if lliga.get("modalitat") in j["initials"] else (mods[0] if mods else "")
            j["initial"] = j["initials"].get(princ, "")
        dades = {
            "equip": f'C.B. Monforte "{lletra}"' if lletra != "unic" else "C.B. Monforte",
            "equip_original": nom_equip,
            "competicio": " · ".join(x for x in (lliga.get("nom", ""), re.sub(r"(\d)[AªaÀ]\b", r"\1a", e0["divisio"].title()), e0["grup"].title()) if x),
            "modalitat": lliga.get("modalitat", ""),
            "temporada": lliga.get("temporada", ""),
            "updated": ara,
            "players": sorted(jugadors.values(), key=lambda p: p["name"]),
            "matches": matches,
            "calendar": calendari,
        }
        carpeta = MONFORTE / "lligues" / slug(lliga.get("nom", f"lliga-{l}"))
        cami = carpeta / f"{lletra}.json"
        if cami in usats:
            cami = carpeta / f"{lletra}-{slug(e0['grup']) or g}.json"
        usats.add(cami)
        escriu_json(cami, dades)
        index.append({"temporada": dades["temporada"], "competicio": dades["competicio"], "modalitat": dades["modalitat"],
                      "equip": nom_equip, "lletra": lletra, "fitxer": str(cami.relative_to(DADES))})
    return index


def modalitats_monforte(partides, clubs, rankings, rankings_idx, ara):
    """Per a cada modalitat: jugadors del Monforte, estadístiques i totes les seves partides."""
    per_mod = defaultdict(lambda: {"partides": [], "jugadors": {}})
    for p in partides:
        for jo, ell in (("local", "visitant"), ("visitant", "local")):
            nom = p[f"jugador_{jo}"]
            equip = p[f"equip_{jo}"]
            if equip:
                propi = es_monforte(equip)
            else:
                propi = "MONFORTE" in club_en(clubs, nom, p["temporada"])
            if not propi:
                continue
            pid = slug(nom)
            res = resultat(p[f"punts_{jo}"], p[f"punts_{ell}"])
            m = per_mod[p["modalitat"]]
            m["partides"].append({
                "data": p["data"], "temporada": p["temporada"], "tipus": p["font"], "competicio": p["competicio"],
                "divisio": p["divisio"], "fase": p["fase"], "jornada": p["jornada"], "pid": pid,
                "equip": equip, "rival": bonic(p[f"jugador_{ell}"]), "equip_rival": p[f"equip_{ell}"],
                "car": p[f"caramboles_{jo}"], "sm": p[f"serie_major_{jo}"], "ent": p["entrades"],
                "car_rival": p[f"caramboles_{ell}"], "sm_rival": p[f"serie_major_{ell}"], "res": res})
            j = m["jugadors"].setdefault(pid, {"id": pid, "name": bonic(nom), "_nom": nom, "partides": 0, "G": 0, "E": 0, "P": 0,
                                               "caramboles": 0, "entrades": 0, "serie_major": 0, "temporades": set()})
            j["partides"] += 1
            if res:
                j[res] += 1
            j["caramboles"] += p[f"caramboles_{jo}"] or 0
            j["entrades"] += p["entrades"] or 0
            j["serie_major"] = max(j["serie_major"], p[f"serie_major_{jo}"] or 0)
            if p["temporada"]:
                j["temporades"].add(p["temporada"])

    darrer_rk = {}
    for r in rankings:
        darrer_rk[r["modalitat"]] = max(darrer_rk.get(r["modalitat"], ""), r["data"])

    index = []
    for mod, m in sorted(per_mod.items()):
        for j in m["jugadors"].values():
            nom = j.pop("_nom")
            j["mitjana"] = round(j["caramboles"] / j["entrades"], 3) if j["entrades"] else None
            j["temporades"] = sorted(j["temporades"])
            rk = [r for r in rankings_idx.get((slug(nom), mod), []) if r["data"] == darrer_rk.get(mod)]
            j["ranking"] = {"posicio": rk[0]["posicio"], "mitjana": rk[0]["mitjana"], "data": rk[0]["data"]} if rk else None
        m["partides"].sort(key=lambda x: (x["data"], x["competicio"]), reverse=True)
        dades = {"modalitat": mod, "updated": ara,
                 "jugadors": sorted(m["jugadors"].values(), key=lambda x: (-x["partides"], x["name"])),
                 "partides": m["partides"]}
        cami = MONFORTE / "modalitats" / f"{slug(mod)}.json"
        escriu_json(cami, dades)
        index.append({"modalitat": mod, "jugadors": len(dades["jugadors"]), "partides": len(dades["partides"]),
                      "fitxer": str(cami.relative_to(DADES))})
    return index


# ---------------------------------------------------------------- principal

def main():
    ara = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes")
    pagines = carrega()
    print(f"{len(pagines)} pàgines en brut carregades")

    lligues, grups, encontres, part_lliga, class_lliga, inscrits = processa_lligues(pagines)
    comps, part_ind, class_ind = processa_individuals(pagines)
    dedueix_modalitat(comps, part_ind)
    for c in class_ind:
        c["modalitat"] = comps.get(int(c["competicio_id"][1:]), {}).get("modalitat", c["modalitat"])
    rankings = processa_rankings(pagines)
    partides = part_lliga + part_ind
    partides.sort(key=lambda p: (p["data"], p["competicio_id"], str(p["encontre_id"]), p["ordre"]))

    clubs = clubs_per_temporada(part_lliga, class_ind, inscrits)
    rankings_idx = defaultdict(list)
    for r in rankings:
        rankings_idx[(slug(r["jugador"]), r["modalitat"])].append(r)

    print("Taules:")
    competicions = [{"competicio_id": f"L{l}", "tipus": "lliga", "nom": v["nom"], "modalitat": v["modalitat"],
                     "temporada": v["temporada"]} for l, v in sorted(lligues.items())]
    competicions += [{"competicio_id": f"I{c}", "tipus": "individual", "nom": v["nom"], "modalitat": v["modalitat"],
                      "temporada": v["temporada"], "modalitat_deduida": v.get("deduida", False)} for c, v in sorted(comps.items())]
    escriu_csv("competicions.csv", ["competicio_id", "tipus", "nom", "modalitat", "modalitat_deduida", "temporada"], competicions)

    camps_partida = ["data", "temporada", "font", "competicio_id", "competicio", "divisio", "fase", "jornada",
                     "encontre_id", "ordre", "modalitat", "jugador_local", "equip_local", "serie_major_local",
                     "caramboles_local", "jugador_visitant", "equip_visitant", "serie_major_visitant",
                     "caramboles_visitant", "entrades", "punts_local", "punts_visitant", "estat"]
    escriu_csv("partides.csv", camps_partida, partides)
    escriu_csv("encontres.csv", ["encontre_id", "lliga_id", "competicio", "temporada", "divisio", "grup", "grup_id",
                                 "jornada", "data", "equip_local", "equip_visitant", "punts_parcials_local",
                                 "punts_parcials_visitant", "punts_match_local", "punts_match_visitant", "estat"],
               sorted(encontres, key=lambda e: (e["data"], e["lliga_id"], e["grup"])))
    escriu_csv("classificacions_lliga.csv", ["temporada", "lliga_id", "competicio", "divisio", "grup", "grup_id",
                                             "posicio", "equip", "punts_match", "punts_parcials", "jugats"],
               sorted(class_lliga, key=lambda c: (c["temporada"], c["lliga_id"], c["divisio"], c["grup"], c["posicio"] or 0)))
    escriu_csv("classificacions_individuals.csv", ["temporada", "competicio_id", "competicio", "modalitat", "divisio",
                                                   "posicio", "jugador", "club", "punts", "partides", "caramboles",
                                                   "entrades", "mitjana_general", "mitjana_particular"],
               sorted(class_ind, key=lambda c: (c["temporada"], c["competicio_id"], c["divisio"], c["posicio"] or 0)))
    escriu_csv("rankings.csv", ["data", "modalitat", "posicio", "jugador", "jugador_fcb_id", "mitjana", "caramboles",
                                "entrades", "partides", "partides_total", "definitiu"], rankings)

    # jugadors
    noms, fcb_id = {}, {}
    for p in partides:
        for costat in ("local", "visitant"):
            noms.setdefault(slug(p[f"jugador_{costat}"]), p[f"jugador_{costat}"])
    for r in rankings:
        noms.setdefault(slug(r["jugador"]), r["jugador"])
        if r["jugador_fcb_id"]:
            fcb_id[slug(r["jugador"])] = r["jugador_fcb_id"]
    jugadors = []
    for pid, nom in sorted(noms.items()):
        temps = clubs.get(pid, {})
        actual = temps[max(temps)] if temps else ""
        jugadors.append({"jugador_id": pid, "nom": nom, "nom_bonic": bonic(nom), "jugador_fcb_id": fcb_id.get(pid, ""),
                         "club_actual": actual, "temporada_club_actual": max(temps) if temps else "",
                         "monforte_actual": "MONFORTE" in actual,
                         "monforte_alguna_vegada": any("MONFORTE" in c for c in temps.values()),
                         "historial_clubs": "; ".join(f"{t}: {c}" for t, c in sorted(temps.items()))})
    escriu_csv("jugadors.csv", list(jugadors[0].keys()), jugadors)

    # fitxers de l'app
    if MONFORTE.exists():
        shutil.rmtree(MONFORTE)
    actual = max(v["temporada"] for v in lligues.values() if v["temporada"])
    print(f"Temporada actual: {actual}")
    idx_equips = equips_monforte(lligues, grups, [e for e in encontres if e["temporada"] == actual],
                                 [p for p in part_lliga if p["temporada"] == actual], rankings_idx, ara)
    idx_mods = modalitats_monforte([p for p in partides if p["temporada"] == actual], clubs, rankings, rankings_idx, ara)
    escriu_json(MONFORTE / "index.json", {
        "updated": ara,
        "temporada": actual,
        "equips": sorted(idx_equips, key=lambda x: (x["temporada"], x["competicio"], x["lletra"]), reverse=True),
        "modalitats": idx_mods,
        "jugadors_actuals": [j["nom_bonic"] for j in jugadors if j["monforte_actual"]],
    })
    print(f"Monforte: {len(idx_equips)} fitxers d'equip, {len(idx_mods)} modalitats, "
          f"{sum(j['monforte_actual'] for j in jugadors)} jugadors actuals")


if __name__ == "__main__":
    main()
