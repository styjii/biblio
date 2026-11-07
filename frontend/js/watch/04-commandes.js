
/** Le lecteur : enchaînement des vidéos, aléatoire et répétition, clavier et touches multimédia (les boutons sont dans PlayerUI). */
class VideoPlayer {
  #order = new PlayOrder();
  #settings = new PlaybackSettings();
  #resume = new ResumeTracker();
  #ui;
  #autoNext = prefs.get('autonext', '1') !== '0';        // lecture automatique : enchaîner la vidéo suivante à la fin
  #shuffle = prefs.get('shuffle', '0') === '1';
  #pendingUrl = null;                                    // vidéo à ouvrir dès que le réseau revient
  #repeat = ['off', 'all', 'one'].includes(prefs.get('repeat', 'off')) ? prefs.get('repeat', 'off') : 'off';   // off | all | one

  constructor() {
    new PlaybackGuard();                                   // s'abonne seul aux événements de la vidéo (reprise après coupure)
    video.addEventListener('ended', () => this.#onEnded());
    this.#ui = new PlayerUI(this.#settings, this);

    document.addEventListener('keydown', (e) => this.#onKey(e));
    this.#setupMediaSession();

    if (innerWidth >= 1000) document.querySelector('.row.cur')?.scrollIntoView({block: 'nearest'});
    this.#order.restore(this.#shuffle);
    this.#renderModes();
  }

  /* ----- enchaînement ----- */
  #goto(target) {
    this.#order.save(target);
    if (window.Transfers) window.Transfers.open(items[target].u);     // pendant un envoi, nouvel onglet : l'envoi n'est pas interrompu
    else this.#navigate(items[target].u);
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
  #setupMediaSession() {
    if (!('mediaSession' in navigator)) return;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({title: document.querySelector('.vtitle')?.textContent ?? document.title});
    } catch { /* titre non affiché sur l'écran de verrouillage */ }
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
