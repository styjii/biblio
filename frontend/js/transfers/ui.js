/* Envois de fichiers : panneau de progression commun à toutes les pages.
   L'envoi lui-même tourne dans un SharedWorker (voir engine.js / worker.js) : changer de dossier, lire une vidéo ou
   éditer un fichier ne l'interrompt pas. Sans SharedWorker, il tourne dans la page « hôte » (et s'arrête si on la quitte).
   Modes : 'worker' (moteur dans le SharedWorker), 'page' (moteur dans cette page, hôte), 'mirror' (cette page affiche l'envoi
   d'une autre page hôte, relayé par BroadcastChannel). Dans tous les cas, TOUTES les pages ouvertes affichent l'envoi en cours. */
(function () {
  var T = window.TCFG || {}, ICO = T.ico || {};
  var ACTIVE = 'bt:active';                       // localStorage : un envoi existe, les pages doivent se connecter
  var MIN = 'bt:min';                             // sessionStorage : panneau réduit dans cet onglet
  var DONE = 'bt:done';                           // sessionStorage : dernière série dont la fin a déjà été traitée
  var mode = '', port = null, engine = null, view = null, clients = 1;
  var bc = null, lastSeen = 0, mirrorTimer = 0;      // canal entre onglets (modes 'page' et 'mirror')
  try { if (window.BroadcastChannel) bc = new BroadcastChannel('biblio-transfers'); } catch (e) {}
  var built = false, pending = null, failed = false, pingTimer = 0, needRefresh = false, seen = false;
  var el = {};

  function $(id) { return document.getElementById(id); }
  function store(area, k, v) { try { window[area].setItem(k, v); } catch (e) {} }
  function load(area, k) { try { return window[area].getItem(k); } catch (e) { return null; } }
  function fmtB(n) {
    var u = ['o', 'Ko', 'Mo', 'Go'], i = 0;
    while (n >= 1024 && i < 3) { n /= 1024; i++; }
    return (i ? n.toFixed(n >= 100 ? 0 : 1) : n) + ' ' + u[i];
  }
  function plural(n, one, many) { return n + ' ' + (n > 1 ? many : one); }

  /* ----- transport : SharedWorker, sinon moteur dans la page ----- */
  function post(msg) {
    if (mode === 'worker' && port) port.postMessage(msg);
    else if (mode === 'mirror' && bc) bc.postMessage(msg);          // l'hôte exécute la commande
  }
  function command(cmd) {                                          // 'cancel' | 'clear'
    if (mode === 'page' && engine) engine[cmd](); else post({cmd: cmd});
  }
  function useEngine(cb) {
    mode = 'page';
    var s = document.createElement('script');
    s.src = '/static/transfer-engine.js?v=' + (T.v || '');
    s.onload = function () {
      engine = TransferEngine(onView);
      if (bc) setInterval(function () {                          // signe de vie pour les pages qui affichent cet envoi
        if (view && view.count) bc.postMessage({type: 'state', view: view});
      }, 2000);
      if (cb) cb();
    };
    s.onerror = function () { mode = ''; failed = true; alert("L'envoi de fichiers n'est pas disponible dans ce navigateur."); };
    document.head.appendChild(s);
  }
  // Sans SharedWorker, une autre page porte peut-être déjà l'envoi : on l'affiche (et on peut l'arrêter) sans le porter.
  function mirror() {
    if (!bc) return;
    mode = 'mirror'; lastSeen = Date.now();
    post({cmd: 'hello'});
    mirrorTimer = setInterval(function () {
      if (Date.now() - lastSeen < 7000) return;                  // l'hôte a disparu : plus rien à afficher
      clearInterval(mirrorTimer); mode = ''; onView({count: 0});
    }, 2000);
  }
  function connect(cb, passive) {
    if (mode) { if (cb) cb(); return; }
    if (passive && (!window.SharedWorker || failed)) { mirror(); return; }
    if (window.SharedWorker && !failed) {
      try {
        var started = false;
        var w = new SharedWorker('/static/upload-worker.js?v=' + (T.v || ''), 'biblio-transfers-' + (T.v || ''));
        w.onerror = function () {                 // script introuvable ou refusé : on se rabat sur la page
          if (started) return;
          failed = true; mode = ''; port = null;
          if (passive) { mirror(); return; }
          useEngine(function () { if (pending) { run(pending); } if (cb) cb(); });
        };
        port = w.port;
        port.onmessage = function (m) {
          var d = m.data || {};
          if (d.type !== 'state') return;
          started = true; pending = null; clients = d.clients || 1;
          onView(d.view);
        };
        port.start();
        mode = 'worker';
        post({cmd: 'hello'});
        pingTimer = setInterval(function () { post({cmd: 'ping'}); }, 4000);
        window.addEventListener('pagehide', function () { post({cmd: 'bye'}); });
        window.addEventListener('pageshow', function (e) { if (e.persisted) post({cmd: 'hello'}); });
        if (cb) cb();
        return;
      } catch (e) { failed = true; }
    }
    useEngine(cb);
  }
  function run(a) {                               // a : {files, rels, dest, over, max}
    if (mode === 'worker') { pending = a; post({cmd: 'add', files: a.files, rels: a.rels, dest: a.dest, over: a.over, max: a.max}); }
    else if (mode === 'mirror') post({cmd: 'add', files: a.files, rels: a.rels, dest: a.dest, over: a.over, max: a.max});
    else if (engine) engine.add(a.files, a.rels, a.dest, a.over, a.max);
  }

  /* ----- interface ----- */
  function build() {
    if (built) return;
    built = true;
    var box = document.createElement('section');
    box.id = 'tr-panel'; box.className = 'trpanel'; box.hidden = true;
    box.setAttribute('aria-label', 'Envois de fichiers');
    box.innerHTML =
      "<div class='trhead'><div class='trtitle'><b id='tr-title'></b><span class='sub' id='tr-pct'></span></div>" +
      "<button class='ibtn' id='tr-min' type='button' aria-label='Réduire le panneau des envois'>" + (ICO.minus || '–') + "</button></div>" +
      "<div class='upbar'><i id='tr-bar'></i></div>" +
      "<div class='sub' id='tr-sum'></div>" +
      "<div id='tr-list' class='uplist'></div>" +
      "<p class='sub trnote' id='tr-note' hidden></p>" +
      "<div class='trfoot'>" +
      "<button id='tr-refresh' class='pill' type='button' hidden>Actualiser la liste</button>" +
      "<button id='tr-cancel' class='pill' type='button'>Arrêter l'envoi</button>" +
      "<button id='tr-done' class='pill primary' type='button' hidden>Terminer</button></div>";
    var tab = document.createElement('button');
    tab.id = 'tr-tab'; tab.className = 'uptab'; tab.type = 'button'; tab.hidden = true;
    tab.setAttribute('aria-label', 'Afficher le panneau des envois');
    tab.innerHTML = "<span class='tricon'>" + (ICO.upload || '') + "</span><span id='tr-tabtxt'></span>";
    document.body.appendChild(box);
    document.body.appendChild(tab);
    ['title', 'pct', 'bar', 'sum', 'list', 'note', 'refresh', 'cancel', 'done', 'min', 'tab', 'tabtxt', 'panel'].forEach(function (k) {
      el[k] = $('tr-' + k);
    });
    el.min.addEventListener('click', function () { setMin(true); });
    el.tab.addEventListener('click', function () { setMin(false); });
    el.cancel.addEventListener('click', function () { command('cancel'); });
    el.done.addEventListener('click', function () {
      command('clear');
      if (needRefresh) setTimeout(function () { location.reload(); }, 150);     // la liste affichée est périmée : on la recharge
    });
    el.refresh.addEventListener('click', function () { location.reload(); });
  }
  function isMin() { return load('sessionStorage', MIN) !== '0'; }      // réduit par défaut sur les pages ouvertes en cours d'envoi
  function setMin(m) { store('sessionStorage', MIN, m ? '1' : '0'); if (view) render(view); }

  function summary(v) {
    var parts = [];
    if (v.ok) parts.push(plural(v.ok, 'fichier envoyé', 'fichiers envoyés'));
    if (v.skipped) parts.push(plural(v.skipped, 'ignoré', 'ignorés'));
    if (v.failed) parts.push(plural(v.failed, 'échec', 'échecs'));
    if (v.running && v.waiting) parts.push(v.waiting + ' en attente');
    return parts.join(' · ');
  }
  function render(v) {
    build();
    var pct = v.total ? Math.min(100, Math.floor(v.done * 100 / v.total)) : 100;
    var title = v.running ? 'Envoi en cours' : v.note === 'arrêté' ? 'Envoi arrêté' : (v.failed || v.note ? 'Envoi terminé avec des problèmes' : 'Envoi terminé');
    var hide = isMin();
    el.panel.hidden = hide;
    el.tab.hidden = !hide;
    el.tab.style.setProperty('--p', pct + '%');
    el.tabtxt.textContent = v.running ? 'Envoi ' + pct + ' %' : (v.note === 'arrêté' ? 'Envoi arrêté' : 'Envoi terminé');
    el.title.textContent = title;
    el.pct.textContent = ' · ' + pct + ' % (' + fmtB(v.done) + ' / ' + fmtB(v.total) + ')';
    el.bar.style.width = pct + '%';
    el.sum.textContent = summary(v);
    el.cancel.hidden = !v.running;
    el.done.hidden = v.running;
    var note = v.note || '';
    if (v.running && mode === 'mirror') note = "L'envoi se poursuit dans un autre onglet de la bibliothèque : garde-le ouvert.";
    else if (v.running && busy()) note = "Garde cet onglet ouvert : l'envoi continue pendant que les liens s'ouvrent dans un nouvel onglet. Il s'arrête si tu fermes cet onglet.";
    else if (v.running) note = "L'envoi continue en arrière-plan tant qu'un des onglets de la bibliothèque reste ouvert.";
    el.note.textContent = note;
    el.note.hidden = !note;
    el.refresh.hidden = !(needRefresh && !v.running);
    if (hide) return;                                // liste détaillée seulement si le panneau est visible
    var html = v.rows.map(function (r) {
      var stat = r.st === 'run' ? r.pct + ' %' : r.st === 'wait' ? 'en attente'
        : r.st === 'ok' ? "<span class='sico'>" + (ICO.check || '') + "</span>envoyé"
        : r.st === 'skip' ? 'ignoré' + (r.msg ? ' · ' + esc(r.msg) : '') : esc(r.msg || 'échec');
      var label = (r.dest ? r.dest + '/' : '') + r.name;
      return "<div class='uprow " + r.st + "'><span class='n' title='" + esc(label) + "'>" + esc(label) +
             "</span><span class='s'>" + stat + "</span></div>";
    }).join('');
    if (v.more > 0) html += "<div class='uprow'><span class='n sub'>… et " + plural(v.more, 'autre fichier', 'autres fichiers') + "</span></div>";
    el.list.innerHTML = html;
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); }

  /* ----- état reçu du moteur ----- */
  function onView(v) {
    view = v;
    if (mode === 'page' && bc) bc.postMessage({type: 'state', view: v});      // les autres onglets affichent le même état
    if (!v.count) {                                  // rien à afficher : tout a été « terminé »
      store('localStorage', ACTIVE, '');
      needRefresh = false;
      if (built) { el.panel.hidden = true; el.tab.hidden = true; }
      return;
    }
    store('localStorage', ACTIVE, '1');
    var first = !seen;
    seen = true;
    if (v.finished && load('sessionStorage', DONE) !== String(v.run)) {      // la série vient de se terminer
      store('sessionStorage', DONE, String(v.run));
      var here = window.Transfers && window.Transfers.currentFolder;
      // à l'ouverture d'une page, la liste est déjà à jour ; sinon (la fin arrive pendant qu'on la regarde) on propose de l'actualiser.
      // Pas de rechargement automatique : il détruirait le récapitulatif (le worker est arrêté quand plus aucune page n'y est connectée).
      if (!first && typeof here === 'string' && v.okDests.indexOf(here) >= 0) needRefresh = true;
    }
    render(v);
  }

  /* ----- onglet porteur -----
     Chrome détruit le worker d'envoi quand la dernière page connectée est quittée. Tant que cet onglet est le seul à
     porter l'envoi, naviguer ici l'interromprait : les liens s'ouvrent donc dans un nouvel onglet (qui se connecte au
     même worker), et on peut ensuite naviguer librement dans l'un ou l'autre. */
  function busy() { return !!(view && view.running && (mode === 'page' || (mode === 'worker' && clients <= 1))); }
  function openAside(url) { return window.open(url, '_blank', 'noopener'); }

  document.addEventListener('click', function (e) {
    if (!busy() || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a || a.origin !== location.origin || a.target === '_blank' || a.hasAttribute('download')) return;
    if (a.pathname === location.pathname && a.search === location.search) return;          // ancre de la même page
    if (/[?&]dl=1(&|$)/.test(a.search) || /^\/zip\b/.test(a.pathname)) return;             // téléchargement : la page ne change pas
    e.preventDefault();
    openAside(a.href);
  }, true);

  window.addEventListener('beforeunload', function (e) {
    if (!view || !view.running) return;
    if (mode === 'mirror' || (mode === 'worker' && clients > 1)) return;                   // un autre onglet porte ou garde l'envoi en vie
    e.preventDefault();
    e.returnValue = '';
  });

  /* ----- API pour les pages ----- */
  window.Transfers = {
    currentFolder: undefined,                        // renseigné par la page de navigation : dossier affiché
    busy: busy,                                      // vrai si changer de page ici interromprait l'envoi
    open: function (url) {                           // ouvrir une page sans interrompre l'envoi (nouvel onglet si besoin)
      if (!busy()) { location.href = url; return; }
      openAside(url);
    },
    start: function (list, dest, over, max) {
      var files = Array.prototype.slice.call(list);
      if (!files.length) return;
      var rels = files.map(function (f) { return f.webkitRelativePath || f.name; });
      store('sessionStorage', MIN, '0');             // l'envoi vient d'ici : on montre le panneau
      store('localStorage', ACTIVE, '1');
      connect(function () { run({files: files, rels: rels, dest: dest || '', over: !!over, max: max || 0}); });
    }
  };

  /* ----- canal entre onglets ----- */
  if (bc) bc.onmessage = function (ev) {
    var d = ev.data || {};
    if (mode === 'page' && engine) {                           // hôte : répond aux autres onglets
      if (d.cmd === 'hello' && view) bc.postMessage({type: 'state', view: view});
      else if (d.cmd === 'cancel') engine.cancel();
      else if (d.cmd === 'clear') engine.clear();
      else if (d.cmd === 'add') engine.add(d.files, d.rels, d.dest, d.over, d.max);
    } else if (mode === 'mirror' && d.type === 'state') {
      lastSeen = Date.now(); onView(d.view);
    }
  };
  // un autre onglet vient de démarrer un envoi : cette page, déjà ouverte, doit l'afficher aussi
  window.addEventListener('storage', function (e) {
    if (e.key === ACTIVE && e.newValue === '1' && !mode) connect(null, true);
  });

  /* ----- reconnexion : un envoi existe peut-être déjà (démarré dans une autre page ou un autre onglet) ----- */
  if (load('localStorage', ACTIVE) === '1') connect(null, true);
})();
