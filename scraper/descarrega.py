"""
Descarrega tota la informació pública de competició de la Federació Catalana de Billar
(https://intranet.fcbillar.cat/frontend/...) i la desa en brut a dades/brut/.

Recorre les seccions Lligues, Individuals, Copa i Rànquings seguint tots els enllaços
interns, i de cada pàgina en guarda els títols, la ruta (breadcrumb), les taules i els enllaços.

Opcions (variables d'entorn):
  HISTORIC=1      També prova identificadors antics de competicions (temporades passades).
  MAX_MINUTS=300  Temps màxim d'execució; en arribar-hi desa el que tingui i s'atura.
  PAUSA=0.3       Segons d'espera entre peticions, per no sobrecarregar la web.
"""

import json
import os
import re
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://intranet.fcbillar.cat"
SECCIONS = ["lligues", "individuals", "copa", "rankings"]
SORTIDA = Path(__file__).resolve().parent.parent / "dades" / "brut"

HISTORIC = os.environ.get("HISTORIC", "0") == "1"
MAX_SEGONS = float(os.environ.get("MAX_MINUTS", "300")) * 60
PAUSA = float(os.environ.get("PAUSA", "0.3"))

sessio = requests.Session()
sessio.headers["User-Agent"] = "CB-Monforte-dades/1.0 (+https://github.com/puigis/cbmonforte_jugadors)"


def neteja(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalitza(url):
    """Retorna l'URL absolut sense fragment, o None si queda fora de l'àmbit."""
    url = urljoin(BASE + "/", url).split("#")[0]
    p = urlparse(url)
    if p.netloc != urlparse(BASE).netloc:
        return None
    if not p.path.startswith("/frontend/"):
        return None
    if "login" in p.path:
        return None
    return url.rstrip("/")


def baixa(url):
    for intent in range(4):
        try:
            r = sessio.get(url, timeout=30)
            if r.status_code == 200:
                return r.text
            if r.status_code in (404, 410):
                return None
        except requests.RequestException:
            pass
        time.sleep(2 * (intent + 1))
    return None


def llegeix_taula(taula):
    capcaleres = [neteja(th.get_text(" ")) for th in taula.select("thead th")]
    files = []
    for tr in taula.select("tbody tr") or taula.select("tr"):
        celles = tr.find_all(["td", "th"])
        if not celles or (not capcaleres and tr.find("th") and not tr.find("td")):
            if not capcaleres:
                capcaleres = [neteja(c.get_text(" ")) for c in celles]
            continue
        fila = []
        for c in celles:
            enllac = c.find("a", href=True)
            cel = {"text": neteja(c.get_text(" "))}
            if enllac and normalitza(enllac["href"]):
                cel["enllac"] = normalitza(enllac["href"])
            fila.append(cel)
        files.append(fila)
    return {"capcaleres": capcaleres, "files": files}


def analitza(url, html):
    sopa = BeautifulSoup(html, "html.parser")
    for el in sopa.select("form, script, style, nav, footer"):
        el.decompose()
    titols = [neteja(h.get_text(" ")) for h in sopa.select("h1, h2, h3, h4, h5")]
    ruta = [neteja(li.get_text(" ")) for li in (sopa.select(".breadcrumb li") or sopa.select(".breadcrumb a"))]
    taules = [llegeix_taula(t) for t in sopa.find_all("table")]
    enllacos = sorted({u for a in sopa.find_all("a", href=True) if (u := normalitza(a["href"]))})
    return {
        "url": url,
        "titols": [t for t in titols if t],
        "ruta": [r for r in ruta if r],
        "taules": [t for t in taules if t["files"] or t["capcaleres"]],
        "enllacos": enllacos,
    }


def te_contingut(pagina):
    return any(t["files"] for t in pagina["taules"])


def clau_fitxer(url):
    """Agrupa les pàgines per secció i competició: dades/brut/<seccio>/<id>.jsonl"""
    p = urlparse(url)
    trossos = p.path.strip("/").split("/")  # frontend, seccio, vista, ids...
    seccio = trossos[1] if len(trossos) > 1 else "altres"
    qs = parse_qs(p.query)
    if "idranking" in qs:
        return seccio, qs["idranking"][0]
    ids = [t for t in trossos[3:] if t.isdigit()]
    return seccio, ids[0] if ids else "llistats"


def llavors_historiques(maxims):
    """Prova identificadors de competicions anteriors als que surten als llistats."""
    for seccio, maxim in maxims.items():
        for i in range(1, maxim):
            yield f"{BASE}/frontend/{seccio}/divisions/{i}"


def main():
    inici = time.time()
    cua = deque(f"{BASE}/frontend/{s}/llistat" for s in SECCIONS)
    vistes = set(cua)
    pagines = defaultdict(dict)
    maxims = defaultdict(int)
    historic_afegit = False
    errors = 0

    while cua or (HISTORIC and not historic_afegit):
        if not cua:
            historic_afegit = True
            for u in llavors_historiques(maxims):
                if u not in vistes:
                    vistes.add(u)
                    cua.append(u)
            print(f"Afegides pàgines històriques a provar: {len(cua)}", flush=True)
            continue
        if time.time() - inici > MAX_SEGONS:
            print("Temps màxim assolit: es desa el que s'ha descarregat.", flush=True)
            break

        url = cua.popleft()
        html = baixa(url)
        time.sleep(PAUSA)
        if html is None:
            errors += 1
            continue
        pagina = analitza(url, html)
        if te_contingut(pagina) or "/llistat" in url:
            seccio, clau = clau_fitxer(url)
            pagines[(seccio, clau)][url] = pagina

        m = re.match(rf"{BASE}/frontend/(lligues|individuals|copa)/divisions/(\d+)$", url)
        if m:
            maxims[m.group(1)] = max(maxims[m.group(1)], int(m.group(2)))

        for enllac in pagina["enllacos"]:
            if enllac not in vistes:
                vistes.add(enllac)
                cua.append(enllac)

        total = sum(len(v) for v in pagines.values())
        if total % 200 == 0:
            minuts = (time.time() - inici) / 60
            print(f"{total} pàgines desades · {len(cua)} a la cua · {minuts:.0f} min", flush=True)

    SORTIDA.mkdir(parents=True, exist_ok=True)
    for (seccio, clau), contingut in pagines.items():
        carpeta = SORTIDA / seccio
        carpeta.mkdir(exist_ok=True)
        fitxer = carpeta / f"{clau}.jsonl"
        existents = {}
        if fitxer.exists():
            for linia in fitxer.read_text(encoding="utf-8").splitlines():
                d = json.loads(linia)
                existents[d["url"]] = d
        existents.update(contingut)
        with fitxer.open("w", encoding="utf-8") as f:
            for u in sorted(existents):
                f.write(json.dumps(existents[u], ensure_ascii=False) + "\n")

    total = sum(len(v) for v in pagines.values())
    print(f"Fet: {total} pàgines desades en {len(pagines)} fitxers ({errors} sense resposta).")
    if total == 0:
        sys.exit("No s'ha pogut descarregar res.")


if __name__ == "__main__":
    main()
