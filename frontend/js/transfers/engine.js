/* Moteur d'envoi : file d'attente séquentielle, une requête POST en flux par fichier.
   Aucun accès au DOM : il tourne dans un SharedWorker (l'envoi survit alors à la navigation d'une page à l'autre)
   ou, si le navigateur n'en a pas, directement dans la page.
   `emit(vue)` est appelé à chaque changement (progression limitée à ~7 fois par seconde). */
function TransferEngine(emit) {
  var MAX_ROWS = 200;                 // lignes envoyées aux pages (les longues files sont résumées)
  var items = [], files = {}, nextId = 1, run = 0, cursor = 0;   // cursor : tout ce qui précède est déjà traité
  var running = false, cancelled = false, xhr = null, note = '', timer = 0;
  var ticket = null, ticketAt = 0, ticketTtl = 0;

  function fmtB(n) {
    var u = ['o', 'Ko', 'Mo', 'Go'], i = 0;
    while (n >= 1024 && i < 3) { n /= 1024; i++; }
    return (i ? n.toFixed(n >= 100 ? 0 : 1) : n) + ' ' + u[i];
  }
  function push(now) {
    if (now) { clearTimeout(timer); timer = 0; emit(view()); }
    else if (!timer) timer = setTimeout(function () { timer = 0; emit(view()); }, 150);
  }

  /* ----- vue envoyée aux pages (sans les fichiers) ----- */
  function view() {
    var total = 0, done = 0, ok = 0, skipped = 0, failed = 0, waiting = 0, dests = {};
    items.forEach(function (it) {
      total += it.size;
      if (it.st === 'ok') { ok++; done += it.size; dests[it.dest] = 1; }
      else if (it.st === 'skip') { skipped++; done += it.size; }
      else if (it.st === 'bad') { failed++; done += it.size; }
      else if (it.st === 'run') done += it.loaded;
      else waiting++;
    });
    var keep = items;
    if (items.length > MAX_ROWS) {      // en cours, échecs et refus d'abord, puis le début de la file et les derniers envoyés
      var pick = {}, n = 0, i;
      for (i = 0; i < items.length && n < MAX_ROWS; i++)
        if (items[i].st === 'run' || items[i].st === 'bad' || items[i].st === 'skip') { pick[i] = 1; n++; }
      for (i = 0; i < items.length && n < MAX_ROWS - 20; i++)
        if (!pick[i] && items[i].st === 'wait') { pick[i] = 1; n++; }
      for (i = items.length - 1; i >= 0 && n < MAX_ROWS; i--)
        if (!pick[i] && items[i].st === 'ok') { pick[i] = 1; n++; }
      keep = items.filter(function (_, k) { return pick[k]; });
    }
    return {
      run: run, running: running, finished: !running && items.length > 0, note: note,
      count: items.length, total: total, done: done, ok: ok, skipped: skipped, failed: failed, waiting: waiting,
      okDests: Object.keys(dests), more: items.length - keep.length,
      rows: keep.map(function (it) {
        return {id: it.id, name: it.rel, dest: it.dest, st: it.st, size: it.size,
                pct: it.size ? Math.min(100, Math.floor(it.loaded * 100 / it.size)) : 100, msg: it.msg};
      })
    };
  }

  /* ----- jeton d'envoi (renouvelé tout seul, même si la page qui l'a demandé n'existe plus) ----- */
  function ticketValid() { return ticket && Date.now() - ticketAt < ticketTtl - 45000; }
  function getTicket() {
    return fetch('/upload-auth', {method: 'POST', headers: {'X-Requested-With': 'biblio'}, credentials: 'same-origin'})
      .then(function (r) { return r.json().then(function (j) { return {s: r.status, j: j}; }); })
      .then(function (x) {
        if (!x.j.ok) { var e = new Error(x.j.error || ('Erreur ' + x.s)); e.locked = !!x.j.locked; throw e; }
        ticket = x.j.ticket; ticketTtl = (x.j.ttl || 900) * 1000; ticketAt = Date.now();
      });
  }

  /* ----- déroulement ----- */
  function endRun(msg) {
    running = false; xhr = null; note = msg || '';
    items.forEach(function (it) {
      if (it.st === 'wait') { it.st = 'skip'; it.msg = msg === 'arrêté' ? 'annulé' : 'non envoyé'; }
    });
    files = {};
    push(true);
  }
  function stopAll(msg) { endRun(msg); }

  function step() {
    if (cancelled) return endRun('arrêté');
    var it = null;
    for (var i = cursor; i < items.length && !it; i++) {
      var c = items[i];
      if (c.st !== 'wait') { if (i === cursor) cursor++; continue; }
      if (c.max && c.size > c.max) { c.st = 'bad'; c.msg = 'trop volumineux (max ' + fmtB(c.max) + ')'; delete files[c.id]; continue; }
      it = c;
    }
    if (!it) return endRun('');
    it.st = 'run'; it.loaded = 0; it.msg = '';
    push(true);
    (ticketValid() ? Promise.resolve() : getTicket()).then(function () { send(it, false); }, function (err) {
      it.st = 'bad'; it.msg = err.locked ? 'accès verrouillé' : (err.message || 'erreur'); delete files[it.id];
      stopAll(err.locked ? 'accès verrouillé : déverrouille puis recommence' : (err.message || 'erreur'));
    });
  }

  function send(it, retried) {
    if (cancelled) { it.st = 'skip'; it.msg = 'annulé'; delete files[it.id]; return step(); }
    var x = new XMLHttpRequest();
    xhr = x;
    x.open('POST', '/upload?d=' + encodeURIComponent(it.dest) + '&n=' + encodeURIComponent(it.rel) + (it.over ? '&o=1' : ''));
    x.setRequestHeader('X-Requested-With', 'biblio');
    x.setRequestHeader('X-Upload-Ticket', ticket);
    x.setRequestHeader('Content-Type', 'application/octet-stream');
    x.upload.onprogress = function (e) { if (e.lengthComputable) { it.loaded = e.loaded; push(false); } };
    x.onload = function () {
      xhr = null;
      var j = {};
      try { j = JSON.parse(x.responseText); } catch (e) {}
      if (x.status === 200 && j.ok) { it.st = 'ok'; it.msg = ''; ticketAt = Date.now(); }
      else if (x.status === 409) { it.st = 'skip'; it.msg = j.error || 'déjà présent'; }
      else if (j.code === 'locked') {
        it.st = 'bad'; it.msg = 'accès verrouillé'; ticket = null; delete files[it.id];
        return stopAll('accès verrouillé : déverrouille puis recommence');
      }
      else if (j.code === 'ticket' && !retried) {
        ticket = null;
        return getTicket().then(function () { send(it, true); }, function (err) {
          it.st = 'bad'; it.msg = err.message || 'erreur'; delete files[it.id]; stopAll(err.message || 'erreur');
        });
      }
      else if (j.code === 'ticket') {
        it.st = 'bad'; it.msg = 'session expirée'; ticket = null; delete files[it.id];
        return stopAll("session d'envoi expirée");
      }
      else { it.st = 'bad'; it.msg = j.error || ('erreur ' + x.status); }
      delete files[it.id];
      push(true);
      step();
    };
    x.onabort = function () { xhr = null; it.st = 'bad'; it.msg = 'arrêté'; delete files[it.id]; push(true); step(); };
    x.onerror = function () { xhr = null; it.st = 'bad'; it.msg = 'échec réseau'; delete files[it.id]; stopAll('connexion perdue'); };
    x.send(files[it.id]);
  }

  /* ----- commandes ----- */
  function add(list, rels, dest, over, max) {
    if (!running && items.length) { items = []; files = {}; note = ''; cursor = 0; }      // nouvelle série : on repart de zéro
    for (var i = 0; i < list.length; i++) {
      var id = nextId++;
      items.push({id: id, rel: rels[i], dest: dest || '', over: !!over, max: max || 0, size: list[i].size,
                  st: 'wait', loaded: 0, msg: ''});
      files[id] = list[i];
    }
    if (running) return push(true);
    running = true; cancelled = false; note = ''; run++;
    push(true);
    step();
  }
  function cancel() {
    if (!running) return;
    cancelled = true;
    if (xhr) xhr.abort();
  }
  function clear() {
    if (running) return;
    items = []; files = {}; note = ''; cursor = 0;
    push(true);
  }
  return {add: add, cancel: cancel, clear: clear, view: view, fmtB: fmtB};
}
