"""
Reel (vídeo vertical 9:16) dels resultats de la Lliga 3 Bandes, amb música.

Fa servir la mateixa plantilla que el cartell (scraper/cartell_lliga/plantilla.html)
en "mode Reel": els resultats van apareixent un a un i el segell AJORNAT "pica".
Cada setmana sona una cançó diferent de scraper/cartell_lliga/musica/ (en rotació);
les de musica/especials.json només sonen la jornada que tenen assignada.

Sortida: imatges/reel-lliga-AAAA-MM-DD.mp4  (1080 x 1920, 30 fps, ~12 s)

Opcions (variables d'entorn):
  DATA=2026-10-11   Dia de referència (per defecte avui).
  DIES=7            Quants dies enrere es miren.
  CANCO=03          Força una cançó concreta (prefix del nom del fitxer).
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cartell_lliga import ARREL, EQUIPS, SORTIDA, PLANTILLA, converteix  # noqa: E402

MUSICA = Path(__file__).resolve().parent / "cartell_lliga" / "musica"
FPS = 30
DURADA = 12.0


def tria_canco(dia, forcada=None, dies=7):
    """Cançó de la setmana: la reservada per a aquella jornada (musica/especials.json)
    o, si no n'hi ha, una de les altres en rotació segons el número de setmana."""
    cancons = sorted(MUSICA.glob("*.mp3"))
    if not cancons:
        return None
    per_prefix = lambda pre: next((c for c in cancons if c.name.startswith(pre)), None)
    if forcada:
        return per_prefix(forcada) or cancons[0]
    especials = {}
    fitxer = MUSICA / "especials.json"
    if fitxer.exists():
        especials = {k: v for k, v in json.loads(fitxer.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    ref = datetime.date.fromisoformat(dia)
    inici = ref - datetime.timedelta(days=dies - 1)
    for data, pre in especials.items():
        if inici <= datetime.date.fromisoformat(data) <= ref and per_prefix(pre):
            return per_prefix(pre)
    reservades = set(especials.values())
    normals = [c for c in cancons if not any(c.name.startswith(r) for r in reservades)] or cancons
    return normals[ref.isocalendar()[1] % len(normals)]


def fotogrames(dades, carpeta):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pag = nav.new_page(viewport={"width": 1080, "height": 1920})
        pag.add_init_script("window.REEL = true;")
        pag.add_init_script(f"window.DADES = {json.dumps(dades, ensure_ascii=False)};")
        pag.goto(PLANTILLA.as_uri())
        pag.wait_for_load_state("networkidle")
        pag.evaluate("document.fonts.ready")
        total = int(DURADA * FPS)
        for n in range(total):
            ms = n * 1000 / FPS
            pag.evaluate(f"document.getAnimations().forEach(a => {{ a.pause(); a.currentTime = {ms}; }})")
            pag.screenshot(path=str(carpeta / f"f{n:04d}.jpg"), type="jpeg", quality=92)
        nav.close()


def munta_video(carpeta, canco, sortida):
    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(carpeta / "f%04d.jpg")]
    if canco:
        cmd += ["-i", str(canco), "-af", f"afade=t=out:st={DURADA - 1.5}:d=1.5", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
            "-movflags", "+faststart", "-t", str(DURADA), str(sortida)]
    subprocess.run(cmd, check=True)


def main():
    ref = os.environ.get("DATA") or None
    dies = int(os.environ.get("DIES") or 7)
    dades = converteix(EQUIPS, ref, dies)
    if dades is None:
        print("Aquesta setmana no hi ha partits de lliga: no es genera el Reel.")
        return
    dia = ref or datetime.date.today().isoformat()
    canco = tria_canco(dia, os.environ.get("CANCO"), dies)
    SORTIDA.mkdir(exist_ok=True)
    sortida = SORTIDA / f"reel-lliga-{dia}.mp4"
    carpeta = Path(tempfile.mkdtemp(prefix="reel-"))
    try:
        fotogrames(dades, carpeta)
        munta_video(carpeta, canco, sortida)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    print(f"Cançó: {canco.name if canco else '(cap)'}")
    print(f"Reel desat a {sortida.relative_to(ARREL)}")


if __name__ == "__main__":
    main()
