"""
Genera el cartell de resultats de lliga del cap de setmana a partir de dades/app/equips.json:

  imatges/resultats-AAAA-MM-DD-1.png   Diapositiva 1: resultat final (punts de match) de cada equip
  imatges/resultats-AAAA-MM-DD-2.png   Diapositiva 2: classificació del grup de cada equip
  imatges/resultats-AAAA-MM-DD.mp4     Vídeo amb transició entre les dues diapositives

Mida 1080 x 1350 (format vertical d'Instagram). Les dues imatges serveixen com a carrusel.
El logo del club es llegeix de imatges/logo.png (o .svg / .jpg) si existeix.

Opcions (variables d'entorn):
  DATA=2026-09-27   Dia de referència (per defecte avui).
  DIES=7            Quants dies enrere es miren.
"""

import base64
import datetime
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ARREL = Path(__file__).resolve().parent.parent
EQUIPS = ARREL / "dades" / "app" / "equips.json"
SORTIDA = ARREL / "imatges"


def esc(t):
    return html.escape(str(t if t is not None else ""))


def bonic(nom):
    n = re.sub(r"\s+", " ", nom or "").strip().replace("“", '"').replace("”", '"')
    return n.title()


def data_llarga(d):
    mesos = ["gener", "febrer", "març", "abril", "maig", "juny", "juliol", "agost", "setembre", "octubre", "novembre", "desembre"]
    dt = datetime.date.fromisoformat(d)
    de = "d'" if mesos[dt.month - 1][0] in "aeiou" else "de "
    return f"{dt.day} {de}{mesos[dt.month - 1]} de {dt.year}"


def logo_html():
    for nom in ("logo.png", "logo.svg", "logo.jpg", "logo.jpeg", "logo.webp"):
        f = SORTIDA / nom
        if f.exists():
            mime = mimetypes.guess_type(f.name)[0] or "image/png"
            b64 = base64.b64encode(f.read_bytes()).decode()
            return f'<img class="logo" src="data:{mime};base64,{b64}" alt="CB Monforte">'
    return '<div class="logo mono">CB<br>M</div>'   # provisional fins que hi hagi el logo


def partits_de_la_setmana(equips, ref, dies):
    inici = (ref - datetime.timedelta(days=dies - 1)).isoformat()
    fi = ref.isoformat()
    avui = ref == datetime.date.today()
    out = []
    for e in equips:
        lletra = e["equip"].split('"')[1] if '"' in e["equip"] else ""
        divisio = e["competicio"].split(" · ", 1)[1] if " · " in e["competicio"] else e["competicio"]
        jugats = [m for m in e["matches"] if m.get("results") and inici <= (m.get("date") or "") <= fi]
        # una jornada avançada té data posterior però ja té resultats
        avancats = [m for m in e["matches"] if avui and m.get("results") and (m.get("date") or "") > fi
                    and not any(x["jornada"] == m["jornada"] for x in jugats)]
        for m in jugats + avancats:
            out.append({"lletra": lletra, "divisio": divisio, "competicio": e["competicio"], "m": m})
    out.sort(key=lambda p: p["lletra"])
    return out


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;overflow:hidden;font-family:Inter,'DejaVu Sans',sans-serif;color:#f3f1ea;background:#0c2116}
.pg{height:1350px;padding:46px 56px 34px;display:flex;flex-direction:column;
  background:radial-gradient(1100px 650px at 90% -10%,#1f6b3a 0%,rgba(31,107,58,0) 62%),linear-gradient(180deg,#123824,#0b1f14)}
header{display:flex;align-items:center;gap:26px;padding-bottom:22px;margin-bottom:26px;border-bottom:2px solid rgba(243,241,234,.18)}
.logo{width:118px;height:118px;object-fit:contain;flex:none}
.logo.mono{border-radius:50%;border:4px solid #f3f1ea;display:flex;align-items:center;justify-content:center;text-align:center;
  font-weight:800;font-size:34px;line-height:1;letter-spacing:1px;background:#1f6b3a}
.tit{flex:1}
.tit small{display:block;font-size:21px;font-weight:700;letter-spacing:5px;color:#9fd8b4;margin-bottom:6px}
.tit h1{font-family:'Inter Display',Inter,sans-serif;font-weight:800;font-size:60px;line-height:1;letter-spacing:-1px}
.tit p{margin-top:10px;font-size:23px;color:#cfe6d6}
main{flex:1;display:flex;flex-direction:column;gap:18px}
footer{margin-top:18px;display:flex;justify-content:space-between;font-size:18px;color:#8fb39b}
.eq{flex:1;display:flex;align-items:center;gap:20px;background:rgba(255,255,255,.06);border-radius:24px;padding:0 28px;border-left:12px solid #8a948d;max-height:200px}
.eq.gu{border-left-color:#34c26e}.eq.pe{border-left-color:#e2574c}.eq.em{border-left-color:#d6b24a}
.lletra{width:76px;height:76px;border-radius:18px;background:#f3f1ea;color:#123824;font-weight:800;font-size:46px;display:flex;align-items:center;justify-content:center;flex:none}
.info{flex:1;min-width:0}
.div{font-size:18px;color:#9fd8b4;font-weight:700;letter-spacing:1px;text-transform:uppercase}
.marc{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:14px;margin-top:10px}
.marc .nom{font-size:24px;font-weight:600;color:#d9dfd9;line-height:1.15;white-space:nowrap}
.marc .nom.mon{color:#fff;font-weight:800}
.marc .nom.dr{text-align:right}
.score{font-family:'Inter Display',Inter,sans-serif;font-weight:800;font-size:60px;color:#fff;white-space:nowrap;font-variant-numeric:tabular-nums}
.score em{font-style:normal;color:#7f9688;margin:0 10px;font-weight:600}
.et{font-size:16px;font-weight:800;letter-spacing:2px;padding:9px 0;border-radius:30px;flex:none;background:#3a4a40;width:124px;text-align:center}
.gu .et{background:#34c26e;color:#0c2116}.pe .et{background:#e2574c;color:#fff}.em .et{background:#d6b24a;color:#1d1a0c}
.buit{font-size:30px;color:#cfe6d6;text-align:center;margin-top:260px}
.cls{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-content:start}
.grp{background:rgba(255,255,255,.06);border-radius:20px;padding:16px 18px 12px}
.grp h3{display:flex;align-items:center;gap:12px;font-size:17px;color:#9fd8b4;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}
.grp h3 b{width:38px;height:38px;border-radius:10px;background:#f3f1ea;color:#123824;font-size:22px;display:flex;align-items:center;justify-content:center;flex:none}
.grp table{width:100%;border-collapse:collapse;font-size:18px;font-variant-numeric:tabular-nums;table-layout:fixed}
.grp td{padding:4px;border-top:1px solid rgba(243,241,234,.08)}
.grp td.p{width:34px;color:#8fa596;text-align:right;padding-right:10px}
.grp td.n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.grp td.v{text-align:right;width:48px;font-weight:700}
.grp td.j{text-align:right;width:34px;color:#8fa596}
.grp tr.mon td{background:rgba(52,194,110,.2);font-weight:800;color:#fff}
.grp tr.cap td{border:0;color:#8fa596;font-size:13px;font-weight:700;letter-spacing:1px;background:none}
"""


def pagina(cos, subtitol, temporada, logo, titol):
    return f"""<!doctype html><html lang="ca"><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="pg">
      <header>{logo}<div class="tit"><small>CB MONFORTE</small><h1>{esc(titol)}</h1><p>{esc(subtitol)}</p></div></header>
      <main>{cos}</main>
      <footer><span>Temporada {esc(temporada)}</span><span>Dades: Federació Catalana de Billar</span></footer>
    </div></body></html>"""


def diapo_resultats(partits):
    etiquetes = {"gu": "VICTÒRIA", "pe": "DERROTA", "em": "EMPAT"}
    blocs = []
    for p in partits:
        m = p["m"]
        mon, riv = (m.get("punts_match") or [None, None])
        estat = "gu" if (mon or 0) > (riv or 0) else "pe" if (mon or 0) < (riv or 0) else "em"
        casa = m.get("venue") == "L"
        nom_mon, nom_riv = f"Monforte {p['lletra']}", bonic(m["rival"])
        l, v = (nom_mon, nom_riv) if casa else (nom_riv, nom_mon)
        gl, gv = (mon, riv) if casa else (riv, mon)
        blocs.append(f"""<section class="eq {estat}"><div class="lletra">{esc(p['lletra'])}</div>
          <div class="info"><div class="div">{esc(p['divisio'])} · Jornada {esc(m['jornada'])}</div>
            <div class="marc"><div class="nom {'mon' if casa else ''}">{esc(l)}</div>
              <div class="score">{esc(gl)}<em>–</em>{esc(gv)}</div>
              <div class="nom dr {'' if casa else 'mon'}">{esc(v)}</div></div></div>
          <div class="et">{etiquetes[estat]}</div></section>""")
    return "".join(blocs)


def diapo_classificacions(equips):
    grups = []
    for e in sorted(equips, key=lambda x: x["equip"]):
        cl = e.get("classificacio") or []
        if not cl:
            continue
        lletra = e["equip"].split('"')[1] if '"' in e["equip"] else ""
        divisio = e["competicio"].split(" · ", 1)[1] if " · " in e["competicio"] else e["competicio"]
        files = "".join(
            f'<tr class="{"mon" if c.get("mon") else ""}"><td class="p">{esc(c.get("pos"))}</td>'
            f'<td class="n">{esc(bonic(c["equip"]))}</td><td class="j">{esc(c.get("j"))}</td><td class="v">{esc(c.get("pm"))}</td></tr>'
            for c in cl)
        grups.append(f"""<div class="grp"><h3><b>{esc(lletra)}</b>{esc(divisio)}</h3><table>
          <tr class="cap"><td class="p"></td><td class="n">EQUIP</td><td class="j">J</td><td class="v">PTS</td></tr>{files}</table></div>""")
    return f'<div class="cls">{"".join(grups)}</div>'


def captura(htmls, pngs):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(viewport={"width": 1080, "height": 1350})
        for h, png in zip(htmls, pngs):
            pg.goto(h.as_uri())
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(png))
        nav.close()


def video(png1, png2, mp4):
    """Vídeo d'11 s: resultats (5 s), transició lliscant (1 s), classificacions (5 s)."""
    if not shutil.which("ffmpeg"):
        print("No hi ha ffmpeg: no es genera el vídeo.")
        return False
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-t", "6", "-framerate", "30", "-i", str(png1),
           "-loop", "1", "-t", "6", "-framerate", "30", "-i", str(png2),
           "-filter_complex", "[0][1]xfade=transition=slideleft:duration=1:offset=5,format=yuv420p",
           "-c:v", "libx264", "-r", "30", "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    return True


def main():
    ref = datetime.date.fromisoformat(os.environ["DATA"]) if os.environ.get("DATA") else datetime.date.today()
    dies = int(os.environ.get("DIES", "7"))
    dades = json.loads(EQUIPS.read_text(encoding="utf-8"))
    partits = partits_de_la_setmana(dades["equips"], ref, dies)
    if not partits:
        print("No hi ha partits aquesta setmana: no es genera cap imatge.")
        return
    dates = sorted(p["m"]["date"] for p in partits if p["m"].get("date") and p["m"]["date"] <= ref.isoformat())
    dia = max(set(dates), key=dates.count) if dates else ref.isoformat()
    competicio = partits[0]["competicio"].split(" · ")[0].upper()
    tres_bandes = "TRES BANDES" in competicio or "3 BANDES" in competicio
    titol = "Resultats Lliga 3 Bandes" if tres_bandes else "Resultats de Lliga"
    jornades = sorted({str(p["m"]["jornada"]) for p in partits}, key=lambda x: int(x) if x.isdigit() else 0)
    logo = logo_html()
    SORTIDA.mkdir(exist_ok=True)
    base = f"resultats-{ref.isoformat()}"
    h1, h2 = SORTIDA / f"{base}-1.html", SORTIDA / f"{base}-2.html"
    p1, p2, mp4 = SORTIDA / f"{base}-1.png", SORTIDA / f"{base}-2.png", SORTIDA / f"{base}.mp4"
    temporada = dades.get("temporada", "")
    h1.write_text(pagina(diapo_resultats(partits), f"Jornada {', '.join(jornades)} · {data_llarga(dia)}",
                         temporada, logo, titol), encoding="utf-8")
    h2.write_text(pagina(diapo_classificacions(dades["equips"]), f"Classificació actual · {data_llarga(ref.isoformat())}",
                         temporada, logo, "Classificacions" + (" 3 Bandes" if tres_bandes else "")), encoding="utf-8")
    captura([h1, h2], [p1, p2])
    h1.unlink()
    h2.unlink()
    fet = video(p1, p2, mp4)
    print(f"Creat: {p1.name}, {p2.name}{', ' + mp4.name if fet else ''} ({len(partits)} partits)")


if __name__ == "__main__":
    sys.exit(main())
