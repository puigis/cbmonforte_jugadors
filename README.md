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

| Fitxer | Què conté |
|---|---|
| `lligues.csv` | Cada lliga: modalitat i temporada |
| `grups.csv` | Divisions i grups on juga algun equip del Monforte |
| `jornades.csv` | Número i data de cada jornada |
| `encontres.csv` | Resultats equip contra equip |
| `partides.csv` | Resultats jugador contra jugador |
| `classificacions.csv` | Classificació de cada grup |

Es guarden els grups complets (també els equips rivals) perquè les classificacions i les imatges tinguin tota la informació.

## Descàrrega de dades

El script `scraper/descarrega.py` recorre totes les pàgines públiques de **Lligues, Individuals, Copa i Rànquings** (tres bandes, banda, lliure, quadre, biathló i la resta de modalitats que hi hagi) i en desa el contingut en brut a `dades/brut/<secció>/<competició>.jsonl`.

S'executa automàticament a GitHub **cada dilluns**. Per llançar-lo a mà: pestanya **Actions** → *Descarrega dades de la Federació* → **Run workflow**. Marcant l'opció *historic* també prova les competicions de temporades passades.

Snooker i pool no surten a la intranet de competició de la Federació; s'afegiran quan en localitzem la font.

## Estat del projecte

- [x] Pas 1 · Repositori creat
- [x] Pas 2 · Estructura de dades definida
- [x] Pas 3 · Script que descarrega totes les dades de la Federació
- [x] Pas 4 · Automatització amb GitHub Actions
- [ ] Pas 5 · Organitzar les dades en brut a les taules de `dades/`
- [ ] Pas 6 · Plantilla i generació d'imatges per a xarxes
