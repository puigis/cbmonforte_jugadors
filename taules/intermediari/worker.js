// Intermediari de TAULES (Cloudflare Worker)
// Llegeix monforte.wifibillar.com (http) i retorna en JSON quines taules
// tenen una partida creada, perquè TAULES (https) ho pugui consultar.
//
// Resposta:
// { "actualitzat": "...", "taules": [ {"taula":1,"ocupada":false}, {"taula":3,"ocupada":true,"competicio":"...","equips":"..."} ] }

const WIFIBILLAR = "http://monforte.wifibillar.com/veurepartida.php?taula=";
const TAULES = [1, 2, 3, 4];

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
};

// La pàgina del wifibillar està en iso-8859-1 (latin1)
function latin1(buf) {
  const b = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  return s;
}

function netejar(html) {
  return html
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

async function llegirTaula(n) {
  const r = await fetch(WIFIBILLAR + n, { cf: { cacheTtl: 0 } });
  if (!r.ok) throw new Error("wifibillar " + r.status);
  const html = latin1(await r.arrayBuffer());
  // Una taula ocupada mostra l'acta de la partida, que porta "TAULA: n"
  const ocupada = /TAULA:\s*\d/i.test(html);
  const t = { taula: n, ocupada };
  if (ocupada) {
    // La competició és l'enllaç sota el botó "REFRESCAR"
    const link = [...html.matchAll(/<a[^>]*>([\s\S]*?)<\/a>/gi)]
      .map(m => netejar(m[1]))
      .find(x => x && !/refrescar/i.test(x));
    if (link) t.competicio = link;
    const cel = [...html.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].slice(0, 2).map(m => netejar(m[1]));
    if (cel.length === 2) t.equips = cel[0] + " – " + cel[1];
  }
  return t;
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    try {
      const taules = await Promise.all(TAULES.map(llegirTaula));
      return new Response(JSON.stringify({ actualitzat: new Date().toISOString(), taules }), { headers: CORS });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), { status: 502, headers: CORS });
    }
  },
};
