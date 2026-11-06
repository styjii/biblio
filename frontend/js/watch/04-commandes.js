
  /** Le lecteur : enchaînement des vidéos, aléatoire et répétition, boutons, clavier et touches multimédia. */
  class VideoPlayer {
    #order = new PlayOrder();
    #settings = new PlaybackSettings();
    #resume = new ResumeTracker();
    #guard = new PlaybackGuard();
    #autoNext = $('autonext');
    #shuffle = prefs.get('shuffle', '0') === '1';
    #pendingUrl = null;                                    // vidéo à ouvrir dès que le réseau revient
    #repeat = ['off', 'all', 'one'].includes(prefs.get('repeat', 'off')) ? prefs.get('repeat', 'off') : 'off';   // off | all | one

    constructor() {
      this.#autoNext.checked = prefs.get('autonext', '1') !== '0';
      this.#autoNext.addEventListener('change', () => prefs.set('autonext', this.#autoNext.checked ? '1' : '0'));
      video.addEventListener('ended', () => this.#onEnded());

      $('w-prev').addEventListener('click', () => this.previous());
      $('w-next').addEventListener('click', () => this.next());
      $('w-back').addEventListener('click', () => seekBy(-10));
      $('w-fwd').addEventListener('click', () => seekBy(10));
      $('w-shuffle').addEventListener('click', () => this.setShuffle(!this.#shuffle));
      $('w-repeat').addEventListener('click', () => this.cycleRepeat());
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
      if (!this.#autoNext.checked) return;
      if (window.Transfers?.busy()) return say('Lecture automatique suspendue : un envoi est en cours dans cet onglet.');
      this.next(true);
    }

    /* ----- aléatoire et répétition ----- */
    setShuffle(on) {
      this.#shuffle = on;
      prefs.set('shuffle', on ? '1' : '0');
      this.#order.rebuild(on);
      this.#order.save();
      this.#renderModes();
      say(on ? 'Lecture aléatoire activée.' : "Lecture dans l'ordre.");
    }

    cycleRepeat() {
      this.#repeat = {off: 'all', all: 'one', one: 'off'}[this.#repeat];
      prefs.set('repeat', this.#repeat);
      this.#renderModes();
      say({off: 'Répétition désactivée.', all: 'Répétition de toutes les vidéos.', one: 'Répétition de la vidéo.'}[this.#repeat]);
    }

    #renderModes() {
      const shuffle = $('w-shuffle');
      const repeat = $('w-repeat');
      const label = {off: 'désactivée', all: 'toutes les vidéos', one: 'cette vidéo'}[this.#repeat];
      shuffle.classList.toggle('on', this.#shuffle);
      shuffle.setAttribute('aria-pressed', String(this.#shuffle));
      setIcon(repeat, this.#repeat === 'one' ? 'repeat1' : 'repeat');
      repeat.classList.toggle('on', this.#repeat !== 'off');
      repeat.setAttribute('aria-pressed', String(this.#repeat !== 'off'));
      repeat.setAttribute('aria-label', `Répétition : ${label}`);
      repeat.title = `Répétition (R) : ${{off: 'aucune', all: 'tout', one: 'une vidéo'}[this.#repeat]}`;
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
      const onPlayer = e.target === video;
      // le curseur de volume garde ses flèches natives
      if (e.target.id === 'w-vol' && key.startsWith('Arrow')) return;

      const actions = {
        k: () => (video.paused ? play() : video.pause()),
        j: () => seekBy(-10),
        l: () => seekBy(10),
        n: () => this.next(),
        p: () => this.previous(),
        s: () => this.setShuffle(!this.#shuffle),
        r: () => this.cycleRepeat(),
        m: () => this.#settings.toggleMute(),
        f: () => (document.fullscreenElement ? document.exitFullscreen() : video.requestFullscreen?.()),
        '<': () => this.#settings.stepRate(-1),
        ',': () => this.#settings.stepRate(-1),
        '>': () => this.#settings.stepRate(1),
        '.': () => this.#settings.stepRate(1),
      };
      // flèches et espace : le lecteur natif les gère déjà quand il a le focus
      if (!onPlayer) {
        Object.assign(actions, {
          ' ': actions.k,
          ArrowLeft: () => seekBy(-5),
          ArrowRight: () => seekBy(5),
          ArrowUp: () => this.#settings.setVolume(this.#settings.volume + 0.05),
          ArrowDown: () => this.#settings.setVolume(this.#settings.volume - 0.05),
        });
      }
      const action = actions[key] ?? actions[lower];
      if (!action) return;
      action();
      e.preventDefault();
    }

    /** Touches multimédia du téléphone / du clavier et écran de verrouillage. */
    #setupMediaSession() {
      if (!('mediaSession' in navigator)) return;
      const handlers = {
        previoustrack: () => this.previous(),
        nexttrack: () => this.next(),
        seekbackward: ({seekOffset} = {}) => seekBy(-(seekOffset || 10)),
        seekforward: ({seekOffset} = {}) => seekBy(seekOffset || 10),
      };
      for (const [name, handler] of Object.entries(handlers)) {
        try { navigator.mediaSession.setActionHandler(name, handler); } catch { /* action non prise en charge */ }
      }
    }
  }

  new VideoPlayer();
})();
