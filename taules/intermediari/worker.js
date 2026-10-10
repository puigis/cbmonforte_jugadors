// Intermediari de TAULES (Cloudflare Worker)
// Fa de pont entre TAULES (https) i monforte.wifibillar.com (http):
//  - consulta quines taules estan ocupades
//  - llegeix pools, fases, jugadors i caramboles
//  - crea jugadors, els assigna a la pool i genera la partida
//
// Rutes:
//   GET  /                                   -> taules ocupades
//   GET  /?accio=pools                       -> pools on es poden generar partides
//   GET  /?accio=fases&pool=N                -> fases d'una pool
//   GET  /?accio=formulari&pool=N&fase=F     -> taules lliures, jugadors assignats, modalitat, entrades
//   GET  /?accio=jugadors                    -> tots els jugadors del wifibillar
//   GET  /?accio=caramboles&pool=N&fase=F&jugador=J -> caramboles que proposa el wifibillar
//   POST /?accio=crear   (JSON)              -> crea jugadors si cal, assigna i genera la partida
//   GET  /?accio=crear&simular=1&dades=JSON  -> mostra què enviaria, sense enviar res
//   GET  /?veure=...                         -> consulta d'una pàgina (només lectura, per diagnosi)

const BASE = "http://monforte.wifibillar.com/";
const TAULES = [1, 2, 3, 4];

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Cache-Control": "no-store",
};
const JSON_H = { ...CORS, "Content-Type": "application/json; charset=utf-8" };
const TEXT_H = { ...CORS, "Content-Type": "text/plain; charset=utf-8" };

// Capçaleres com les d'un navegador normal
const CAPCALERES = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "ca,es;q=0.9",
  "Referer": BASE,
};

/* ---------- utilitats ---------- */

// El wifibillar treballa en iso-8859-1 (latin1)
function latin1(buf) {
  const b = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  return s;
}
// Codifica un formulari en latin1, com ho faria el navegador en aquesta web
function codificar(camps) {
  const enc = s => {
    let o = "";
    for (const ch of String(s)) {
      let c = ch.charCodeAt(0);
      if (c > 255) c = 63; // '?'
      if ((c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || "-_.*".includes(ch)) o += ch;
      else if (c === 32) o += "+";
      else o += "%" + c.toString(16).toUpperCase().padStart(2, "0");
    }
    return o;
  };
  return camps.map(([k, v]) => enc(k) + "=" + enc(v)).join("&");
}
function entitats(s) {
  return s
    .replace(/&nbsp;/g, " ").replace(/&quot;/g, '"').replace(/&#0?39;/g, "'")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
    .replace(/&amp;/g, "&");
}
function netejar(html) {
  return entitats(html.replace(/<br\s*\/?>/gi, " ").replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}
const reEsc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function attr(tag, nom) {
  const m = tag.match(new RegExp("\\b" + nom + "\\s*=\\s*(?:'([^']*)'|\"([^\"]*)\"|([^\\s>]+))", "i"));
  return m ? entitats(m[1] ?? m[2] ?? m[3] ?? "") : null;
}
// Opcions d'un <select name="...">
function opcions(html, nom) {
  const m = html.match(new RegExp("<select[^>]*name\\s*=\\s*['\"]" + reEsc(nom) + "['\"][^>]*>([\\s\\S]*?)</select>", "i"));
  if (!m) return null;
  return [...m[1].matchAll(/<option([^>]*)>([\s\S]*?)<\/option>/gi)].map(o => ({
    valor: attr("<x " + o[1] + ">", "value") ?? netejar(o[2]),
    text: netejar(o[2]),
    triat: /\bselected\b/i.test(o[1]),
  }));
}
// Valor triat d'un select (si n'hi ha diversos de marcats, el navegador es queda amb l'últim)
function triat(ops) {
  if (!ops || !ops.length) return null;
  const t = ops.filter(o => o.triat);
  return (t.length ? t[t.length - 1] : ops[0]).valor;
}
// Tots els <input> amb nom
function inputs(html) {
  return [...html.matchAll(/<input\b[^>]*>/gi)].map(m => ({
    tag: m[0], nom: attr(m[0], "name"), valor: attr(m[0], "value") ?? "", tipus: (attr(m[0], "type") || "text").toLowerCase(),
  })).filter(i => i.nom);
}
const valorInput = (html, nom) => (inputs(html).find(i => i.nom === nom) || {}).valor ?? null;

async function pagina(url, camps) {
  const opts = { headers: { ...CAPCALERES }, redirect: "follow" };
  if (camps) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/x-www-form-urlencoded";
    opts.body = codificar(camps);
  }
  const r = await fetch(BASE + url, opts);
  const html = latin1(await r.arrayBuffer());
  if (r.status >= 500 && html.length < 50) throw new Error("El wifibillar ha respost amb error " + r.status);
  return html;
}

/* ---------- taules ocupades ---------- */

async function llegirTaula(n) {
  const html = await pagina("veurepartida.php?taula=" + n);
  // Una taula ocupada mostra l'acta de la partida, que porta "TAULA: n"
  const ocupada = /TAULA:\s*\d/i.test(html);
  const t = { taula: n, ocupada };
  if (ocupada) {
    const link = [...html.matchAll(/<a[^>]*>([\s\S]*?)<\/a>/gi)].map(m => netejar(m[1])).find(x => x && !/refrescar/i.test(x));
    if (link) t.competicio = link;
    const cel = [...html.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].slice(0, 2).map(m => netejar(m[1]));
    if (cel.length === 2) t.equips = cel[0] + " – " + cel[1];
  }
  return t;
}
const taulesOcupades = async () => Promise.all(TAULES.map(llegirTaula));

/* ---------- lectura ---------- */

async function pools() {
  const html = await pagina("generar_partides12.php?vinc=1&refrescar=0");
  return (opcions(html, "clau_pool") || []).filter(o => o.valor !== "X").map(o => ({ id: o.valor, nom: o.text }));
}
async function fases(pool) {
  const html = await pagina("generar_partides12.php", [["clau_pool", pool], ["vinc", "4"]]);
  return (opcions(html, "fase") || []).filter(o => o.valor !== "X").map(o => ({ id: o.valor, nom: o.text }));
}
// Formulari de generar partides d'una pool i fase
async function formulariGenerar(pool, fase) {
  const html = await pagina("generar_partides12.php", [["clau_pool", pool], ["fase", fase], ["vinc", "3"]]);
  const lliures = inputs(html).filter(i => /^taula\[\d+\]$/.test(i.nom)).map(i => +i.valor);
  const t0 = lliures[0];
  const jugadors = t0 ? (opcions(html, `idjugador1[${t0}]`) || []).filter(o => o.valor !== "N").map(o => ({ id: o.valor, nom: o.text })) : [];
  const modalitats = t0 ? (opcions(html, `modalitat[${t0}]`) || []).map(o => ({ id: o.valor, nom: o.text })) : [];
  return {
    html, lliures, jugadors, modalitats,
    modalitat: t0 ? triat(opcions(html, `modalitat[${t0}]`)) : null,
    entrades: t0 ? valorInput(html, `topeent[${t0}]`) : null,
    ocultes: {
      clau_pool: valorInput(html, "clau_pool"),
      taulesocupades: valorInput(html, "taulesocupades"),
      fase: valorInput(html, "fase"),
      tipus_fase: valorInput(html, "tipus_fase"),
      indexacio: valorInput(html, "indexacio"),
    },
  };
}
async function totsJugadors() {
  const html = await pagina("mante_jugadors.php?vinc=1&refrescar=0");
  return (opcions(html, "clau_jugador") || []).filter(o => o.valor !== "X" && o.valor !== "A").map(o => ({ id: o.valor, nom: o.text }));
}
async function caramboles(pool, fase, jugador) {
  const t = (await pagina(`calcular_caramboles1.php?id_jugador=${encodeURIComponent(jugador)}&clau_pool=${encodeURIComponent(pool)}&fase=${encodeURIComponent(fase)}`)).trim();
  return /^\d+$/.test(t) && t !== "0" ? +t : null;
}

/* ---------- escriptura ---------- */

const normNom = s => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().replace(/\s+/g, " ").trim();
// Nom alfabètic d'una entrada de la llista "COGNOMS, NOM(nom marcador)"
const alfDe = nom => normNom(nom.split("(")[0]);

// Dona d'alta un jugador nou (o retorna el que ja existeix amb el mateix nom alfabètic)
async function crearJugador(nou, simular, registre) {
  const abans = await totsJugadors();
  const existent = abans.find(j => alfDe(j.nom) === normNom(nou.alfabetic));
  if (existent) { registre.push(`Jugador ja existent: ${existent.nom} (${existent.id})`); return existent.id; }
  const form = await pagina("mante_jugadors.php", [["clau_jugador", "A"], ["vinc", "3"]]);
  const indexacio = valorInput(form, "indexacio");
  if (!/Afegeix/i.test(form) || !indexacio) throw new Error("No s'ha pogut obrir el formulari d'alta de jugador");
  const camps = [
    ["nom_jugador_alfabetic", nou.alfabetic], ["nom_jugador", nou.marcador], ["fed_jugador", "cat"],
    ["fotourl", ""], ["actiu_jugador", "S"], ["vinc", "2"], ["id_jugador", ""], ["indexacio", indexacio],
  ];
  if (simular) { registre.push({ pas: "alta jugador", camps }); return "NOU:" + nou.alfabetic; }
  await pagina("mante_jugadors.php", camps);
  const despres = await totsJugadors();
  const creat = despres.find(j => alfDe(j.nom) === normNom(nou.alfabetic) && !abans.some(a => a.id === j.id));
  if (!creat) throw new Error("He enviat l'alta de " + nou.alfabetic + " però no apareix a la llista de jugadors");
  registre.push(`Jugador creat: ${creat.nom} (${creat.id})`);
  return creat.id;
}

// Assigna jugadors a la pool i fase, respectant tots els que ja hi són
async function assignar(pool, fase, ids, simular, registre) {
  const html = await pagina("assignar_jugadors_fasepool.php", [["clau_pool", pool], ["vinc", "3"]]);
  const totals = +valorInput(html, "jugadors");
  if (!totals) throw new Error("No s'ha pogut llegir la llista d'assignació de la pool");
  const nFases = +valorInput(html, "fases") || 1;
  const camps = [];
  const pendents = new Set(ids.map(String));
  let canvis = 0;
  for (let n = 1; n <= totals; n++) {
    const id = valorInput(html, `idjug[${n}]`);
    camps.push([`idjug[${n}]`, id]);
    for (let f = 1; f <= nFases; f++) {
      let v = triat(opcions(html, `fasegrup[${n}][${f}]`)) ?? "";
      if (String(f) === String(fase) && pendents.has(String(id)) && v === "") { v = "A"; canvis++; }
      camps.push([`fasegrup[${n}][${f}]`, v]);
      const c = valorInput(html, `caramb[${n}][${f}]`);
      if (c !== null) camps.push([`caramb[${n}][${f}]`, c]);
    }
    pendents.delete(String(id));
  }
  if (pendents.size) throw new Error("Aquests jugadors no surten a la llista d'assignació: " + [...pendents].join(", "));
  for (const k of ["jugadors", "clau_pool", "grups", "fases"]) camps.push([k, valorInput(html, k)]);
  camps.push(["vinc", "4"]);
  if (!canvis) { registre.push("Els jugadors ja estaven assignats a la pool"); return; }
  if (simular) { registre.push({ pas: "assignar", canvis, total_jugadors: totals, camps: camps.filter(([k, v]) => !/^idjug|^caramb/.test(k) && v !== "") }); return; }
  await pagina("assignar_jugadors_fasepool.php", camps);
  registre.push(`Assignats ${canvis} jugador(s) a la pool`);
}

async function crear(d, simular) {
  const registre = [];
  const pool = String(d.pool), fase = String(d.fase), taula = +d.taula;
  if (!pool || !fase || !taula) throw new Error("Falten la pool, la fase o la taula");
  if (!Array.isArray(d.jugadors) || d.jugadors.length !== 2) throw new Error("Calen dos jugadors");

  // 0. La taula ha d'estar lliure
  const ocupades = await taulesOcupades();
  if (ocupades.find(t => t.taula === taula && t.ocupada)) throw new Error(`La taula ${taula} ja té una partida creada`);

  // 1. Jugadors nous
  const ids = [];
  for (const j of d.jugadors) ids.push(j.id ? String(j.id) : await crearJugador(j.nou, simular, registre));

  // 2. Assignar (només els que encara no hi són)
  let form = await formulariGenerar(pool, fase);
  const falten = ids.filter(id => !form.jugadors.some(j => j.id === id));
  if (falten.length) {
    await assignar(pool, fase, falten.filter(id => !id.startsWith("NOU:")), simular, registre);
    if (falten.some(id => id.startsWith("NOU:"))) registre.push({ pas: "assignar", nota: "També s'hi assignarien els jugadors nous" });
    if (!simular) form = await formulariGenerar(pool, fase);
  }

  // 3. Generar la partida
  if (!form.lliures.includes(taula)) throw new Error(`La taula ${taula} no surt com a lliure al wifibillar`);
  if (!form.ocultes.indexacio) throw new Error("No s'ha pogut obrir el formulari de generar partides");
  if (!simular) for (const id of ids) if (!form.jugadors.some(j => j.id === id)) throw new Error("Un jugador no ha quedat assignat a la pool (" + id + ")");
  const camps = [];
  for (const t of form.lliures) {
    const meva = t === taula;
    camps.push(
      [`idjugador1[${t}]`, meva ? ids[0] : "N"], [`idjugador2[${t}]`, meva ? ids[1] : "N"],
      [`modalitat[${t}]`, meva ? String(d.modalitat || form.modalitat) : String(form.modalitat)],
      [`topecar1[${t}]`, meva ? String(d.caramboles?.[0] ?? "") : ""], [`topecar2[${t}]`, meva ? String(d.caramboles?.[1] ?? "") : ""],
      [`topeent[${t}]`, meva ? String(d.entrades || form.entrades || 50) : String(form.entrades || 50)],
      [`id_partida[${t}]`, "X"], [`taula[${t}]`, String(t)],
    );
  }
  for (const [k, v] of Object.entries(form.ocultes)) camps.push([k, v ?? ""]);
  camps.push(["vinc", "2"]);
  if (simular) { registre.push({ pas: "generar partida", camps }); return { simulat: true, registre }; }
  await pagina("generar_partides12.php", camps);

  // 4. Comprovar
  const ara = await llegirTaula(taula);
  if (!ara.ocupada) throw new Error("He enviat la partida però la taula " + taula + " no surt ocupada. Revisa el wifibillar.");
  registre.push(`Partida creada a la taula ${taula}`);
  return { creada: true, taula: ara, registre };
}

/* ---------- consulta de pàgines (només lectura, diagnosi) ---------- */

const PAGINES = {
  generar:  { url: "generar_partides12.php",         vinc: ["3", "4"] },
  quilles:  { url: "generar_partides12_quilles.php", vinc: ["3", "4"] },
  artistic: { url: "generar_partides12_art.php",     vinc: ["3", "4"] },
  assignar: { url: "assignar_jugadors_fasepool.php", vinc: ["3"] },
  jugadors: { url: "mante_jugadors.php",             vinc: ["3"] },
};
async function veurePagina(params) {
  const p = PAGINES[params.get("veure")];
  if (!p) return new Response("Pàgina no permesa", { status: 400, headers: TEXT_H });
  const vinc = params.get("vinc") || p.vinc[0];
  if (!p.vinc.includes(vinc)) return new Response("Pas no permès", { status: 400, headers: TEXT_H });
  const camps = [["vinc", vinc]];
  for (const c of ["clau_pool", "fase", "clau_jugador"]) if (params.get(c)) camps.push([c, params.get(c)]);
  return new Response(await pagina(p.url, camps), { headers: TEXT_H });
}

/* ---------- entrada ---------- */

const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: JSON_H });

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    const params = new URL(request.url).searchParams;
    try {
      if (params.get("veure")) return await veurePagina(params);
      const accio = params.get("accio");
      if (!accio) return json({ actualitzat: new Date().toISOString(), taules: await taulesOcupades() });
      if (accio === "pools") return json(await pools());
      if (accio === "fases") return json(await fases(params.get("pool")));
      if (accio === "formulari") {
        const f = await formulariGenerar(params.get("pool"), params.get("fase"));
        return json({ lliures: f.lliures, jugadors: f.jugadors, modalitats: f.modalitats, modalitat: f.modalitat, entrades: f.entrades });
      }
      if (accio === "jugadors") return json(await totsJugadors());
      if (accio === "caramboles") return json({ caramboles: await caramboles(params.get("pool"), params.get("fase"), params.get("jugador")) });
      if (accio === "crear") {
        if (request.method === "POST") return json(await crear(await request.json(), false));
        // Per GET només es permet simular: mai escriu res
        return json(await crear(JSON.parse(params.get("dades") || "{}"), true));
      }
      return json({ error: "Acció desconeguda" }, 400);
    } catch (e) {
      return json({ error: String(e.message || e) }, 502);
    }
  },
};
