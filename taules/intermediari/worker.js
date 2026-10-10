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

// El wifibillar respon com si la petició vingués d'un navegador
const CAPCALERES = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "ca,es;q=0.9",
  "Referer": "http://monforte.wifibillar.com/",
};

async function descarregar(n) {
  const r = await fetch(WIFIBILLAR + n, { headers: CAPCALERES, redirect: "follow" });
  return { status: r.status, html: latin1(await r.arrayBuffer()) };
}

async function llegirTaula(n) {
  const { status, html } = await descarregar(n);
  if (status >= 400 && !/TAULA:\s*\d|refrescar/i.test(html)) throw new Error("wifibillar " + status);
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
    // Diagnosi: /?prova=3 mostra el que retorna el wifibillar per a la taula 3
    const prova = new URL(request.url).searchParams.get("prova");
    if (prova) {
      const { status, html } = await descarregar(prova);
      return new Response("Estat: " + status + "\n\n" + html.slice(0, 3000), { headers: { ...CORS, "Content-Type": "text/plain; charset=utf-8" } });
    }
    try {
      const taules = await Promise.all(TAULES.map(llegirTaula));
      return new Response(JSON.stringify({ actualitzat: new Date().toISOString(), taules }), { headers: CORS });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), { status: 502, headers: CORS });
    }
  },
};
