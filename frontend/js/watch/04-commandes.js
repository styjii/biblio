
/** Le lecteur : enchaînement des vidéos, aléatoire et répétition, clavier et touches multimédia (les boutons sont dans PlayerUI). */
class VideoPlayer {
  static FIXED_MOBILE = matchMedia('(max-width:999px) and (min-height:501px)');      // mobile à lecteur fixe : même condition que le CSS du « dock » (07-page-de-lecture-video.css)

  #order = new PlayOrder();
  #settings = new PlaybackSettings();
  #resume = new ResumeTracker();
  #ui;
  #guard;
  #switching = false;                                    // une vidéo est en train d'être chargée sur place : les clics suivants sont ignorés
  #historyBound = false;
  #autoNext = prefs.get('autonext', '1') !== '0';        // lecture automatique : enchaîner la vidéo suivante à la fin
  #shuffle = prefs.get('shuffle', '0') === '1';
  #pendingUrl = null;                                    // vidéo à ouvrir dès que le réseau revient
  #repeat = ['off', 'all', 'one'].includes(prefs.get('repeat', 'off')) ? prefs.get('repeat', 'off') : 'off';   // off | all | one

  constructor() {
    this.#guard = new PlaybackGuard();                     // s'abonne seul aux événements de la vidéo (reprise après coupure)
    video.addEventListener('ended', () => this.#onEnded());
    this.#ui = new PlayerUI(this.#settings, this);

    document.addEventListener('keydown', (e) => this.#onKey(e));
    this.#setupMediaSession();

    const list = this.#listMode();
    if (list === 'aside') document.querySelector('.row.cur')?.scrollIntoView({block: 'nearest'});
    else if (list === 'fixed') requestAnimationFrame(() => this.#revealCurrent(false));      // la liste défile sous le lecteur fixe : la vidéo en cours doit y être visible
    this.#order.restore(this.#shuffle);
    this.#renderModes();
  }

  /* ----- enchaînement ----- */
  /** Le plein écran est-il actif ? (API standard, préfixe WebKit, ou plein écran natif du lecteur d'iOS) */
  #isFullscreen() {
    return Boolean(document.fullscreenElement || document.webkitFullscreenElement || video.webkitDisplayingFullscreen);
  }

  #goto(target) {
    if (this.#switching) return;
    this.#order.save(target);
    if (!this.#isFullscreen()) return this.#leaveTo(target);
    // Plein écran : ouvrir une autre page le fermerait, et le navigateur interdit de le rouvrir sans geste de l'utilisateur.
    // La vidéo suivante est donc chargée dans le même lecteur, qui reste en plein écran. En cas d'échec : navigation classique.
    this.#switching = true;
    this.#loadInPlace(target).catch(() => this.#leaveTo(target)).finally(() => { this.#switching = false; });
  }

  #leaveTo(target) {
    if (window.Transfers) window.Transfers.open(items[target].u);     // pendant un envoi, nouvel onglet : l'envoi n'est pas interrompu
    else this.#navigate(items[target].u);
  }

  /** Charge une autre vidéo sans changer de page : on lit d'abord sa page (titre, sous-titres, adresse du fichier), puis on remplace
      la source du lecteur. Tant que la page n'est pas reçue et vérifiée, rien n'est modifié (l'échec se rattrape par une navigation). */
  async #loadInPlace(target) {
    const item = items[target];
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    let html;
    try {
      const response = await fetch(item.u, {credentials: 'same-origin', signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      html = await response.text();
    } finally {
      clearTimeout(timeout);
    }
    const page = new DOMParser().parseFromString(html, 'text/html');
    const source = page.getElementById('player')?.getAttribute('src');
    const fresh = JSON.parse(html.match(/window\.WCFG = (\{.*?\}); window\.WICO/s)?.[1] ?? 'null');
    if (!source || fresh?.items?.[fresh.index]?.f !== item.f) throw new Error('page inattendue');   // page de connexion, dossier modifié…

    this.#resume.leave();                                  // position de la vidéo qu'on quitte, avant tout changement
    index = fresh.index;
    cfg.key = fresh.key;
    cfg.download = fresh.download;
    this.#applyPage(page);
    this.#guard.reset();
    this.#resume.reset();
    this.#order.restore(this.#shuffle);                    // l'ordre (dans l'ordre ou mélangé) se poursuit depuis la nouvelle vidéo
    video.src = source;                                    // le plein écran reste sur le même élément : il n'est jamais fermé
    this.#ui.reload();
    play();
    history.pushState(null, '', item.u);                   // l'adresse de la page suit la vidéo (partage, rechargement)
    if (!this.#historyBound) {
      this.#historyBound = true;
      window.addEventListener('popstate', () => location.reload());       // « précédent » du navigateur : on recharge la vidéo de l'adresse
    }
  }

  /** Reporte sur la page ouverte ce qui change d'une vidéo à l'autre : titre, informations, sous-titres, vidéo en cours dans la liste. */
  #applyPage(page) {
    video.querySelectorAll('track').forEach((track) => track.remove());
    for (const track of page.querySelectorAll('#player track')) video.append(document.importNode(track, true));
    const title = page.querySelector('.vtitle')?.textContent ?? '';
    document.querySelector('.vtitle').textContent = title;
    document.querySelector('.vp-top').textContent = title;
    document.querySelector('.chips').innerHTML = page.querySelector('.chips')?.innerHTML ?? '';
    document.title = page.title;
    const current = page.querySelector('.list .row.cur')?.dataset.f;
    document.querySelectorAll('.list .row').forEach((row) => row.classList.toggle('cur', row.dataset.f === current));
    const list = this.#listMode();
    if (list === 'fixed') this.#revealCurrent(!this.#isFullscreen());
    else if (list === 'aside') document.querySelector('.list .row.cur')?.scrollIntoView({block: 'nearest'});
    this.#updateMediaTitle(title);
  }

  /** Où est la liste, et doit-elle suivre la vidéo en cours ?
      - 'fixed'  : mobile à lecteur fixe, la liste est celle de la page : on amène la ligne en cours sous le lecteur (#revealCurrent) ;
      - 'aside'  : PC, liste dans son volet à droite (défilement propre) : la ligne en cours y est ramenée en vue ;
      - 'static' : lecteur non fixé et liste dans la page (mode cinéma, mobile en paysage bas) : aucun défilement automatique, la page reste où
                   l'on est (sinon elle quitterait le lecteur pour descendre à la ligne en cours) ; la ligne en cours reste surlignée. */
  #listMode() {
    if (VideoPlayer.FIXED_MOBILE.matches) return 'fixed';
    if (innerWidth >= 1000 && !$('watch')?.classList.contains('theater')) return 'aside';
    return 'static';
  }

  /** Mobile à lecteur fixe : la liste est celle de la page, qui défile sous le lecteur et ses informations (collés en haut). `scrollIntoView` ne tient pas
      compte de ce bloc et laisserait la vidéo en cours cachée dessous : on amène donc la ligne juste sous lui, si elle n'est pas déjà visible,
      et on la fait clignoter un instant (la vidéo en cours est toujours surlignée par la classe « cur »). */
  #revealCurrent(smooth) {
    const row = document.querySelector('.list .row.cur');
    const dock = $('dock');
    if (!row || !dock) return;
    const limit = dock.getBoundingClientRect().bottom + 8;                  // le haut de la zone visible de la liste
    const rect = row.getBoundingClientRect();
    if (rect.top < limit || rect.bottom > innerHeight) {
      const calm = matchMedia('(prefers-reduced-motion:reduce)').matches;
      scrollBy({top: rect.top - limit, behavior: smooth && !calm ? 'smooth' : 'auto'});
    }
    row.classList.remove('flash');
    void row.offsetWidth;                                                   // relance l'animation même si la classe était déjà posée
    row.classList.add('flash');
  }

  /** Ouvre la page d'une vidéo ; hors connexion, attend le retour du réseau (sinon le navigateur afficherait sa page d'erreur et la liste de lecture serait perdue). */
  #navigate(url) {
    if (navigator.onLine !== false) { location.href = url; return; }
    say('Hors connexion : la vidéo suivante démarrera au retour du réseau.');
    if (!this.#pendingUrl) window.addEventListener('online', () => { const target = this.#pendingUrl; this.#pendingUrl = null; if (target) location.href = target; }, {once: true});
    this.#pendingUrl = url;
  }

  /** Vidéo suivante ; `auto` : fin de lecture (et non une demande de l'utilisateur). */
  next(auto = false) {
    if (this.#order.next !== undefined) return this.#goto(this.#order.next);
    if (this.#repeat === 'all' || (!auto && this.#order.count > 1)) return this.#goto(this.#order.wrap(this.#shuffle));
    if (!auto) { video.currentTime = 0; return play(); }              // une seule vidéo : « suivante » la relance
    say('Fin de la liste.');
  }

  previous() {
    if (video.currentTime > 3) { video.currentTime = 0; return; }
    if (this.#order.previous !== undefined) return this.#goto(this.#order.previous);
    if (this.#order.count > 1) return this.#goto(this.#order.last);
    video.currentTime = 0;
  }

  #onEnded() {
    this.#resume.finish();
    if (this.#repeat === 'one') { video.currentTime = 0; return play(); }      // (repli : la boucle native s'en charge déjà)
    if (!this.#autoNext) return;
    if (window.Transfers?.busy()) return say('Lecture automatique suspendue : un envoi est en cours dans cet onglet.');
    this.next(true);
  }

  /* ----- lecture automatique, aléatoire et répétition (réglages lus et modifiés par PlayerUI) ----- */
  get autoNext() { return this.#autoNext; }
  get shuffle() { return this.#shuffle; }
  get repeat() { return this.#repeat; }

  setAutoNext(on) {
    this.#autoNext = on;
    prefs.set('autonext', on ? '1' : '0');
    say(on ? 'Lecture automatique activée.' : 'Lecture automatique désactivée.');
  }

  setShuffle(on) {
    this.#shuffle = on;
    prefs.set('shuffle', on ? '1' : '0');
    this.#order.rebuild(on);
    this.#order.save();
    this.#renderModes();
    say(on ? 'Lecture aléatoire activée.' : "Lecture dans l'ordre.");
  }

  cycleRepeat() { this.setRepeat({off: 'all', all: 'one', one: 'off'}[this.#repeat]); }

  setRepeat(mode) {
    this.#repeat = mode;
    prefs.set('repeat', mode);
    this.#renderModes();
    say({off: 'Répétition désactivée.', all: 'Répétition de toutes les vidéos.', one: 'Répétition de la vidéo.'}[mode]);
  }

  #renderModes() {
    this.#ui.renderModes({shuffle: this.#shuffle, repeat: this.#repeat});
    video.loop = this.#repeat === 'one';
  }

  /* ----- clavier ----- */
  #onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const tag = (e.target.tagName || '').toLowerCase();
    const type = (e.target.type || '').toLowerCase();
    if (tag === 'textarea' || (tag === 'input' && type !== 'range')) return;
    const {key} = e;
    const lower = key.toLowerCase();
    if (tag === 'button' && (key === ' ' || key === 'Enter')) return;
    if (e.target.closest?.('.vp-menu')) return;            // dans le menu des paramètres, les flèches parcourent les choix
    // le curseur de volume garde ses flèches natives
    if (e.target.id === 'vp-vol' && key.startsWith('Arrow')) return;

    const volume = (delta) => { this.#settings.setVolume(this.#settings.volume + delta); this.#ui.peekVolume(); };
    const actions = {
      k: () => this.#ui.toggle(),
      ' ': () => this.#ui.toggle(),
      j: () => this.#ui.skip(-10),
      l: () => this.#ui.skip(10),
      ArrowLeft: () => this.#ui.skip(-5),
      ArrowRight: () => this.#ui.skip(5),
      ArrowUp: () => volume(0.05),
      ArrowDown: () => volume(-0.05),
      Home: () => this.#ui.jumpTo(0),
      n: () => this.next(),
      p: () => this.previous(),
      s: () => this.setShuffle(!this.#shuffle),
      r: () => this.cycleRepeat(),
      m: () => { this.#settings.toggleMute(); this.#ui.peekVolume(); },
      f: () => this.#ui.toggleFullscreen(),
      t: () => this.#ui.toggleTheater(),
      i: () => this.#ui.togglePip(),
      c: () => this.#ui.toggleCaptions(),
      '<': () => this.#settings.stepRate(-1),
      ',': () => this.#settings.stepRate(-1),
      '>': () => this.#settings.stepRate(1),
      '.': () => this.#settings.stepRate(1),
    };
    for (let digit = 0; digit <= 9; digit++) actions[String(digit)] = () => this.#ui.jumpTo(digit / 10);     // 0 à 9 : 0 % à 90 % de la vidéo
    const action = actions[key] ?? actions[lower];
    if (!action) return;
    action();
    e.preventDefault();
  }

  /** Touches multimédia du téléphone / du clavier et écran de verrouillage. */
  #updateMediaTitle(title) {
    if (!('mediaSession' in navigator)) return;
    try { navigator.mediaSession.metadata = new MediaMetadata({title}); } catch { /* titre non affiché sur l'écran de verrouillage */ }
  }

  #setupMediaSession() {
    if (!('mediaSession' in navigator)) return;
    this.#updateMediaTitle(document.querySelector('.vtitle')?.textContent ?? document.title);
    const handlers = {
      previoustrack: () => this.previous(),
      nexttrack: () => this.next(),
      seekbackward: ({seekOffset} = {}) => this.#ui.skip(-(seekOffset || 10)),
      seekforward: ({seekOffset} = {}) => this.#ui.skip(seekOffset || 10),
    };
    for (const [name, handler] of Object.entries(handlers)) {
      try { navigator.mediaSession.setActionHandler(name, handler); } catch { /* action non prise en charge */ }
    }
  }
}

new VideoPlayer();
