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
//   POST /?accio=foto {id,url}               -> canvia la foto (fotourl) d'un jugador del Monforte (enllaç de Drive)
//   GET  /?accio=foto&id=N&url=...           -> simula el canvi de foto, sense escriure res
//   GET  /?veure=...                       -> consulta d'una pàgina (només lectura, per diagnosi)
//   GET  /?accio=conv&j=N                    -> convocatòries dels equips A-E de la jornada N (app CONVOCATORIES)
//   POST /?accio=conv&j=N  {equips:{B:{...}}} -> desa la convocatòria dels equips que s'envien
//   GET  /?accio=biatlo                      -> resultats del Campionat de Catalunya de Biatló (app BIATLO)
//   POST /?accio=biatlo-entrar {usuari,contrasenya} -> token d'administrador (30 dies)
//   POST /?accio=biatlo {token,id,dades|null} -> desa (o esborra) el resultat d'una partida (només administradors)
//   POST /?accio=biatlo-sortir {token}       -> tanca la sessió

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

// Nom de la competició que surt a l'acta (subratllat, o en un enllaç)
function competicioActa(html) {
  const u = html.match(/<u>([\s\S]*?)<\/u>/i);
  if (u && netejar(u[1])) return netejar(u[1]);
  return [...html.matchAll(/<a[^>]*>([\s\S]*?)<\/a>/gi)].map(m => netejar(m[1])).find(x => x && !/refrescar/i.test(x)) || null;
}
// La partida ha començat si hi ha alguna entrada anotada a l'acta.
// Cada fila de l'acta és: ## | c1 | suma | ## | c1 | suma | ... ; el ## sempre porta el número d'entrada.
function partidaComencada(html) {
  for (const fila of html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)) {
    const cel = [...fila[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)].map(m => netejar(m[1]));
    if (cel.length < 3 || !/^\d+$/.test(cel[0])) continue;   // només files d'entrades
    for (let i = 0; i < cel.length; i++) if (i % 3 !== 0 && cel[i] !== "") return true;
  }
  return false;
}

async function llegirTaula(n) {
  const html = await pagina("veurepartida.php?taula=" + n);
  // Una taula ocupada mostra l'acta de la partida, que porta "TAULA: n"
  const ocupada = /TAULA:\s*\d/i.test(html);
  const t = { taula: n, ocupada };
  if (ocupada) {
    const comp = competicioActa(html);
    if (comp) t.competicio = comp;
    t.comencada = partidaComencada(html);
    const cel = [...html.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].slice(0, 2).map(m => netejar(m[1]));
    if (cel.length === 2) t.equips = cel[0] + " – " + cel[1];
  }
  return t;
}
const taulesOcupades = async () => Promise.all(TAULES.map(llegirTaula));

/* ---------- lectura ---------- */

// Pàgina de generar partides segons el tipus de pool: carambola (3 bandes, banda, lliure...) o quilles (també el biatló)
const GENERADOR = { "": "generar_partides12.php", quilles: "generar_partides12_quilles.php" };
const generador = tipus => GENERADOR[tipus === "quilles" ? "quilles" : ""];
async function pools() {
  const [car, qui] = await Promise.all([
    pagina("generar_partides12.php?vinc=1&refrescar=0"),
    pagina("generar_partides12_quilles.php?vinc=1&refrescar=0").catch(() => ""),
  ]);
  const llista = (opcions(car, "clau_pool") || []).filter(o => o.valor !== "X").map(o => ({ id: o.valor, nom: o.text }));
  for (const o of (opcions(qui, "clau_pool") || []).filter(o => o.valor !== "X"))
    if (!llista.some(p => p.id === o.valor)) llista.push({ id: o.valor, nom: o.text, tipus: "quilles" });
  return llista;
}
async function fases(pool, tipus) {
  const html = await pagina(generador(tipus), [["clau_pool", pool], ["vinc", "4"]]);
  return (opcions(html, "fase") || []).filter(o => o.valor !== "X").map(o => ({ id: o.valor, nom: o.text }));
}
// Tots els camps de cada taula lliure (nom[t]) amb el valor que proposa el wifibillar, i els camps ocults generals.
// Serveix per a la pàgina de quilles, que té camps propis: s'envien tal com venen i només es canvien jugadors, caramboles i entrades.
function campsFormulari(html) {
  const perTaula = {}, generals = [];
  const afegeix = (nom, v) => { const m = nom.match(/\[(\d+)\]$/); if (m) (perTaula[m[1]] = perTaula[m[1]] || []).push([nom, v]); else generals.push([nom, v]); };
  for (const i of inputs(html)) {
    if (["submit", "button", "reset", "image", "file"].includes(i.tipus)) continue;
    if ((i.tipus === "checkbox" || i.tipus === "radio") && !/\bchecked\b/i.test(i.tag)) continue;
    if (!/\[\d+\]$/.test(i.nom) && i.tipus !== "hidden") continue;
    afegeix(i.nom, i.valor);
  }
  for (const m of html.matchAll(/<select[^>]*name\s*=\s*['"]([^'"]+)['"]/gi)) afegeix(m[1], triat(opcions(html, m[1])) ?? "");
  for (const m of html.matchAll(/<textarea[^>]*name\s*=\s*['"]([^'"]+)['"][^>]*>([\s\S]*?)<\/textarea>/gi)) afegeix(m[1], entitats(m[2]));
  return { perTaula, generals: generals.filter(([k]) => k !== "vinc") };
}
// Formulari de generar partides d'una pool i fase
async function formulariGenerar(pool, fase, tipus) {
  const html = await pagina(generador(tipus), [["clau_pool", pool], ["fase", fase], ["vinc", "3"]]);
  const lliures = inputs(html).filter(i => /^taula\[\d+\]$/.test(i.nom)).map(i => +i.valor);
  const t0 = lliures[0];
  const jugadors = t0 ? (opcions(html, `idjugador1[${t0}]`) || []).filter(o => o.valor !== "N").map(o => ({ id: o.valor, nom: o.text })) : [];
  const modalitats = t0 ? (opcions(html, `modalitat[${t0}]`) || []).map(o => ({ id: o.valor, nom: o.text })) : [];
  return {
    html, lliures, jugadors, modalitats,
    modalitat: t0 ? triat(opcions(html, `modalitat[${t0}]`)) : null,
    camps: tipus === "quilles" ? campsFormulari(html) : null,
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
  // El formulari envia els dos desplegables (actius i no actius), com el navegador
  const form = await pagina("mante_jugadors.php", [["clau_jugador", "A"], ["clau_jugadorno", "X"], ["vinc", "3"]]);
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

// Canvia el "nom marcador" d'un jugador que ja existeix (ex. 'C.B.MONFORTE "E" (B.Villate)' -> 'CB MONFORTE (B.Villate)').
// Obre la seva fitxa, hi canvia només aquest camp i torna a enviar tota la resta tal com estava.
// Si alguna cosa no quadra, no toca res i ho apunta al registre (la partida es crea igualment).
async function canviaMarcador(id, marcador, simular, registre) {
  marcador = String(marcador || "").trim();
  if (!marcador || String(id).startsWith("NOU:")) return;
  // Si el wifibillar no el desa a la primera (passa amb el segon jugador seguit), ho torna a provar
  for (let intent = 1; intent <= 3; intent++) {
    const r = await canviaMarcadorUnCop(id, marcador, simular, registre, intent === 3, intent > 1);
    if (r !== "reintentar") return;
    await new Promise(ok => setTimeout(ok, 1500 * intent));
  }
}
async function canviaMarcadorUnCop(id, marcador, simular, registre, ultim, reintent) {
  const form = await pagina("mante_jugadors.php", [["clau_jugador", id], ["clau_jugadorno", "X"], ["vinc", "3"]]);
  const ins = inputs(form);
  const val = n => (ins.find(i => i.nom === n) || {}).valor;
  const actual = val("nom_jugador"), alf = val("nom_jugador_alfabetic");
  if (actual == null || !alf || String(val("id_jugador")) !== String(id) || !val("indexacio")) {
    registre.push(`No he pogut obrir la fitxa del jugador ${id} per canviar el nom del marcador (es queda com estava)`);
    return;
  }
  if (actual.trim() === marcador) { if (reintent) registre.push(`Nom al marcador: ${marcador}`); return "fet"; }
  const NO = new Set(["clau_jugador", "clau_jugadorno", "vinc"]);
  const camps = [];
  for (const i of ins) {
    if (NO.has(i.nom) || ["submit", "button", "reset", "image", "file"].includes(i.tipus)) continue;
    if ((i.tipus === "checkbox" || i.tipus === "radio") && !/\bchecked\b/i.test(i.tag)) continue;
    camps.push([i.nom, i.nom === "nom_jugador" ? marcador : i.valor]);
  }
  for (const m of form.matchAll(/<select[^>]*name\s*=\s*['"]([^'"]+)['"]/gi)) {
    if (NO.has(m[1]) || camps.some(c => c[0] === m[1])) continue;
    camps.push([m[1], triat(opcions(form, m[1])) ?? ""]);
  }
  camps.push(["vinc", "2"]);
  if (simular) { registre.push({ pas: "canviar nom marcador", jugador: alf, abans: actual, despres: marcador, camps }); return; }
  await pagina("mante_jugadors.php", camps);
  const ara = (await totsJugadors()).find(j => String(j.id) === String(id));
  if (ara && ara.nom.includes(marcador)) { registre.push(`Nom al marcador: ${actual} -> ${marcador}`); return "fet"; }
  if (!ultim) return "reintentar";
  registre.push(`He intentat canviar el nom al marcador de ${alf} però no s'ha desat (es queda: ${actual})`);
}

// Canvia la foto (camp "fotourl") de la fitxa d'un jugador del Monforte.
// Només accepta enllaços de Google Drive. Obre la fitxa, canvia només aquest camp i torna a enviar la resta tal com estava.
// Guarda l'enllaç anterior al KV (foto:ID) per poder-lo recuperar.
async function canviaFoto(d, env) {
  const id = String(d.id || "").trim(), url = String(d.url || "").trim();
  if (!/^\d+$/.test(id)) throw new Error("Falta l'identificador del jugador");
  if (!/^https:\/\/(drive|lh\d)\.google(usercontent)?\.com\/[\w\-/?=&.%]+$/.test(url)) throw new Error("L'enllaç ha de ser de Google Drive");
  const form = await pagina("mante_jugadors.php", [["clau_jugador", id], ["clau_jugadorno", "X"], ["vinc", "3"]]);
  const ins = inputs(form);
  const val = n => (ins.find(i => i.nom === n) || {}).valor;
  const alf = val("nom_jugador_alfabetic"), marcador = val("nom_jugador") || "";
  if (!alf || String(val("id_jugador")) !== id || !val("indexacio")) throw new Error("No he pogut obrir la fitxa del jugador " + id);
  if (!/MONFORTE/i.test(marcador)) throw new Error("Aquest jugador no és del Monforte: " + alf);
  const abans = val("fotourl") ?? "";
  if (abans.trim() === url) return { jugador: alf, fet: true, abans, ara: url, nota: "Ja tenia aquesta foto" };
  const NO = new Set(["clau_jugador", "clau_jugadorno", "vinc"]);
  const camps = [];
  for (const i of ins) {
    if (NO.has(i.nom) || ["submit", "button", "reset", "image", "file"].includes(i.tipus)) continue;
    if ((i.tipus === "checkbox" || i.tipus === "radio") && !/\bchecked\b/i.test(i.tag)) continue;
    camps.push([i.nom, i.nom === "fotourl" ? url : i.valor]);
  }
  if (!camps.some(c => c[0] === "fotourl")) throw new Error("La fitxa no té el camp de la foto");
  for (const m of form.matchAll(/<select[^>]*name\s*=\s*['"]([^'"]+)['"]/gi)) {
    if (NO.has(m[1]) || camps.some(c => c[0] === m[1])) continue;
    camps.push([m[1], triat(opcions(form, m[1])) ?? ""]);
  }
  camps.push(["vinc", "2"]);
  if (d.simular) return { jugador: alf, simulat: true, abans, ara: url };
  if (env && env.CAMS) await env.CAMS.put("foto:" + id, JSON.stringify({ abans, ara: url, quan: new Date().toISOString() }));
  for (let intent = 1; intent <= 3; intent++) {
    await pagina("mante_jugadors.php", camps);
    const despres = await pagina("mante_jugadors.php", [["clau_jugador", id], ["clau_jugadorno", "X"], ["vinc", "3"]]);
    if ((valorInput(despres, "fotourl") || "").trim() === url) return { jugador: alf, fet: true, abans, ara: url };
    await new Promise(ok => setTimeout(ok, 1500 * intent));
  }
  throw new Error("He enviat la foto nova de " + alf + " però el wifibillar no l'ha desada");
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

  // 1b. Nom al marcador amb el format del club: "CB MONFORTE (I.Puig)"
  for (const [k, j] of d.jugadors.entries()) {
    if (!j.id || !j.marcador) continue;
    try { await canviaMarcador(ids[k], j.marcador, simular, registre); }
    catch (e) { registre.push("No s'ha pogut canviar el nom al marcador: " + (e.message || e)); }
  }

  // 2. Assignar (només els que encara no hi són)
  const tipus = d.tipus === "quilles" ? "quilles" : "";
  let form = await formulariGenerar(pool, fase, tipus);
  const falten = ids.filter(id => !form.jugadors.some(j => j.id === id));
  if (falten.length) {
    await assignar(pool, fase, falten.filter(id => !id.startsWith("NOU:")), simular, registre);
    if (falten.some(id => id.startsWith("NOU:"))) registre.push({ pas: "assignar", nota: "També s'hi assignarien els jugadors nous" });
    if (!simular) form = await formulariGenerar(pool, fase, tipus);
  }

  // 3. Generar la partida
  if (!form.lliures.includes(taula)) throw new Error(`La taula ${taula} no surt com a lliure al wifibillar`);
  if (!form.ocultes.indexacio) throw new Error("No s'ha pogut obrir el formulari de generar partides");
  if (!simular) for (const id of ids) if (!form.jugadors.some(j => j.id === id)) throw new Error("Un jugador no ha quedat assignat a la pool (" + id + ")");
  const camps = [];
  if (tipus === "quilles") {
    // Pàgina de quilles: tots els camps tal com els proposa el wifibillar; només es canvien jugadors, caramboles i entrades
    const fc = form.camps;
    for (const t of form.lliures) {
      const meva = t === taula;
      for (const [nom, v] of fc.perTaula[t] || []) {
        const base = nom.replace(/\[\d+\]$/, "");
        let val = v;
        if (base === "idjugador1") val = meva ? ids[0] : "N";
        else if (base === "idjugador2") val = meva ? ids[1] : "N";
        else if (meva && base === "topecar1" && d.caramboles?.[0]) val = String(d.caramboles[0]);
        else if (meva && base === "topecar2" && d.caramboles?.[1]) val = String(d.caramboles[1]);
        else if (meva && base === "topeent" && d.entrades) val = String(d.entrades);
        else if (base === "id_partida") val = "X";
        camps.push([nom, val ?? ""]);
      }
    }
    for (const [k, v] of fc.generals) if (k !== "vinc") camps.push([k, v ?? ""]);
    camps.push(["vinc", "2"]);
    if (simular) { registre.push({ pas: "generar partida (quilles)", camps }); return { simulat: true, registre }; }
    await pagina(generador(tipus), camps);
  } else {
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
  }

  // 4. Comprovar
  const ara = await llegirTaula(taula);
  if (!ara.ocupada) throw new Error("He enviat la partida però la taula " + taula + " no surt ocupada. Revisa el wifibillar.");
  registre.push(`Partida creada a la taula ${taula}`);
  return { creada: true, taula: ara, registre };
}

/* ---------- anul·lar una partida que encara no ha començat ---------- */

async function anular(taula, simular) {
  taula = +taula;
  if (!TAULES.includes(taula)) throw new Error("Taula incorrecta");
  const acta = await pagina("veurepartida.php?taula=" + taula);
  if (!/TAULA:\s*\d/i.test(acta)) throw new Error(`La taula ${taula} no té cap partida creada`);
  if (partidaComencada(acta)) return { comencada: true };

  // Pool de la partida: la que té el mateix nom que la competició de l'acta
  const comp = normNom(competicioActa(acta) || "");
  const totes = await pools();
  const ordre = [...totes.filter(p => normNom(p.nom) === comp), ...totes.filter(p => normNom(p.nom) !== comp)];

  // Busca la partida en joc a aquesta taula a la pàgina d'eliminar
  const reTaula = new RegExp("\\[taula:\\s*" + taula + "\\]\\s*\\[En joc:\\s*S\\]", "i");
  let trobada = null;
  for (const p of ordre) {
    const fasesPool = await fasesEliminar(p.id);
    for (const f of fasesPool) {
      const html = await pagina("eliminar_partides.php", [["clau_pool", p.id], ["fase", f], ["vinc", "3"]]);
      const o = (opcions(html, "partida") || []).find(o => o.valor !== "X" && reTaula.test(o.text));
      if (o) { trobada = { pool: p.id, fase: f, partida: o.valor, text: o.text }; break; }
    }
    if (trobada) break;
  }
  if (!trobada) throw new Error(`No he trobat la partida de la taula ${taula} a la llista d'eliminar del wifibillar`);

  const camps = [["clau_pool", trobada.pool], ["fase", trobada.fase], ["partida", trobada.partida], ["vinc", "2"]];
  if (simular) return { simulat: true, partida: trobada.text, camps };

  // Torna a comprovar just abans d'eliminar, per si s'acaba d'anotar una entrada
  if (partidaComencada(await pagina("veurepartida.php?taula=" + taula))) return { comencada: true };
  await pagina("eliminar_partides.php", camps);
  const ara = await llegirTaula(taula);
  if (ara.ocupada) throw new Error(`He enviat l'anul·lació però la taula ${taula} encara surt ocupada. Revisa el wifibillar.`);
  return { anulada: true, partida: trobada.text };
}
async function fasesEliminar(pool) {
  const html = await pagina("eliminar_partides.php", [["clau_pool", pool], ["vinc", "4"]]);
  return (opcions(html, "fase") || []).filter(o => o.valor !== "X").map(o => o.valor);
}

/* ---------- consulta de pàgines (només lectura, diagnosi) ---------- */

const PAGINES = {
  generar:  { url: "generar_partides12.php",         vinc: ["3", "4"] },
  quilles:  { url: "generar_partides12_quilles.php", vinc: ["3", "4"] },
  artistic: { url: "generar_partides12_art.php",     vinc: ["3", "4"] },
  assignar: { url: "assignar_jugadors_fasepool.php", vinc: ["3"] },
  jugadors: { url: "mante_jugadors.php",             vinc: ["3"] },
  eliminar: { url: "eliminar_partides.php",          vinc: ["4", "3"] },   // només triar pool i fase: mai elimina
};
async function veurePagina(params) {
  // Acta d'una taula, tal com la mostra el wifibillar
  // Títols per a YouTube que prepara el wifibillar (ELABORACIÓ llistats → Taules youtube)
  if (params.get("veure") === "youtube") return new Response(await pagina("youtube.php?refrescar=0"), { headers: TEXT_H });
  if (params.get("veure") === "acta") return new Response(await pagina("veurepartida.php?taula=" + (+params.get("taula") || 1)), { headers: TEXT_H });
  const p = PAGINES[params.get("veure")];
  if (!p) return new Response("Pàgina no permesa", { status: 400, headers: TEXT_H });
  const vinc = params.get("vinc") || p.vinc[0];
  if (!p.vinc.includes(vinc)) return new Response("Pas no permès", { status: 400, headers: TEXT_H });
  const camps = [["vinc", vinc]];
  for (const c of ["clau_pool", "fase", "clau_jugador", "clau_jugadorno"]) if (params.get(c)) camps.push([c, params.get(c)]);
  return new Response(await pagina(p.url, camps), { headers: TEXT_H });
}

/* ---------- entrada ---------- */

const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: JSON_H });

/* ---------- càmeres: cua d'ordres i estat (Cloudflare KV, enllaç "CAMS") ---------- */
// L'app hi deixa ordres; el programa del PC del club les recull i hi publica l'estat.
const CLAU_PC = "cbmonforte-610393230cc6f165";   // només el programa del club pot publicar l'estat
async function cameres(accio, request, params, env) {
  const kv = env && env.CAMS;
  if (!kv) return json({ error: "Falta l'enllaç CAMS (KV) a l'intermediari" }, 500);
  if (accio === "cam" && request.method === "POST") {
    const taula = +params.get("taula"), on = params.get("on") === "1";
    if (!(taula >= 1 && taula <= 4)) return json({ error: "Taula incorrecta" }, 400);
    const ordres = (await kv.get("ordres", "json")) || [];
    const id = Date.now();
    ordres.push({ id, taula, on });
    await kv.put("ordres", JSON.stringify(ordres.filter(o => id - o.id < 10 * 60 * 1000).slice(-50)));
    return json({ ok: true, id });
  }
  if (accio === "ordres") {             // el PC del club demana les ordres noves
    if (params.get("clau") !== CLAU_PC) return json({ error: "No permès" }, 403);
    const des = +params.get("des") || 0;
    const ordres = ((await kv.get("ordres", "json")) || []).filter(o => o.id > des);
    return json({ ara: Date.now(), ordres });
  }
  if (accio === "estat" && request.method === "POST") {   // el PC del club publica l'estat
    if (params.get("clau") !== CLAU_PC) return json({ error: "No permès" }, 403);
    const e = await request.json();
    await kv.put("estat", JSON.stringify({ cams: e.cams || {}, t: Math.floor(Date.now() / 1000) }));
    return json({ ok: true });
  }
  if (accio === "estat") return json((await kv.get("estat", "json")) || { cams: {}, t: 0 });
  return json({ error: "Acció desconeguda" }, 400);
}

/* ---------- convocatòries de lliga (app CONVOCATORIES, KV "CAMS", clau conv:jN) ---------- */
async function convocatories(request, params, env) {
  const kv = env && env.CAMS;
  if (!kv) return json({ error: "Falta l'enllaç CAMS (KV) a l'intermediari" }, 500);
  const j = parseInt(params.get("j"), 10);
  if (!(j >= 1 && j <= 40)) return json({ error: "Jornada incorrecta" }, 400);
  const clau = "conv:j" + j;
  const equips = (await kv.get(clau, "json")) || {};
  if (request.method !== "POST") return json({ j, equips });
  const cos = await request.json();
  const nous = (cos && cos.equips) || {};
  for (const [t, e] of Object.entries(nous)) {
    if (!["A", "B", "C", "D", "E"].includes(t) || !e || typeof e !== "object") return json({ error: "Equip incorrecte" }, 400);
    const conv = Array.isArray(e.conv) ? e.conv.filter(x => typeof x === "string" && x.length < 80).slice(0, 12) : [];
    equips[t] = {
      conv: [...new Set(conv)],
      perj: !!e.perj,
      perjMsg: typeof e.perjMsg === "string" ? e.perjMsg.slice(0, 200) : "",
      data: typeof e.data === "string" && /^\d{4}-\d{2}-\d{2}$/.test(e.data) ? e.data : null,
      hora: typeof e.hora === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(e.hora) ? e.hora : null,
      t: Date.now(),
    };
  }
  await kv.put(clau, JSON.stringify(equips));
  return json({ j, equips });
}

/* ---------- Campionat de Catalunya de Biatló (app BIATLO, KV "CAMS", clau biatlo:2026) ---------- */
// Administradors: només ells poden anotar resultats. Les contrasenyes no es guarden: només el seu hash (PBKDF2-SHA256).
// Per canviar-ne una, demana a Claude un hash nou.
const ADMINS_BIATLO = {
  isaacpuig:  { nom: "Isaac Puig",        sal: "45f2da5272921d9f67f43b35ed91abed", hash: "90cf0dc67406432f268717b67fa96623012883157cf71bb59d2b30f8f8f90ddf" },
  jonhzuleta: { nom: "John Jairo Zuleta", sal: "1258a391afcdaf8fae321ac20e1c506e", hash: "5009b6baf6e7570c68f7a9739a5b505dc58f3b5b9181cb570f03784a43956815" },
  monforte:   { nom: "CB Monforte",       sal: "cf7d786767e0e356d24cffe787e5895c", hash: "9fab81578a586a4d41d2c36d35740639cf986307ea78fb366cd0dbdc9b0c9171" },
};
const hexBytes = h => new Uint8Array(h.match(/../g).map(x => parseInt(x, 16)));
const bytesHex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
async function pbkdf2(pass, salHex) {
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(pass), "PBKDF2", false, ["deriveBits"]);
  return bytesHex(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: hexBytes(salHex), iterations: 100000 }, k, 256));
}
async function usuariDelToken(kv, token) {
  if (!token || !/^[0-9a-f]{48}$/.test(token)) return null;
  return await kv.get("biatlo:tok:" + token);
}
async function biatlo(request, params, env) {
  const kv = env && env.CAMS;
  if (!kv) return json({ error: "Falta l'enllaç CAMS (KV) a l'intermediari" }, 500);
  const accio = params.get("accio");
  if (accio === "biatlo-entrar" && request.method === "POST") {
    const cos = await request.json().catch(() => ({}));
    const u = String(cos.usuari || "").trim().toLowerCase().replace(/\s+/g, "");
    const a = ADMINS_BIATLO[u];
    await new Promise(r => setTimeout(r, 400));   // frena els intents a cegues
    if (!a || (await pbkdf2(String(cos.contrasenya || ""), a.sal)) !== a.hash) return json({ error: "Usuari o contrasenya incorrectes" }, 403);
    const token = bytesHex(crypto.getRandomValues(new Uint8Array(24)));
    await kv.put("biatlo:tok:" + token, a.nom, { expirationTtl: 60 * 60 * 24 * 30 });
    return json({ token, nom: a.nom });
  }
  if (accio === "biatlo-sortir" && request.method === "POST") {
    const cos = await request.json().catch(() => ({}));
    if (cos.token && /^[0-9a-f]{48}$/.test(cos.token)) await kv.delete("biatlo:tok:" + cos.token);
    return json({ ok: true });
  }
  const clau = "biatlo:2026";
  const res = (await kv.get(clau, "json")) || {};
  if (request.method !== "POST") return json({ resultats: res });
  const cos = await request.json();
  const qui = await usuariDelToken(kv, cos && cos.token);
  if (!qui) return json({ error: "Cal entrar com a administrador" }, 401);
  const id = String(cos.id || "");
  if (!/^(G[A-G][123]|Q[1-4]|S[12]|F)$/.test(id)) return json({ error: "Partida incorrecta" }, 400);
  if (cos.dades === null) { delete res[id]; }
  else {
    const d = cos.dades || {}, n = v => Math.max(0, Math.min(999, parseInt(v, 10) || 0));
    res[id] = { c1: n(d.c1), q1: n(d.q1), c2: n(d.c2), q2: n(d.q2), e: n(d.e),
      s1: n(d.s1), s2: n(d.s2), g: d.g === 1 || d.g === 2 ? d.g : 0, t: Date.now(), per: qui };
  }
  await kv.put(clau, JSON.stringify(res));
  return json({ resultats: res });
}

/* ---------- YouTube: títol automàtic del directe de cada taula ---------- */
// Cada canal dona permís una vegada (/yt/connecta?taula=N&clau=...). Es desa el permís a KV "yt:N".
// Quan la taula emet, el PC del club crida ?accio=yt_titol&taula=N&clau=... i es posa el títol amb les dades de l'acta.
// Cal definir a Cloudflare (Settings → Variables and Secrets): GOOGLE_CLIENT_ID i GOOGLE_CLIENT_SECRET.
const YT_SCOPE = "https://www.googleapis.com/auth/youtube";
const ytRedirect = request => new URL("/yt/callback", request.url).toString();
const html = (cos, status = 200) => new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MARCADORS · YouTube</title><body style="font:18px system-ui,sans-serif;max-width:560px;margin:40px auto;padding:0 16px;line-height:1.5">${cos}</body>`,
  { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
const escH = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function ytToken(env, taula) {
  const d = await env.CAMS.get("yt:" + taula, "json");
  if (!d || !d.refresh) throw new Error(`La taula ${taula} no té cap canal de YouTube connectat`);
  const r = await fetch("https://oauth2.googleapis.com/token", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, refresh_token: d.refresh, grant_type: "refresh_token" }) });
  const t = await r.json();
  if (!t.access_token) throw new Error("Google no ha renovat el permís de la taula " + taula + ": " + (t.error_description || t.error || r.status) + ". Torna a connectar el canal.");
  return { token: t.access_token, canal: d.canal };
}
async function ytApi(token, cami, opts = {}) {
  const r = await fetch("https://www.googleapis.com/youtube/v3/" + cami, { ...opts, headers: { Authorization: "Bearer " + token, "Content-Type": "application/json", ...(opts.headers || {}) } });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error("YouTube: " + ((j.error && j.error.message) || r.status));
  return j;
}
// Títol a partir de l'acta: "Lliga Catalana 3 bandes 4a divisió · Taula 1 · CB MONFORTE (B.Villate) vs CB MONFORTE (J.Gili)"
async function titolTaula(taula) {
  const acta = await pagina("veurepartida.php?taula=" + taula);
  if (!/TAULA:\s*\d/i.test(acta)) return null;
  const comp = competicioActa(acta) || "";
  const cel = [...acta.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].slice(0, 2).map(m => netejar(m[1]).replace(/\s*\(\d+\)\s*$/, ""));
  let t = [comp, "Taula " + taula, cel.length === 2 ? cel[0] + " vs " + cel[1] : ""].filter(Boolean).join(" · ");
  t = t.replace(/[<>]/g, "");
  return t.length > 100 ? t.slice(0, 99) + "…" : t;
}
async function ytTitol(env, taula, forcat) {
  const titol = (forcat || "").trim() || await titolTaula(taula);
  if (!titol) return { pendent: true, motiu: `La taula ${taula} no té cap partida creada` };
  const { token, canal } = await ytToken(env, taula);
  const emissions = (await ytApi(token, "liveBroadcasts?part=snippet,status&broadcastStatus=active&broadcastType=all&maxResults=5")).items || [];
  if (!emissions.length) return { pendent: true, motiu: `El canal ${canal} encara no té cap directe en marxa` };
  const b = emissions.sort((x, y) => String(y.snippet.actualStartTime || "").localeCompare(String(x.snippet.actualStartTime || "")))[0];
  const v = ((await ytApi(token, "videos?part=snippet&id=" + b.id)).items || [])[0];
  if (!v) return { pendent: true, motiu: "YouTube encara no mostra el vídeo del directe" };
  if (v.snippet.title === titol) return { ok: true, canal, titol, video: b.id, ja: true };
  const sn = { title: titol, categoryId: v.snippet.categoryId || "17", description: v.snippet.description || "" };
  if (v.snippet.tags) sn.tags = v.snippet.tags;
  if (v.snippet.defaultLanguage) sn.defaultLanguage = v.snippet.defaultLanguage;
  await ytApi(token, "videos?part=snippet", { method: "PUT", body: JSON.stringify({ id: b.id, snippet: sn }) });
  return { ok: true, canal, titol, video: b.id };
}
async function youtube(cami, request, params, env) {
  if (!env.CAMS) return json({ error: "Falta l'enllaç CAMS (KV) a l'intermediari" }, 500);
  if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_CLIENT_SECRET) return html("<h2>Falta configurar Google</h2><p>Cal posar GOOGLE_CLIENT_ID i GOOGLE_CLIENT_SECRET a Cloudflare (Settings → Variables and Secrets).</p>", 500);
  if (cami === "/yt/connecta") {
    const taula = +params.get("taula");
    if (params.get("clau") !== CLAU_PC) return html("<h2>Enllaç no vàlid</h2>", 403);
    if (!(taula >= 1 && taula <= 4)) return html("<h2>Taula incorrecta</h2>", 400);
    const estat = crypto.randomUUID();
    await env.CAMS.put("ytestat:" + estat, String(taula), { expirationTtl: 900 });
    const u = new URL("https://accounts.google.com/o/oauth2/v2/auth");
    for (const [k, v] of Object.entries({ client_id: env.GOOGLE_CLIENT_ID, redirect_uri: ytRedirect(request), response_type: "code", scope: YT_SCOPE,
      access_type: "offline", prompt: "consent select_account", include_granted_scopes: "true", state: estat })) u.searchParams.set(k, v);
    return Response.redirect(u.toString(), 302);
  }
  if (cami === "/yt/callback") {
    if (params.get("error")) return html(`<h2>No s'ha connectat</h2><p>Google ha respost: ${escH(params.get("error"))}</p>`, 400);
    const taula = await env.CAMS.get("ytestat:" + params.get("state"));
    if (!taula) return html("<h2>L'enllaç ha caducat</h2><p>Torna a obrir l'enllaç de connexió de la taula.</p>", 400);
    await env.CAMS.delete("ytestat:" + params.get("state"));
    const r = await fetch("https://oauth2.googleapis.com/token", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ code: params.get("code") || "", client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, redirect_uri: ytRedirect(request), grant_type: "authorization_code" }) });
    const t = await r.json();
    if (!t.refresh_token) return html(`<h2>No s'ha connectat</h2><p>Google no ha donat permís permanent (${escH(t.error_description || t.error || "sense refresh_token")}). Torna-ho a provar.</p>`, 400);
    const ch = ((await ytApi(t.access_token, "channels?part=snippet&mine=true")).items || [])[0];
    const canal = ch ? ch.snippet.title : "(canal desconegut)";
    await env.CAMS.put("yt:" + taula, JSON.stringify({ refresh: t.refresh_token, canal, id: ch ? ch.id : null, t: Date.now() }));
    return html(`<h2>✅ Taula ${taula} connectada</h2><p>Canal de YouTube: <b>${escH(canal)}</b></p><p>Si no és el canal d'aquesta taula, torna a obrir l'enllaç i tria'n un altre.</p>`);
  }
  return json({ error: "Ruta desconeguda" }, 404);
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    const params = new URL(request.url).searchParams;
    try {
      const cami = new URL(request.url).pathname;
      if (cami.startsWith("/yt/")) return await youtube(cami, request, params, env);
      if (params.get("accio") === "yt_estat") {
        const out = {};
        for (const n of TAULES) { const d = env.CAMS && await env.CAMS.get("yt:" + n, "json"); out[n] = d ? d.canal : null; }
        return json(out);
      }
      if (params.get("accio") === "yt_titol") {
        if (params.get("clau") !== CLAU_PC) return json({ error: "No permès" }, 403);
        return json(await ytTitol(env, +params.get("taula"), params.get("titol")));
      }
      if (params.get("veure")) return await veurePagina(params);
      const accio = params.get("accio");
      if (["cam", "ordres", "estat"].includes(accio)) return await cameres(accio, request, params, env);
      if (accio === "conv") return await convocatories(request, params, env);
      if (accio && accio.startsWith("biatlo")) return await biatlo(request, params, env);
      if (!accio) return json({ actualitzat: new Date().toISOString(), taules: await taulesOcupades() });
      if (accio === "pools") return json(await pools());
      if (accio === "fases") return json(await fases(params.get("pool"), params.get("tipus")));
      if (accio === "formulari") {
        const f = await formulariGenerar(params.get("pool"), params.get("fase"), params.get("tipus"));
        return json({ lliures: f.lliures, jugadors: f.jugadors, modalitats: f.modalitats, modalitat: f.modalitat, entrades: f.entrades });
      }
      if (accio === "jugadors") return json(await totsJugadors());
      if (accio === "foto") {
        // Per GET només es permet simular: mai escriu res
        if (request.method === "POST") return json(await canviaFoto(await request.json(), env));
        return json(await canviaFoto({ id: params.get("id"), url: params.get("url"), simular: true }, env));
      }
      if (accio === "caramboles") return json({ caramboles: await caramboles(params.get("pool"), params.get("fase"), params.get("jugador")) });
      if (accio === "anular") {
        // Per GET només es permet simular: mai elimina res
        return json(await anular(params.get("taula"), request.method !== "POST"));
      }
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
