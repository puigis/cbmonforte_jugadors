"""
Genera la imatge de resultats de lliga del cap de setmana, amb tots els equips del Monforte,
a partir de dades/app/equips.json. Es desa a imatges/resultats-AAAA-MM-DD.png (1080 px d'amplada,
format vertical d'Instagram 4:5).

Quins partits hi surten: els de la setmana que acaba el dia de referència (per defecte avui).
Opcions (variables d'entorn):
  DATA=2026-09-27   Dia de referència (per refer la imatge d'un cap de setmana passat).
  DIES=7            Quants dies enrere es miren.
"""

import datetime
import html
import json
import os
import re
import sys
from pathlib import Path

ARREL = Path(__file__).resolve().parent.parent
EQUIPS = ARREL / "dades" / "app" / "equips.json"
SORTIDA = ARREL / "imatges"


def esc(t):
    return html.escape(str(t if t is not None else ""))


def nom_curt(nom):
    """'García Alarcón, Ricardo' -> 'R. García Alarcón'"""
    if "," in nom:
        cognoms, noms = [x.strip() for x in nom.split(",", 1)]
        return f"{noms[:1]}. {cognoms}" if noms else cognoms
    return nom


def rival_bonic(nom):
    n = re.sub(r"\s+", " ", nom).strip()
    n = n.replace("“", '"').replace("”", '"')
    return n.title()


def data_llarga(d):
    mesos = ["gener", "febrer", "març", "abril", "maig", "juny", "juliol", "agost", "setembre", "octubre", "novembre", "desembre"]
    dt = datetime.date.fromisoformat(d)
    de = "d'" if mesos[dt.month - 1][0] in "aeiou" else "de "
    return f"{dt.day} {de}{mesos[dt.month - 1]} de {dt.year}"


def partits_de_la_setmana(equips, ref, dies):
    inici = (ref - datetime.timedelta(days=dies - 1)).isoformat()
    fi = ref.isoformat()
    # una jornada avançada pot tenir data posterior; s'inclou si ja té resultats
    out = []
    for e in equips:
        lletra = e["equip"].split('"')[1] if '"' in e["equip"] else ""
        divisio = e["competicio"].split(" · ", 1)[1] if " · " in e["competicio"] else e["competicio"]
        jugats = [m for m in e["matches"] if m.get("results") and inici <= (m.get("date") or "") <= fi]
        avancats = [m for m in e["matches"] if m.get("results") and (m.get("date") or "") > fi
                    and ref == datetime.date.today()
                    and not any(x["jornada"] == m["jornada"] for x in jugats)]
        noms = {p["id"]: p["name"] for p in e["players"]}
        for m in jugats + avancats:
            out.append({"lletra": lletra, "divisio": divisio, "competicio": e["competicio"], "m": m, "noms": noms})
    return out


def bloc(p):
    m = p["m"]
    pm = m.get("punts_match") or [None, None]
    mon, riv = pm[0], pm[1]
    estat = "gu" if (mon or 0) > (riv or 0) else "pe" if (mon or 0) < (riv or 0) else "em"
    etiqueta = {"gu": "VICTÒRIA", "pe": "DERROTA", "em": "EMPAT"}[estat]
    casa = m.get("venue") == "L"
    local, visitant = (f"MONFORTE {p['lletra']}", rival_bonic(m["rival"])) if casa else (rival_bonic(m["rival"]), f"MONFORTE {p['lletra']}")
    gl, gv = (mon, riv) if casa else (riv, mon)
    files = []
    for r in m["results"]:
        prom = r["car"] / r["ent"] if r.get("ent") else None
        files.append(f"""<div class="fila"><span class="res r{esc(r.get('res'))}">{esc(r.get('res') or '·')}</span>
          <span class="jug">{esc(nom_curt(p['noms'].get(r['pid'], r['pid'])))}</span>
          <span class="num">{esc(r.get('car'))}<i>/</i>{esc(r.get('ent'))}</span>
          <span class="prom">{f'{prom:.3f}' if prom is not None else '—'}</span>
          <span class="riv">vs {esc(nom_curt(r.get('rival', '')))} <b>{esc(r.get('car_rival', ''))}</b></span></div>""")
    return f"""<section class="eq {estat}">
      <div class="cap"><div class="lletra">{esc(p['lletra'])}</div>
        <div class="info"><div class="div">{esc(p['divisio'])} · Jornada {esc(m['jornada'])}</div>
          <div class="marc"><span class="{'mon' if casa else ''}">{esc(local)}</span><b>{esc(gl)}</b><em>–</em><b>{esc(gv)}</b><span class="{'' if casa else 'mon'}">{esc(visitant)}</span></div></div>
        <div class="et">{etiqueta}</div></div>
      <div class="files">{''.join(files)}</div></section>"""


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;min-height:1350px;background:#0f2a1c;font-family:Inter,'DejaVu Sans',sans-serif;color:#f3f1ea}
.pg{min-height:1350px;padding:44px 56px 30px;display:flex;flex-direction:column;
  background:radial-gradient(1200px 700px at 85% -10%,#1f6b3a 0%,rgba(31,107,58,0) 60%),linear-gradient(180deg,#123824,#0c2116)}
header{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid rgba(243,241,234,.18);padding-bottom:18px;margin-bottom:18px}
.club{font-family:'Inter Display',Inter,sans-serif;font-weight:800;font-size:58px;letter-spacing:-1px;line-height:1}
.club small{display:block;font-size:22px;font-weight:600;letter-spacing:5px;color:#9fd8b4;margin-bottom:10px}
.data{text-align:right;font-size:22px;color:#cfe6d6;line-height:1.35}
.data b{display:block;font-size:30px;color:#fff;font-weight:700}
main{flex:1;display:flex;flex-direction:column;gap:12px}
.eq{background:rgba(255,255,255,.06);border-radius:20px;padding:13px 22px 11px;border-left:10px solid #8a948d}
.eq.gu{border-left-color:#34c26e}.eq.pe{border-left-color:#e2574c}.eq.em{border-left-color:#d6b24a}
.cap{display:flex;align-items:center;gap:20px}
.lletra{width:56px;height:56px;border-radius:14px;background:#f3f1ea;color:#123824;font-weight:800;font-size:34px;display:flex;align-items:center;justify-content:center;flex:none}
.info{flex:1;min-width:0}
.div{font-size:16px;color:#9fd8b4;font-weight:600;letter-spacing:.5px;text-transform:uppercase}
.marc{display:flex;align-items:center;gap:12px;margin-top:2px;font-size:23px;font-weight:600;white-space:nowrap}
.marc span{overflow:hidden;text-overflow:ellipsis;max-width:330px;color:#d9dfd9}
.marc span.mon{color:#fff;font-weight:800}
.marc b{font-family:'Inter Display',Inter,sans-serif;font-size:34px;font-weight:800;color:#fff}
.marc em{font-style:normal;color:#8fa596;font-size:30px}
.et{font-size:17px;font-weight:800;letter-spacing:2px;padding:8px 14px;border-radius:30px;flex:none;background:#3a4a40}
.gu .et{background:#34c26e;color:#0c2116}.pe .et{background:#e2574c;color:#fff}.em .et{background:#d6b24a;color:#1d1a0c}
.files{margin-top:8px;display:grid;gap:3px}
.fila{display:grid;grid-template-columns:34px 1fr 98px 92px 300px;align-items:center;gap:12px;font-size:19px}
.res{width:26px;height:26px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;background:#3a4a40;color:#cfd8d1}
.rG{background:#34c26e;color:#0c2116}.rP{background:#e2574c;color:#fff}.rE{background:#d6b24a;color:#1d1a0c}
.jug{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.num{font-variant-numeric:tabular-nums;text-align:right;color:#e6ebe6}.num i{font-style:normal;color:#7f9688;margin:0 2px}
.prom{font-variant-numeric:tabular-nums;font-weight:800;text-align:right}
.riv{color:#a9b9ae;font-size:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.riv b{color:#d9dfd9}
.buit{font-size:28px;color:#cfe6d6;text-align:center;margin-top:200px}
footer{margin-top:16px;display:flex;justify-content:space-between;font-size:17px;color:#8fb39b}
"""


def genera(ref, dies):
    dades = json.loads(EQUIPS.read_text(encoding="utf-8"))
    partits = partits_de_la_setmana(dades["equips"], ref, dies)
    partits.sort(key=lambda p: p["lletra"])
    dates = sorted(p["m"]["date"] for p in partits if p["m"].get("date") and p["m"]["date"] <= ref.isoformat())
    dia = max(set(dates), key=dates.count) if dates else ref.isoformat()
    competicions = sorted({p["competicio"].split(" · ")[0] for p in partits}) or ["Lliga Catalana"]
    cos = "".join(bloc(p) for p in partits) or '<p class="buit">Aquest cap de setmana no hi ha hagut partits de lliga.</p>'
    pagina = f"""<!doctype html><html lang="ca"><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="pg">
      <header><div class="club"><small>RESULTATS DE LLIGA</small>CB Monforte</div>
        <div class="data"><b>{esc(data_llarga(dia))}</b>{esc(' · '.join(competicions))}</div></header>
      <main>{cos}</main>
      <footer><span>Temporada {esc(dades.get('temporada', ''))}</span><span>Dades: Federació Catalana de Billar</span></footer>
    </div></body></html>"""
    return pagina, len(partits)


def main():
    ref = datetime.date.fromisoformat(os.environ["DATA"]) if os.environ.get("DATA") else datetime.date.today()
    dies = int(os.environ.get("DIES", "7"))
    pagina, n = genera(ref, dies)
    SORTIDA.mkdir(exist_ok=True)
    html_path = SORTIDA / f"resultats-{ref.isoformat()}.html"
    png_path = SORTIDA / f"resultats-{ref.isoformat()}.png"
    html_path.write_text(pagina, encoding="utf-8")
    if n == 0 and os.environ.get("NOMES_SI_HI_HA", "1") == "1":
        html_path.unlink()
        print("No hi ha partits aquesta setmana: no es genera imatge.")
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(viewport={"width": 1080, "height": 1350})
        pg.goto(html_path.as_uri())
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(png_path), full_page=True)
        nav.close()
    html_path.unlink()
    print(f"Imatge creada: {png_path.relative_to(ARREL)} ({n} partits)")


if __name__ == "__main__":
    sys.exit(main())
