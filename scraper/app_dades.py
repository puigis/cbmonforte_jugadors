"""
Genera les dades que fa servir l'app (carpeta dades/app/):

  rankings.json            Per a cada modalitat, tres rànquings:
                             - inici: el rànquing del 27/07/2026, amb el que es va començar la temporada
                             - federatiu: el darrer rànquing publicat per la Federació
                             - personal: calculat aquí amb les partides que la Federació encara no ha comptat
  jugadors/<id>.json       Fitxa de cada jugador: rànquings, evolució, últimes 15 partides, partides
                           pendents de comptar i estadístiques històriques per temporada.
  equips.json              Els equips del Monforte de la temporada actual (format app Monforte C).

Com calcula la Federació la mitjana (comprovat amb les dades): caramboles totals / entrades totals
de les darreres 15 partides a tres bandes i 10 a la resta de modalitats. Un jugador és "definitiu"
quan té aquest nombre de partides; els no definitius van al final del rànquing. El rànquing personal fa el mateix càlcul afegint-hi les
partides jugades després del darrer rànquing.
"""

import csv
import datetime
import glob
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from organitza import MODALITATS_RANKING, bonic, club_clau, norm, slug  # noqa: E402

ARREL = Path(__file__).resolve().parent.parent
DADES = ARREL / "dades"
APP = DADES / "app"
DATA_INICI = "2026-07-27"
N_PARTIDES = {"Tres bandes": 15}   # la resta de modalitats: 10 partides (comprovat amb les dades)
N_ALTRES = 10


def llegeix_csv(nom):
    with open(DADES / nom, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def enter(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def r5(x):
    return round(x, 5) if x is not None else None


def temporada_actual(competicions):
    return max(c["temporada"] for c in competicions if c["tipus"] == "lliga" and c["temporada"])


# ---------------------------------------------------------------- partides comptades per la Federació

def partides_del_ranking(id_ranking):
    """{(modalitat, slug jugador): [partides]} de les fitxes 'Partides' d'un rànquing."""
    out = {}
    for f in glob.glob(str(DADES / "brut" / "rankings" / f"{id_ranking}.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for linia in fh:
                d = json.loads(linia)
                qs = parse_qs(urlparse(d["url"]).query)
                if "partides" not in d["url"] or "idjugador" not in qs:
                    continue
                mod = MODALITATS_RANKING.get(qs.get("idmodalitat", [""])[0])
                llista = []
                for t in d["taules"]:
                    for fila in t["files"]:
                        x = [c["text"] for c in fila]
                        if len(x) < 8 or not re.match(r"\d{4}-\d{2}-\d{2}", x[0]):
                            continue
                        llista.append({"d": x[0], "l": x[1], "pl": enter(x[2]), "cl": enter(x[3]),
                                       "v": x[4], "pv": enter(x[5]), "cv": enter(x[6]), "e": enter(x[7])})
                out[(mod, qs["idjugador"][0])] = llista
    return out


def id_ranking_de(data):
    """Busca l'idranking d'una data a les pàgines de llistat."""
    for f in glob.glob(str(DADES / "brut" / "rankings" / "*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for linia in fh:
                d = json.loads(linia)
                if "-dades?" in d["url"] and data in " ".join(d["titols"]):
                    return parse_qs(urlparse(d["url"]).query)["idranking"][0]
    return None


# ---------------------------------------------------------------- principal

def main():
    ara = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes")
    competicions = llegeix_csv("competicions.csv")
    actual = temporada_actual(competicions)
    anterior = f"{int(actual[:4]) - 1}-{actual[2:4]}"
    rankings = llegeix_csv("rankings.csv")
    partides = llegeix_csv("partides.csv")
    jugadors_csv = {j["jugador_id"]: j for j in llegeix_csv("jugadors.csv")}
    # classificacions finals de competicions individuals (opens i campionats), per jugador i modalitat
    classif = llegeix_csv("classificacions_individuals.csv")
    participants = defaultdict(int)
    for c in classif:
        participants[(c["competicio_id"], c["divisio"])] += 1
    classif_de = defaultdict(lambda: defaultdict(list))
    for c in classif:
        pos = enter(c["posicio"])
        if pos is None:
            continue
        classif_de[slug(c["jugador"])][c["modalitat"]].append({
            "t": c["temporada"], "comp": c["competicio"], "div": c["divisio"], "pos": pos,
            "de": participants[(c["competicio_id"], c["divisio"])], "pts": enter(c["punts"]),
            "open": "OPEN" in c["competicio"].upper(), "mg": num(c["mitjana_general"])})


    # clubs d'aquesta temporada: inscripcions i equips en què han jugat
    club_actual = {}
    for p in partides:
        if p["temporada"] in (anterior, actual) and p["font"] == "lliga":
            for c in ("local", "visitant"):
                club_actual[slug(p[f"jugador_{c}"])] = (p["temporada"], club_clau(p[f"equip_{c}"]))
    for pid, j in jugadors_csv.items():
        if j["temporada_club_actual"] in (anterior, actual) and j["club_actual"]:
            prev = club_actual.get(pid)
            if not prev or prev[0] <= j["temporada_club_actual"]:
                club_actual[pid] = (j["temporada_club_actual"], j["club_actual"])
    club = {pid: c for pid, (_, c) in club_actual.items()}
    es_mon = lambda pid: "MONFORTE" in club.get(pid, "")

    # equips de la temporada actual
    equips = []
    for f in sorted((DADES / "monforte" / "lligues").glob("*/*.json")):
        equips.append(json.loads(f.read_text(encoding="utf-8")))
    # classificació del grup de cada equip
    classif_lliga = defaultdict(list)
    for c in llegeix_csv("classificacions_lliga.csv"):
        if c["temporada"] == actual:
            classif_lliga[(c["lliga_id"], c["grup_id"])].append({
                "pos": enter(c["posicio"]), "equip": c["equip"], "pm": enter(c["punts_match"]),
                "pp": enter(c["punts_parcials"]), "j": enter(c["jugats"]), "mon": "MONFORTE" in norm(c["equip"])})
    for e in equips:
        e["classificacio"] = sorted(classif_lliga.get((str(e.get("lliga_id")), str(e.get("grup_id"))), []),
                                    key=lambda x: x["pos"] or 99)
    equip_de = defaultdict(list)
    for e in equips:
        lletra = e["equip"].split('"')[1] if '"' in e["equip"] else ""
        for p in e["players"]:
            equip_de[p["id"]].append(lletra)
        for c in e.get("calendar", []):
            pass

    # partides per jugador i modalitat (totes les temporades)
    per_jug = defaultdict(lambda: defaultdict(list))
    for p in partides:
        ent = enter(p["entrades"])
        if not ent:
            continue
        for jo, ell in (("local", "visitant"), ("visitant", "local")):
            pid = slug(p[f"jugador_{jo}"])
            pj, pe = enter(p[f"punts_{jo}"]), enter(p[f"punts_{ell}"])
            res = "" if pj is None or pe is None else ("G" if pj > pe else "P" if pj < pe else "E")
            per_jug[pid][p["modalitat"]].append({
                "d": p["data"], "t": p["temporada"], "comp": p["competicio"], "fase": p["fase"] or p["divisio"],
                "j": p["jornada"], "eq": p[f"equip_{jo}"], "riv": bonic(p[f"jugador_{ell}"]), "eqr": p[f"equip_{ell}"],
                "car": enter(p[f"caramboles_{jo}"]), "ent": ent, "sm": enter(p[f"serie_major_{jo}"]),
                "rc": enter(p[f"caramboles_{ell}"]), "rsm": enter(p[f"serie_major_{ell}"]), "res": res,
                "_ril": slug(p[f"jugador_{ell}"]), "rid": slug(p[f"jugador_{ell}"])})
    for mods in per_jug.values():
        for llista in mods.values():
            llista.sort(key=lambda g: (g["d"], g["comp"]))

    # rànquings: inici i federatiu (darrer)
    dates = sorted({r["data"] for r in rankings})
    data_fed = dates[-1]
    rk = defaultdict(dict)    # (data, mod) -> {pid: fila}
    for r in rankings:
        if r["data"] in (DATA_INICI, data_fed):
            rk[(r["data"], r["modalitat"])][slug(r["jugador"])] = r
    evolucio = defaultdict(list)
    for r in rankings:
        if r["data"]:
            evolucio[(slug(r["jugador"]), r["modalitat"])].append([r["data"], num(r["mitjana"]), enter(r["posicio"])])

    id_fed = id_ranking_de(data_fed)
    comptades = partides_del_ranking(id_fed) if id_fed else {}
    id_ini = id_ranking_de(DATA_INICI)
    comptades_inici = partides_del_ranking(id_ini) if id_ini else {}
    print(f"Rànquing inicial {DATA_INICI} · federatiu {data_fed} (id {id_fed}) · temporada {actual}")

    sortida_rk = {"updated": ara, "temporada": actual, "data_inici": DATA_INICI, "data_federatiu": data_fed,
                  "n_partides": {m: N_PARTIDES.get(m, N_ALTRES) for m in MODALITATS_RANKING.values()}, "modalitats": {}}
    fitxes = defaultdict(lambda: {"modalitats": {}})

    for mod in MODALITATS_RANKING.values():
        inici, fed = rk.get((DATA_INICI, mod), {}), rk.get((data_fed, mod), {})
        if not fed and not inici:
            continue
        N = N_PARTIDES.get(mod, N_ALTRES)
        jugadors = set(fed) | set(inici) | {pid for pid in per_jug if es_mon(pid) and per_jug[pid].get(mod)}
        personal = {}
        for pid in jugadors:
            f = fed.get(pid)
            base_rk = f or inici.get(pid)          # si no surt al darrer rànquing, parteix del d'inici
            fcb = base_rk["jugador_fcb_id"] if base_rk else ""
            nom_fed = base_rk["jugador"] if base_rk else ""
            font = comptades if f else comptades_inici
            llista_fed = font.get((mod, fcb), []) if fcb else []
            # partides que la Federació ja ha comptat (amb el detall de la nostra base de dades quan hi és)
            meves = per_jug.get(pid, {}).get(mod, [])
            index_meves = {}
            for g in meves:
                index_meves.setdefault((g["d"], g["_ril"], g["car"], g["ent"]), g)
            comptats = []
            for x in llista_fed:
                soc_local = slug(x["l"]) == pid or norm(x["l"]) == norm(nom_fed)
                car, pr, rc, riv = (x["cl"], x["pl"], x["cv"], x["v"]) if soc_local else (x["cv"], x["pv"], x["cl"], x["l"])
                pr_r = x["pv"] if soc_local else x["pl"]
                g = index_meves.get((x["d"], slug(riv), car, x["e"]))
                base = dict(g) if g else {"d": x["d"], "riv": bonic(riv), "car": car, "ent": x["e"], "rc": rc,
                                          "res": "G" if pr > pr_r else "P" if pr < pr_r else "E", "comp": "", "fase": ""}
                base["pts"] = pr
                comptats.append(base)
            # partides jugades després i que encara no compten
            data_base = data_fed if f else DATA_INICI
            darrera = max((g["d"] for g in comptats), default="") if comptats else (data_base if base_rk else "")
            claus = {(g["d"], slug(g["riv"]), g["car"], g["ent"]) for g in comptats}
            pendents = [dict(g, pendent=True) for g in meves
                        if g["d"] and g["d"] >= darrera and (g["d"], g["_ril"], g["car"], g["ent"]) not in claus
                        and (comptats or g["d"] > data_base)]
            if not comptats and not base_rk:
                comptats_rel = [dict(g) for g in meves[-N:]]
                pendents = []
            else:
                comptats_rel = comptats
            totes = sorted(comptats_rel + pendents, key=lambda g: g["d"])
            ultimes = totes[-N:]
            c = sum(g["car"] or 0 for g in ultimes)
            e = sum(g["ent"] or 0 for g in ultimes)
            personal[pid] = {"mj": c / e if e else None, "c": c, "e": e, "n": len(ultimes),
                             "pend": len(pendents), "ultimes": ultimes, "pendents": pendents}

        # posicions del rànquing personal (ordre per mitjana, com fa la Federació)
        ordre = sorted((p for p in personal if personal[p]["mj"] is not None),
                       key=lambda p: (personal[p]["n"] < N, -personal[p]["mj"]))
        pos_personal = {p: i + 1 for i, p in enumerate(ordre)}

        def nom_de(pid):
            for font in (fed, inici):
                if pid in font:
                    return bonic(font[pid]["jugador"])
            return bonic(jugadors_csv.get(pid, {}).get("nom", pid))

        def fila(pid, r=None, extra=None):
            d = {"id": pid, "nom": nom_de(pid), "club": bonic(club.get(pid, "")), "mon": es_mon(pid)}
            if r:
                d.update({"pos": enter(r["posicio"]), "mj": num(r["mitjana"]), "c": enter(r["caramboles"]),
                          "e": enter(r["entrades"]), "p": enter(r["partides"]), "pt": enter(r["partides_total"]),
                          "def": r["definitiu"]})
            if extra:
                d.update(extra)
            return d

        bloc = {
            "inici": sorted([fila(p, r) for p, r in inici.items()], key=lambda x: x["pos"] or 9999),
            "federatiu": sorted([fila(p, r) for p, r in fed.items()], key=lambda x: x["pos"] or 9999),
            "personal": [fila(p, None, {"pos": pos_personal[p], "mj": r5(personal[p]["mj"]), "c": personal[p]["c"],
                                        "e": personal[p]["e"], "n": personal[p]["n"], "pend": personal[p]["pend"],
                                        "def": "Si" if personal[p]["n"] >= N else "No"})
                         for p in ordre],
        }
        sortida_rk["modalitats"][mod] = bloc

        # fitxes de jugador (per a tots els que surten als rànquings)
        for pid in jugadors:
            meves = per_jug.get(pid, {}).get(mod, [])
            per_temp = defaultdict(lambda: {"pj": 0, "G": 0, "E": 0, "P": 0, "car": 0, "ent": 0, "sm": 0})
            for g in meves:
                s = per_temp[g["t"] or "?"]
                s["pj"] += 1
                if g["res"]:
                    s[g["res"]] += 1
                s["car"] += g["car"] or 0
                s["ent"] += g["ent"] or 0
                s["sm"] = max(s["sm"], g["sm"] or 0)
            temporades = [dict(t=t, mj=r5(s["car"] / s["ent"]) if s["ent"] else None, **s)
                          for t, s in sorted(per_temp.items(), reverse=True)]
            pr = personal.get(pid, {})
            neteja = lambda gs: [{k: v for k, v in g.items() if not k.startswith("_")} for g in gs]
            fitxes[pid]["modalitats"][mod] = {
                "inici": fila(pid, inici.get(pid)) if pid in inici else None,
                "federatiu": fila(pid, fed.get(pid)) if pid in fed else None,
                "personal": {"pos": pos_personal.get(pid), "mj": r5(pr.get("mj")), "c": pr.get("c"), "e": pr.get("e"),
                             "n": pr.get("n")} if pr else None,
                "evolucio": evolucio.get((pid, mod), []),
                "ultimes": neteja(list(reversed(pr.get("ultimes", [])))),
                "pendents": neteja(list(reversed(pr.get("pendents", [])))),
                "temporades": temporades,
                "partides": neteja(list(reversed(meves))),
                "classificacions": sorted(classif_de.get(pid, {}).get(mod, []), key=lambda c: (c["t"], c["comp"]), reverse=True),
            }
            fitxes[pid]["nom"] = nom_de(pid)

    if APP.exists():
        shutil.rmtree(APP)
    (APP / "jugadors").mkdir(parents=True)
    with open(APP / "rankings.json", "w", encoding="utf-8") as f:
        json.dump(sortida_rk, f, ensure_ascii=False, separators=(",", ":"))
    for pid, fx in fitxes.items():
        fx.update({"id": pid, "club": bonic(club.get(pid, "")), "mon": es_mon(pid),
                   "equips": sorted(set(equip_de.get(pid, []))), "updated": ara})
        with open(APP / "jugadors" / f"{pid}.json", "w", encoding="utf-8") as f:
            json.dump(fx, f, ensure_ascii=False, separators=(",", ":"))
    with open(APP / "equips.json", "w", encoding="utf-8") as f:
        json.dump({"updated": ara, "temporada": actual, "equips": equips}, f, ensure_ascii=False, separators=(",", ":"))
    mon = sum(1 for p in fitxes if es_mon(p))
    print(f"App: {len(fitxes)} fitxes de jugador ({mon} del Monforte), {len(equips)} equips, "
          f"{len(sortida_rk['modalitats'])} modalitats de rànquing")


if __name__ == "__main__":
    main()
