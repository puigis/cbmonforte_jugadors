// Marcador CB Monforte: funciona sense connexió un cop s'ha obert una vegada
const C = "marcador-cbm-v1";
const FITXERS = ["./", "./index.html", "./escut.png", "./manifest.webmanifest"];
self.addEventListener("install", e => { e.waitUntil(caches.open(C).then(c => c.addAll(FITXERS))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k))))); self.clients.claim(); });
// Primer la xarxa (per tenir sempre la darrera versió); si no n'hi ha, la còpia guardada
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(fetch(e.request).then(r => { const cp = r.clone(); caches.open(C).then(c => c.put(e.request, cp)); return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match("./index.html"))));
});
