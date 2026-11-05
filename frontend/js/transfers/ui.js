/* Envois de fichiers : panneau de progression commun à toutes les pages.
   L'envoi lui-même tourne dans un SharedWorker (voir engine.js / worker.js) : changer de dossier, lire une vidéo ou
   éditer un fichier ne l'interrompt pas. Sans SharedWorker, il tourne dans la page « hôte » (et s'arrête si on la quitte).
   Modes : 'worker' (moteur dans le SharedWorker), 'page' (moteur dans cette page, hôte), 'mirror' (cette page affiche l'envoi
   d'une autre page hôte, relayé par BroadcastChannel). Dans tous les cas, TOUTES les pages ouvertes affichent l'envoi en cours. */
(() => {
  const CONFIG = window.TCFG ?? {};
  const ICO = CONFIG.ico ?? {};
  const KEYS = {
    active: 'bt:active',          // localStorage : un envoi existe ; vaut « worker:<nom> » ou « page » : comment s'y connecter
    minimized: 'bt:min',          // sessionStorage : panneau réduit dans cet onglet
    handled: 'bt:done',           // sessionStorage : dernière série dont la fin a déjà été traitée
  };

  const storage = {
    get(area, key) { try { return window[area].getItem(key); } catch { return null; } },
    set(area, key, value) { try { window[area].setItem(key, value); } catch { /* stockage indisponible */ } },
  };
  const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;
  const escapeHtml = (text) => String(text).replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]);
  const formatBytes = (bytes) => {
    const units = ['o', 'Ko', 'Mo', 'Go'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
    return `${i ? bytes.toFixed(bytes >= 100 ? 0 : 1) : bytes} ${units[i]}`;
  };

  /** Le panneau (et sa pastille réduite) : il n'affiche que ce qu'on lui donne, sans rien savoir du transport. */
  class TransferPanel {
    #els = null;
    #handlers;

    /** @param handlers {minimize, restore, cancel, done, refresh} : actions de l'utilisateur */
    constructor(handlers) {
      this.#handlers = handlers;
    }

    #build() {
      const panel = document.createElement('section');
      panel.id = 'tr-panel';
      panel.className = 'trpanel';
      panel.hidden = true;
      panel.setAttribute('aria-label', 'Envois de fichiers');
      panel.innerHTML = `
        <div class='trhead'><div class='trtitle'><b id='tr-title'></b><span class='sub' id='tr-pct'></span></div>
          <button class='ibtn' id='tr-min' type='button' aria-label='Réduire le panneau des envois'>${ICO.minus ?? '–'}</button></div>
        <div class='upbar'><i id='tr-bar'></i></div>
        <div class='sub' id='tr-sum'></div>
        <div id='tr-list' class='uplist'></div>
        <p class='sub trnote' id='tr-note' hidden></p>
        <div class='trfoot'>
          <button id='tr-refresh' class='pill' type='button' hidden>Actualiser la liste</button>
          <button id='tr-cancel' class='pill' type='button'>Arrêter l'envoi</button>
          <button id='tr-done' class='pill primary' type='button' hidden>Terminer</button></div>`;
      const tab = document.createElement('button');
      tab.id = 'tr-tab';
      tab.className = 'uptab';
      tab.type = 'button';
      tab.hidden = true;
      tab.setAttribute('aria-label', 'Afficher le panneau des envois');
      tab.innerHTML = `<span class='tricon'>${ICO.upload ?? ''}</span><span id='tr-tabtxt'></span>`;
      document.body.append(panel, tab);

      const byId = (name) => document.getElementById(`tr-${name}`);
      this.#els = Object.fromEntries(['title', 'pct', 'bar', 'sum', 'list', 'note', 'refresh', 'cancel', 'done', 'min', 'tab', 'tabtxt', 'panel']
        .map((name) => [name, byId(name)]));
      const {min, tab: tabButton, cancel, done, refresh} = this.#els;
      min.addEventListener('click', () => this.#handlers.minimize());
      tabButton.addEventListener('click', () => this.#handlers.restore());
      cancel.addEventListener('click', () => this.#handlers.cancel());
      done.addEventListener('click', () => this.#handlers.done());
      refresh.addEventListener('click', () => this.#handlers.refresh());
    }

    hide() {
      if (!this.#els) return;
      this.#els.panel.hidden = true;
      this.#els.tab.hidden = true;
    }

    /** @param view état du moteur ; @param extra {minimized, note, canRefresh} */
    render(view, {minimized, note, canRefresh}) {
      if (!this.#els) this.#build();
      const els = this.#els;
      const pct = view.total ? Math.min(100, Math.floor(view.done * 100 / view.total)) : 100;
      const stopped = view.note === 'arrêté';
      const title = view.running ? 'Envoi en cours' : stopped ? 'Envoi arrêté' : (view.failed || view.note ? 'Envoi terminé avec des problèmes' : 'Envoi terminé');

      els.panel.hidden = minimized;
      els.tab.hidden = !minimized;
      els.tab.style.setProperty('--p', `${pct}%`);
      els.tabtxt.textContent = view.running ? `Envoi ${pct} %` : (stopped ? 'Envoi arrêté' : 'Envoi terminé');
      els.title.textContent = title;
      els.pct.textContent = ` · ${pct} % (${formatBytes(view.done)} / ${formatBytes(view.total)})`;
      els.bar.style.width = `${pct}%`;
      els.sum.textContent = this.#summary(view);
      els.cancel.hidden = !view.running;
      els.done.hidden = view.running;
      els.note.textContent = note;
      els.note.hidden = !note;
      els.refresh.hidden = !(canRefresh && !view.running);
      if (!minimized) els.list.innerHTML = this.#rows(view);       // liste détaillée seulement si le panneau est visible
    }

    #summary({ok, skipped, failed, running, waiting}) {
      return [
        ok && plural(ok, 'fichier envoyé', 'fichiers envoyés'),
        skipped && plural(skipped, 'ignoré', 'ignorés'),
        failed && plural(failed, 'échec', 'échecs'),
        running && waiting && `${waiting} en attente`,
      ].filter(Boolean).join(' · ');
    }

    #rows({rows, more}) {
      const status = ({st, pct, msg}) => ({
        run: `${pct} %`,
        wait: 'en attente',
        ok: `<span class='sico'>${ICO.check ?? ''}</span>envoyé`,
        skip: `ignoré${msg ? ` · ${escapeHtml(msg)}` : ''}`,
      })[st] ?? escapeHtml(msg || 'échec');
      const html = rows.map((row) => {
        const label = `${row.dest ? `${row.dest}/` : ''}${row.name}`;
        return `<div class='uprow ${row.st}'><span class='n' title='${escapeHtml(label)}'>${escapeHtml(label)}</span><span class='s'>${status(row)}</span></div>`;
      }).join('');
      return more > 0 ? `${html}<div class='uprow'><span class='n sub'>… et ${plural(more, 'autre fichier', 'autres fichiers')}</span></div>` : html;
    }
  }

  /** Le lien avec le moteur d'envoi (worker, page hôte ou page miroir) et l'API proposée aux pages. */
  class Transfers {
    currentFolder;                                   // renseigné par la page de navigation : dossier affiché

    #mode = '';
    #workerName = '';                                // nom du SharedWorker (unique : voir #connectWorker)
    #port = null;
    #engine = null;
    #view = null;
    #clients = 1;
    #channel = null;                                 // canal entre onglets (modes 'page' et 'mirror')
    #lastSeen = 0;
    #pending = null;                                 // dernier lot demandé, rejoué si le worker échoue au démarrage
    #whenReady = null;                               // {resolve, reject} : première réponse du worker
    #failed = false;
    #needRefresh = false;
    #seen = false;
    #panel = new TransferPanel({
      minimize: () => this.#setMinimized(true),
      restore: () => this.#setMinimized(false),
      cancel: () => this.#command('cancel'),
      done: () => {
        this.#command('clear');
        if (this.#needRefresh) setTimeout(() => location.reload(), 150);     // la liste affichée est périmée : on la recharge
      },
      refresh: () => location.reload(),
    });

    constructor() {
      try { if (window.BroadcastChannel) this.#channel = new BroadcastChannel('biblio-transfers'); } catch { /* pas de relais entre onglets */ }
      this.#listen();
      const active = storage.get('localStorage', KEYS.active);
      if (active) this.#connect({passive: true, active});                                    // un envoi existe peut-être déjà
    }

    /** Vrai si changer de page ici interromprait l'envoi (cet onglet est alors le seul à le porter). */
    busy() {
      return !!(this.#view?.running && (this.#mode === 'page' || (this.#mode === 'worker' && this.#clients <= 1)));
    }

    /** Ouvre une page sans interrompre l'envoi : dans un nouvel onglet si besoin. */
    open(url) {
      if (this.busy()) window.open(url, '_blank', 'noopener');
      else location.href = url;
    }

    async start(list, dest = '', over = false, max = 0) {
      const files = [...list];
      if (!files.length) return;
      const rels = files.map((f) => f.webkitRelativePath || f.name);
      storage.set('sessionStorage', KEYS.minimized, '0');          // l'envoi vient d'ici : on montre le panneau
      await this.#connect({active: storage.get('localStorage', KEYS.active)});
      this.#publish();                                             // les autres pages ne se connectent qu'une fois le moteur prêt
      this.#run({files, rels, dest, over: !!over, max});
    }

    /* ----- transport : SharedWorker, sinon moteur dans la page, sinon simple miroir ----- */
    #post(message) {
      if (this.#mode === 'worker') this.#port?.postMessage(message);
      else if (this.#mode === 'mirror') this.#channel?.postMessage(message);       // l'hôte exécute la commande
    }

    #command(cmd) {                                  // 'cancel' | 'clear'
      if (this.#mode === 'page') this.#engine?.[cmd]();
      else this.#post({cmd});
    }

    #run(batch) {
      const {files, rels, dest, over, max} = batch;
      if (this.#mode === 'worker') { this.#pending = batch; this.#post({cmd: 'add', files, rels, dest, over, max}); }
      else if (this.#mode === 'mirror') this.#post({cmd: 'add', files, rels, dest, over, max});
      else this.#engine?.add(files, rels, dest, over, max);
    }

    /** Comment se connecter : `active` est la valeur publiée par la page qui porte déjà l'envoi (« worker:<nom> » ou « page »). */
    async #connect({passive = false, active = ''} = {}) {
      if (this.#mode) return;
      const existingWorker = (active ?? '').startsWith('worker:') ? active.slice('worker:'.length) : '';
      if (passive && (!existingWorker || !window.SharedWorker || this.#failed)) return this.#mirror();
      if (window.SharedWorker && !this.#failed) {
        try { return await this.#connectWorker(passive, existingWorker); } catch { this.#failed = true; }
      }
      await this.#useEngine();
    }

    /** Publie comment se connecter à l'envoi en cours, pour les autres pages (et le conserve à jour). */
    #publish() {
      const active = this.#mode === 'worker' ? `worker:${this.#workerName}` : this.#mode === 'page' ? 'page' : '';
      if (active) storage.set('localStorage', KEYS.active, active);
    }

    /** Se connecte au SharedWorker. Une page qui démarre un envoi le crée sous un nom UNIQUE et attend sa première réponse avant de le
        publier : sinon une autre page déjà ouverte pourrait le créer la première, et il tournerait alors dans un autre processus du
        navigateur, incapable de lire les fichiers choisis ici (la requête d'envoi ne partirait jamais). */
    #connectWorker(passive, existingName = '') {
      const version = CONFIG.v ?? '';
      this.#workerName = existingName || `biblio-transfers-${version}-${Math.random().toString(36).slice(2, 10)}`;
      const worker = new SharedWorker(`/static/upload-worker.js?v=${version}`, this.#workerName);
      let started = false;
      const ready = new Promise((resolve, reject) => {
        this.#whenReady = {resolve, reject};
        setTimeout(() => reject(new Error('worker injoignable')), 4000);
      });
      ready.catch(() => {});                                               // une page passive n'attend pas : pas d'erreur non gérée
      worker.onerror = async () => {                 // script introuvable ou refusé : on se rabat sur la page
        if (started) return;
        this.#failed = true;
        this.#mode = '';
        this.#port = null;
        if (passive) return this.#mirror();
        await this.#useEngine();
        if (this.#pending) this.#run(this.#pending);
      };
      this.#port = worker.port;
      this.#port.onmessage = ({data = {}}) => {
        if (data.type !== 'state') return;
        started = true;
        this.#whenReady?.resolve();
        this.#pending = null;
        this.#clients = data.clients || 1;
        this.#onView(data.view);
      };
      this.#port.start();
      this.#mode = 'worker';
      this.#post({cmd: 'hello'});
      setInterval(() => this.#post({cmd: 'ping'}), 4000);
      window.addEventListener('pagehide', () => this.#post({cmd: 'bye'}));
      window.addEventListener('pageshow', (e) => { if (e.persisted) this.#post({cmd: 'hello'}); });
      return passive ? undefined : ready;                                  // une page passive n'attend pas : elle affiche ce qui arrive
    }

    /** Sans SharedWorker : le moteur tourne dans cette page (qui devient « hôte »). */
    async #useEngine() {
      this.#mode = 'page';
      try {
        await new Promise((resolve, reject) => {
          const script = document.createElement('script');
          script.src = `/static/transfer-engine.js?v=${CONFIG.v ?? ''}`;
          script.onload = resolve;
          script.onerror = reject;
          document.head.appendChild(script);
        });
      } catch {
        this.#mode = '';
        this.#failed = true;
        alert("L'envoi de fichiers n'est pas disponible dans ce navigateur.");
        return;
      }
      this.#engine = new TransferEngine((view) => this.#onView(view));
      if (this.#channel) {
        setInterval(() => {                          // signe de vie pour les pages qui affichent cet envoi
          if (this.#view?.count) this.#channel.postMessage({type: 'state', view: this.#view});
        }, 2000);
      }
    }

    /** Sans SharedWorker, une autre page porte peut-être déjà l'envoi : on l'affiche (et on peut l'arrêter) sans le porter. */
    #mirror() {
      if (!this.#channel) return;
      this.#mode = 'mirror';
      this.#lastSeen = Date.now();
      this.#post({cmd: 'hello'});
      const timer = setInterval(() => {
        if (Date.now() - this.#lastSeen < 7000) return;              // l'hôte a disparu : plus rien à afficher
        clearInterval(timer);
        this.#mode = '';
        this.#onView({count: 0});
      }, 2000);
    }

    /* ----- état reçu du moteur ----- */
    #onView(view) {
      this.#view = view;
      if (this.#mode === 'page') this.#channel?.postMessage({type: 'state', view});      // les autres onglets affichent le même état
      if (!view.count) {                             // rien à afficher : tout a été « terminé »
        storage.set('localStorage', KEYS.active, '');
        this.#needRefresh = false;
        this.#panel.hide();
        return;
      }
      this.#publish();
      const first = !this.#seen;
      this.#seen = true;
      if (view.finished && storage.get('sessionStorage', KEYS.handled) !== String(view.run)) {      // la série vient de se terminer
        storage.set('sessionStorage', KEYS.handled, String(view.run));
        // À l'ouverture d'une page, la liste est déjà à jour ; sinon (la fin arrive pendant qu'on la regarde) on propose de l'actualiser.
        // Pas de rechargement automatique : il détruirait le récapitulatif (le worker est arrêté quand plus aucune page n'y est connectée).
        if (!first && typeof this.currentFolder === 'string' && view.okDests.includes(this.currentFolder)) this.#needRefresh = true;
      }
      this.#render();
    }

    #isMinimized() { return storage.get('sessionStorage', KEYS.minimized) !== '0'; }     // réduit par défaut sur les pages ouvertes en cours d'envoi

    #setMinimized(minimized) {
      storage.set('sessionStorage', KEYS.minimized, minimized ? '1' : '0');
      this.#render();
    }

    #render() {
      if (!this.#view) return;
      this.#panel.render(this.#view, {minimized: this.#isMinimized(), note: this.#note(), canRefresh: this.#needRefresh});
    }

    #note() {
      const view = this.#view;
      if (view.running && this.#mode === 'mirror') return "L'envoi se poursuit dans un autre onglet de la bibliothèque : garde-le ouvert.";
      if (view.running && this.busy()) return "Garde cet onglet ouvert : l'envoi continue pendant que les liens s'ouvrent dans un nouvel onglet. Il s'arrête si tu fermes cet onglet.";
      if (view.running) return "L'envoi continue en arrière-plan tant qu'un des onglets de la bibliothèque reste ouvert.";
      return view.note || '';
    }

    /* ----- écoute : liens, fermeture de page, autres onglets ----- */
    #listen() {
      // Chrome détruit le worker d'envoi quand la dernière page connectée est quittée. Tant que cet onglet est le seul à
      // porter l'envoi, naviguer ici l'interromprait : les liens s'ouvrent donc dans un nouvel onglet (qui se connecte au
      // même worker), et on peut ensuite naviguer librement dans l'un ou l'autre.
      document.addEventListener('click', (e) => {
        if (!this.busy() || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
        const link = e.target.closest?.('a[href]');
        if (!link || link.origin !== location.origin || link.target === '_blank' || link.hasAttribute('download')) return;
        if (link.pathname === location.pathname && link.search === location.search) return;       // ancre de la même page
        if (/[?&]dl=1(&|$)/.test(link.search) || /^\/zip\b/.test(link.pathname)) return;           // téléchargement : la page ne change pas
        e.preventDefault();
        window.open(link.href, '_blank', 'noopener');
      }, true);

      window.addEventListener('beforeunload', (e) => {
        if (!this.#view?.running) return;
        if (this.#mode === 'mirror' || (this.#mode === 'worker' && this.#clients > 1)) return;   // un autre onglet porte ou garde l'envoi en vie
        e.preventDefault();
        e.returnValue = '';
      });

      if (this.#channel) {
        this.#channel.onmessage = ({data = {}}) => {
          if (this.#mode === 'page' && this.#engine) {                // hôte : répond aux autres onglets
            switch (data.cmd) {
              case 'hello': if (this.#view) this.#channel.postMessage({type: 'state', view: this.#view}); break;
              case 'cancel': this.#engine.cancel(); break;
              case 'clear': this.#engine.clear(); break;
              case 'add': this.#engine.add(data.files, data.rels, data.dest, data.over, data.max); break;
            }
          } else if (this.#mode === 'mirror' && data.type === 'state') {
            this.#lastSeen = Date.now();
            this.#onView(data.view);
          }
        };
      }

      // un autre onglet vient de démarrer un envoi : cette page, déjà ouverte, doit l'afficher aussi
      window.addEventListener('storage', ({key, newValue}) => {
        if (key === KEYS.active && newValue && !this.#mode) this.#connect({passive: true, active: newValue});
      });
    }
  }

  window.Transfers = new Transfers();
})();
