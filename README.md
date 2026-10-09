# CB Monforte · Dades de competició

Base de dades dels resultats de lliga dels equips i jugadors del **Club Billar Monforte**, extreta de la web pública de la Federació Catalana de Billar ([intranet.fcbillar.cat](https://intranet.fcbillar.cat/frontend/lligues/llistat)).

Les dades es guarden en fitxers CSV dins de la carpeta `dades/`. Es poden obrir amb Excel o Google Sheets i reutilitzar des de qualsevol altre projecte.

## Com està organitzada la font

```
Lliga  →  Divisió  →  Grup  →  Jornada  →  Encontre (equip vs equip)  →  Partida (jugador vs jugador)
```

Patrons d'URL de la Federació:

| Nivell | URL |
|---|---|
| Lligues | `/frontend/lligues/llistat` |
| Divisions d'una lliga | `/frontend/lligues/divisions/{lliga}` |
| Grups d'una divisió | `/frontend/lligues/grups/{lliga}/{divisio}` |
| Jornades d'un grup | `/frontend/lligues/jornades/{lliga}/{divisio}/{grup}` |
| Classificació d'un grup | `/frontend/lligues/classificacio/{lliga}/{divisio}/{grup}` |
| Encontres d'una jornada | `/frontend/lligues/encontres/{lliga}/{divisio}/{grup}/{jornada}` |
| Partides d'un encontre | `/frontend/lligues/partides/{lliga}/{divisio}/{grup}/{jornada}/{encontre}` |
| Jugadors inscrits d'un club | `/frontend/lligues/participants/{lliga}/{club}` |

El CB Monforte és el club amb identificador **2**.

## Fitxers de dades (`dades/`)

Taules generals (tota la Federació, totes les temporades des del 2012):

| Fitxer | Què conté |
|---|---|
| `competicions.csv` | Totes les lligues i competicions individuals, amb modalitat i temporada |
| `jugadors.csv` | Tots els jugadors, el club actual, l'historial de clubs i si són del Monforte |
| `partides.csv` | Totes les partides jugador contra jugador (lligues i individuals) |
| `encontres.csv` | Encontres de lliga equip contra equip |
| `classificacions_lliga.csv` | Classificacions dels grups de lliga |
| `classificacions_individuals.csv` | Classificacions finals de les competicions individuals |
| `rankings.csv` | Tots els rànquings de la Federació (3 bandes, banda, lliure, quadre 47/2 i 71/2) |

Fitxers per a l'app del club (`dades/monforte/`), només de la **temporada actual**:

| Fitxer | Què conté |
|---|---|
| `index.json` | Llista de tots els fitxers disponibles i dels jugadors actuals del club |
| `lligues/<lliga>/<equip>.json` | Un fitxer per equip (A, B, C, D, E…), amb el mateix format que l'app Monforte C |
| `modalitats/<modalitat>.json` | Per a cada modalitat: jugadors del Monforte, estadístiques, rànquing i totes les seves partides |

Notes:
- La modalitat dels opens que no la diuen al nom es dedueix per la mitjana de les partides (columna `modalitat_deduida`).
- Biathló, 5 quilles i artístic surten com a competicions, però la Federació no n'ha publicat resultats.

## L'app

`index.html` és l'app del club (es publica amb GitHub Pages). Té tres pestanyes:

- **Equips**: els equips del Monforte d'aquesta temporada, amb jugadors, partits i calendari.
- **Rànquing**: per a cada modalitat, tres vistes: *inici de temporada* (rànquing del 27/07/2026), *federatiu* (darrer rànquing publicat, cada mes) i *personal* (calculat amb les partides que la Federació encara no ha comptat).
- **Jugadors**: tots els jugadors del club. Tocant qualsevol nom s'obre la seva fitxa: rànquings, evolució, les partides que fan el promig, les pendents de comptar i l'historial de totes les temporades.

Com es calcula el rànquing (comprovat amb les dades de la Federació): caramboles ÷ entrades de les darreres **15 partides a tres bandes** i **10 a la resta de modalitats**. Els jugadors que encara no tenen aquest nombre de partides són provisionals i van al final. Les dades de l'app les genera `scraper/app_dades.py` a `dades/app/`.

## Descàrrega de dades

El script `scraper/descarrega.py` recorre totes les pàgines públiques de **Lligues, Individuals, Copa i Rànquings** (tres bandes, banda, lliure, quadre, biathló i la resta de modalitats que hi hagi) i en desa el contingut en brut a `dades/brut/<secció>/<competició>.jsonl`.

S'executa automàticament a GitHub **cada diumenge a primera hora** (cap a les 6:00). Per llançar-lo a mà: pestanya **Actions** → *Descarrega dades de la Federació* → **Run workflow**. Marcant l'opció *historic* també prova les competicions de temporades passades.

Snooker i pool no surten a la intranet de competició de la Federació; s'afegiran quan en localitzem la font.

## Estat del projecte

- [x] Pas 1 · Repositori creat
- [x] Pas 2 · Estructura de dades definida
- [x] Pas 3 · Script que descarrega totes les dades de la Federació
- [x] Pas 4 · Automatització amb GitHub Actions
- [x] Pas 5 · Organitzar les dades en taules (`scraper/organitza.py`, s'executa després de cada descàrrega)
- [x] Pas 6 · App del club (equips, rànquings i fitxes de jugador)
- [x] Pas 7 · Imatge de resultats automàtica cada diumenge
- [ ] Pas 8 · Publicació automàtica a xarxes socials

## Imatge de resultats

Cada **diumenge a les 16:00** (hora de Madrid) el workflow *Imatge de resultats del cap de setmana* baixa els resultats nous (mode ràpid, només la temporada actual), actualitza l'app i genera el cartell amb tots els equips del Monforte que han jugat (1080 × 1350, format vertical d'Instagram):
`imatges/resultats-AAAA-MM-DD-1.png` amb el resultat final de cada partit, `…-2.png` amb les classificacions, i `….mp4`, un vídeo amb transició entre les dues. Es pot llançar a mà des d'**Actions → Run workflow**, i indicar una data per refer la d'un cap de setmana passat. El script és `scraper/imatge_resultats.py`.

## Pendent d'actualitzar

- **Rànquing d'opens**: quan la Federació publiqui el primer, extreure'l i afegir-lo a la fitxa de cada jugador.
- **Snooker i pool**: localitzar on es publiquen els resultats i afegir-los a la base de dades.
- **5 quilles (individual i per parelles), biathló i artístic**: la Federació encara no n'ha publicat resultats; s'afegiran sols quan n'hi hagi.
- **Logo del CB Monforte**: desar-lo com a `imatges/logo.png` (o .svg) perquè surti als cartells; ara hi ha un segell provisional.
- **Publicació automàtica a les xarxes socials** (falta decidir a quines). Continguts previstos:
  - Resultats dels partits de lliga (el cartell de cada diumenge).
  - Campionats aconseguits pels nostres jugadors.
  - Jugadors classificats per a les fases finals.
  - Notícies i imatges del club.
  - Informació general: comunicats de la junta, dies de tancament del club i horaris extraordinaris.
