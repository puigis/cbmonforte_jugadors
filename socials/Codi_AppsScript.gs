// Socials CB Monforte · servidor al full de Google
// 1. Canvia la clau de la junta aquí sota (és la que posareu al mòbil per poder anotar resultats).
const CLAU = 'CANVIA-AQUESTA-CLAU';

function doGet(e) {
  const files = full().getDataRange().getValues();
  const socials = {};
  files.slice(1).forEach(f => { if (f[0]) socials[f[0]] = JSON.parse(f[1]); });
  return json({ ok: true, socials: socials });
}

function doPost(e) {
  const b = JSON.parse(e.postData.contents);
  if (b.clau !== CLAU) return json({ ok: false, error: 'clau' });
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const sh = full();
    const files = sh.getDataRange().getValues();
    let fila = -1;
    for (let i = 1; i < files.length; i++) if (files[i][0] === b.id) { fila = i + 1; break; }

    if (b.accio === 'esborrar') {
      if (fila > 0) sh.deleteRow(fila);
      return json({ ok: true });
    }

    let doc;
    if (b.accio === 'desar') {
      doc = b.doc;
    } else if (b.accio === 'patch') {
      if (fila < 0) return json({ ok: false, error: 'no existeix' });
      doc = JSON.parse(files[fila - 1][1]);
      (b.del || []).forEach(p => posa(doc, p, null));
      posa(doc, b.path, b.value);
    } else {
      return json({ ok: false, error: 'accio' });
    }

    const text = JSON.stringify(doc);
    if (fila > 0) sh.getRange(fila, 2, 1, 2).setValues([[text, new Date()]]);
    else sh.appendRow([b.id, text, new Date()]);
    return json({ ok: true, doc: doc });
  } finally {
    lock.releaseLock();
  }
}

function posa(doc, path, value) {
  let o = doc;
  for (let i = 0; i < path.length - 1; i++) {
    if (o[path[i]] == null) o[path[i]] = {};
    o = o[path[i]];
  }
  const k = path[path.length - 1];
  if (value === null) delete o[k]; else o[k] = value;
}

function full() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName('socials');
  if (!sh) { sh = ss.insertSheet('socials'); sh.appendRow(['id', 'dades', 'actualitzat']); }
  return sh;
}

function json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
