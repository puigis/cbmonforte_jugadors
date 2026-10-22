"""
#DiaDePartit automàtic: història (imatge 1080x1920) i Reel amb música dels partits A CASA d'avui.

Llegeix:
  - el calendari oficial de cada equip (dades/app/equips.json)
  - l'app CONVOCATORIES (intermediari de Cloudflare): data canviada, hora i convocats de cada jornada
Un partit és "d'avui" si la data efectiva (la canviada a l'app o, si no n'hi ha, l'oficial) és avui.
Si no hi ha convocats a l'app, la imatge surt sense noms.

Sortida (només si avui hi ha algun partit a casa):
  imatges/diadepartit-AAAA-MM-DD.png   història
  imatges/diadepartit-AAAA-MM-DD.mp4   Reel (10 s, amb música)
  imatges/diadepartit-AAAA-MM-DD.json  dades (per redactar el text de la publicació)

Opcions (variables d'entorn):
  DATA=2026-10-22   Dia (per defecte avui, hora de Madrid).
  CONV=fitxer.json  Llegeix les convocatòries d'un fitxer {jornada: {equip: {...}}} en lloc de l'intermediari (proves).
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cartell_lliga import ARREL, EQUIPS, SORTIDA, divisio, nom_club  # noqa: E402
from reel_lliga import tria_canco  # noqa: E402

API = "https://taules-monforte.puigis.workers.dev/"
APP_CONV = ARREL / "taules" / "convocatories" / "index.html"
PLANTILLA = Path(__file__).resolve().parent / "dia_partit" / "plantilla.html"
FPS, DURADA = 30, 10.0
DIES = ["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"]
MESOS = ["gener", "febrer", "març", "abril", "maig", "juny", "juliol", "agost", "setembre", "octubre", "novembre", "desembre"]


def dia_llarg(d):
    mes = MESOS[d.month - 1]
    return f"{DIES[d.weekday()].capitalize()} {d.day} {'d' + chr(39) if mes[0] in 'aeiou' else 'de '}{mes}"


def jugadors_app():
    """id -> "Nom Cognom" a partir de la llista de jugadors de l'app de convocatòries."""
    text = APP_CONV.read_text(encoding="utf-8")
    dades = json.loads(re.search(r"const D=(\{.*?\});\n", text).group(1))
    noms = {}
    for p in dades["players"]:
        cognoms, nom = (p["n"].split(", ") + [""])[:2]
        noms[p["id"]] = f"{nom.split(' ')[0]} {cognoms.split(' ')[0]}".strip()
    return noms


def convocatories(jornades):
    fitxer = os.environ.get("CONV")
    if fitxer:
        return {int(k): v for k, v in json.loads(Path(fitxer).read_text(encoding="utf-8")).items()}
    totes = {}
    for j in jornades:
        req = urllib.request.Request(f"{API}?accio=conv&j={j}", headers={"User-Agent": "cbmonforte-diadepartit"})
        with urllib.request.urlopen(req, timeout=20) as r:
            totes[j] = json.load(r).get("equips", {})
    return totes


def partits_davui(avui):
    app = json.load(open(EQUIPS, encoding="utf-8"))
    jornades = sorted({int(c["jornada"]) for e in app["equips"] for c in e.get("calendar", [])})
    conv = convocatories(jornades)
    noms = jugadors_app()
    partits = []
    for e in app["equips"]:
        lletra = e["equip"].replace("“", '"').replace("”", '"').split('"')[1]
        for c in e.get("calendar", []):
            if c["venue"] != "L":
                continue                                   # només els partits a casa
            dc = (conv.get(int(c["jornada"])) or {}).get(lletra) or {}
            efectiva = dc.get("data") or c["date"]
            if efectiva != avui.isoformat() or c.get("played"):
                continue
            jug = [noms[i] for i in dc.get("conv") or [] if i in noms]
            partits.append({
                "equip": lletra,
                "divisio": f"Equip <b>{lletra}</b> · {divisio(e['competicio'])}<br>Jornada {c['jornada']}"
                           + (" (ajornada)" if efectiva > c["date"] else " (avançada)" if efectiva < c["date"] else ""),
                "jornada": c["jornada"],
                "rival": nom_club(c["rival"]),
                "hora": dc.get("hora") or "",
                "jugadors": jug,
            })
    return sorted(partits, key=lambda p: (p["hora"] or "99", p["equip"]))


def captura(dades, carpeta=None, png=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pag = nav.new_page(viewport={"width": 1080, "height": 1920})
        if carpeta:
            pag.add_init_script("window.REEL = true;")
        pag.add_init_script(f"window.DADES = {json.dumps(dades, ensure_ascii=False)};")
        pag.goto(PLANTILLA.as_uri())
        pag.wait_for_load_state("networkidle")
        pag.evaluate("document.fonts.ready")
        if png:
            pag.screenshot(path=str(png))
        else:
            for n in range(int(FPS * DURADA)):
                pag.evaluate(f"document.getAnimations().forEach(a => {{ a.pause(); a.currentTime = {n * 1000 / FPS}; }})")
                pag.screenshot(path=str(carpeta / f"f{n:04d}.jpg"), type="jpeg", quality=92)
        nav.close()


def main():
    avui = datetime.date.fromisoformat(os.environ["DATA"]) if os.environ.get("DATA") \
        else datetime.datetime.now(ZoneInfo("Europe/Madrid")).date()
    partits = partits_davui(avui)
    if not partits:
        print(f"{avui}: avui no hi ha cap partit a casa. No es genera res.")
        return
    dades = {"sub": f"Lliga 3 Bandes · <b>Avui</b> · {dia_llarg(avui)}", "dia": dia_llarg(avui), "partits": partits}
    SORTIDA.mkdir(exist_ok=True)
    base = SORTIDA / f"diadepartit-{avui.isoformat()}"
    captura(dades, png=base.with_suffix(".png"))
    carpeta = Path(tempfile.mkdtemp(prefix="diadepartit-"))
    try:
        captura(dades, carpeta=carpeta)
        canco = tria_canco(avui.isoformat())
        cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(carpeta / "f%04d.jpg")]
        if canco:
            cmd += ["-i", str(canco), "-af", f"afade=t=out:st={DURADA - 1.5}:d=1.5", "-c:a", "aac", "-b:a", "192k"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart",
                "-t", str(DURADA), str(base.with_suffix(".mp4"))]
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    base.with_suffix(".json").write_text(json.dumps(dades, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dades, ensure_ascii=False, indent=2))
    print(f"Desats {base.relative_to(ARREL)}.png/.mp4/.json")


if __name__ == "__main__":
    main()
