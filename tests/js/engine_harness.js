// Exécute frontend/js/transfers/engine.js avec un faux XMLHttpRequest / fetch et affiche le résultat de chaque scénario en JSON.
const vm = require('vm'), fs = require('fs'), path = require('path');
const code = fs.readFileSync(path.join(__dirname, '..', '..', 'frontend', 'js', 'transfers', 'engine.js'), 'utf8');
const tick = (ms) => new Promise(r => setTimeout(r, ms || 5));

function makeEngine(respond, opts) {
  opts = opts || {};
  const calls = {uploads: [], tickets: 0};
  class XHR {
    constructor() { this.upload = {}; this.h = {}; }
    open(m, u) { this.url = u; }
    setRequestHeader(k, v) { this.h[k] = v; }
    send(body) {
      this.body = body;
      calls.uploads.push({url: this.url, ticket: this.h['X-Upload-Ticket']});
      if (opts.hang) { this.hung = true; return; }
      setTimeout(() => {
        const r = respond(this.url, this.h, calls.uploads.length);
        if (r.error) return this.onerror();
        this.status = r.status || 200; this.responseText = JSON.stringify(r.json || {ok: true});
        if (this.upload.onprogress) this.upload.onprogress({lengthComputable: true, loaded: body.size});
        this.onload();
      }, 1);
    }
    abort() { setTimeout(() => this.onabort && this.onabort(), 1); }
  }
  const views = [];
  const ctx = {XMLHttpRequest: XHR, setTimeout, clearTimeout, Promise, encodeURIComponent, Date, JSON, Object, Math,
    fetch: () => { calls.tickets++; return Promise.resolve({status: 200, json: () => Promise.resolve(opts.auth ? opts.auth(calls.tickets) : {ok: true, ticket: 't' + calls.tickets, ttl: 900})}); }};
  vm.createContext(ctx);
  vm.runInContext(code + '\nthis.TransferEngine = TransferEngine;', ctx);
  const engine = ctx.TransferEngine(v => views.push(v));
  return {engine, calls, views};
}
const files = (n, size) => Array.from({length: n}, (_, i) => ({size: size || 10, name: 'f' + i}));
const names = n => Array.from({length: n}, (_, i) => 'f' + i + '.bin');
async function waitDone(e, ms) { for (let i = 0; i < (ms || 400); i++) { if (!e.engine.view().running) return; await tick(); } }
const out = {};

(async () => {
  // 1) envoi simple, un seul jeton pour toute la série
  let e = makeEngine(() => ({}));
  e.engine.add(files(3), names(3), 'dossier/sous', true, 0); await waitDone(e);
  let v = e.engine.view();
  out.simple = {ok: v.ok, failed: v.failed, finished: v.finished, tickets: e.calls.tickets, urls: e.calls.uploads.map(u => u.url), okDests: v.okDests};

  // 2) « déjà présent » (409) -> ignoré, la série continue
  e = makeEngine((u, h, n) => n === 2 ? {status: 409, json: {ok: false, error: 'existe déjà'}} : {});
  e.engine.add(files(3), names(3), '', false, 0); await waitDone(e); v = e.engine.view();
  out.deja = {ok: v.ok, skipped: v.skipped, msg: v.rows[1].msg};

  // 3) jeton expiré : un nouveau jeton est demandé et le même fichier est renvoyé
  e = makeEngine((u, h, n) => n === 1 ? {status: 403, json: {ok: false, code: 'ticket'}} : {});
  e.engine.add(files(1), names(1), '', false, 0); await waitDone(e); v = e.engine.view();
  out.jeton = {ok: v.ok, failed: v.failed, tickets: e.calls.tickets, uploads: e.calls.uploads.length, tokens: e.calls.uploads.map(u => u.ticket)};

  // 4) accès verrouillé : arrêt de la série, le reste est « non envoyé »
  e = makeEngine((u, h, n) => n === 2 ? {status: 403, json: {ok: false, code: 'locked'}} : {});
  e.engine.add(files(4), names(4), '', false, 0); await waitDone(e); v = e.engine.view();
  out.verrou = {ok: v.ok, failed: v.failed, skipped: v.skipped, uploads: e.calls.uploads.length, note: v.note, running: v.running};

  // 5) fichier trop volumineux : refusé sans être envoyé
  e = makeEngine(() => ({}));
  e.engine.add([{size: 50}, {size: 5}], ['gros.bin', 'petit.bin'], '', false, 10); await waitDone(e); v = e.engine.view();
  out.taille = {ok: v.ok, failed: v.failed, uploads: e.calls.uploads.length, msg: v.rows[0].msg};

  // 6) coupure réseau : arrêt de la série
  e = makeEngine((u, h, n) => n === 2 ? {error: true} : {});
  e.engine.add(files(4), names(4), '', false, 0); await waitDone(e); v = e.engine.view();
  out.reseau = {ok: v.ok, failed: v.failed, skipped: v.skipped, note: v.note};

  // 7) arrêt demandé pendant un envoi
  e = makeEngine(() => ({}), {hang: true});
  e.engine.add(files(3), names(3), '', false, 0); await tick(10); e.engine.cancel(); await waitDone(e); v = e.engine.view();
  out.arret = {running: v.running, note: v.note, ok: v.ok, failed: v.failed, skipped: v.skipped, msgs: v.rows.map(r => r.msg)};

  // 8) ajout pendant l'envoi (même série) puis nouvelle série après la fin
  e = makeEngine(() => ({}));
  e.engine.add(files(2), names(2), 'a', false, 0); e.engine.add(files(2), names(2), 'b', false, 0); await waitDone(e); v = e.engine.view();
  const first = {count: v.count, ok: v.ok, dests: v.okDests.sort(), run: v.run};
  e.engine.add(files(1), names(1), 'c', false, 0); await waitDone(e); v = e.engine.view();
  out.series = {first, second: {count: v.count, ok: v.ok, dests: v.okDests, run: v.run}};

  // 9) « Terminer » vide l'état, sauf pendant un envoi
  e.engine.clear(); out.clear = {count: e.engine.view().count};

  // 10) longue file : la vue reste bornée
  e = makeEngine(() => ({}), {hang: true});
  e.engine.add(files(1000), names(1000), '', false, 0); await tick(5); v = e.engine.view();
  out.longue = {count: v.count, rows: v.rows.length, more: v.more, waiting: v.waiting, firstRowRunning: v.rows[0].st};
  console.log(JSON.stringify(out));
})();
