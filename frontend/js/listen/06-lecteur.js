
/** Le lecteur : lecture, enchaînement des pistes, aléatoire et répétition, volume, vitesse, boutons, clavier et touches multimédia. */
class AudioPlayer {
  #view = new PlayerView();
  #info = new TrackInfo();
  #list = new TrackList(this.#info, (index) => this.playIndex(index));
  #order = new PlayOrder();
  #position = new PositionKeeper();
  #seek = $('l-seek');
  #index = cfg.start;
  #shuffle = prefs.get('shuffle', '0') === '1';
  #repeat = ['off', 'all', 'one'].includes(prefs.get('repeat', 'off')) ? prefs.get('repeat', 'off') : 'off';   // off | all | one
  #rate = RATES.includes(parseFloat(prefs.get('rate', '1'))) ? parseFloat(prefs.get('rate', '1')) : 1;
  #errorRun = 0;                                           // pistes illisibles d'affilée
  #errorTimer = 0;

  constructor() {
    let volume = parseFloat(prefs.get('vol', '1'));
    if (!(volume >= 0 && volume <= 1)) volume = 1;
    audio.volume = volume;
    audio.muted = prefs.get('muted', '0') === '1';

    this.#bindAudioEvents();
    this.#bindControls();
    this.#bindKeyboard();
    this.#bindMediaSession();
    window.addEventListener('pagehide', () => this.#position.save(true));
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') this.#position.save(true); });

    this.#order.rebuild(this.#shuffle, this.#index);
    this.#renderAll();
    this.start(this.#index, true);
  }

  #renderAll() {
    this.#renderPlay();
    this.#view.renderModes(this.#shuffle, this.#repeat);
    this.#view.renderVolume();
    this.#view.renderRate(this.#rate);
    this.#view.renderSeek();
  }

  #renderPlay() {
    const playing = !audio.paused;
    this.#view.renderPlay(playing);
    this.#list.setPlaying(!audio.paused && !audio.ended);
  }

  play() {
    audio.play()?.catch((error) => {
      if (error?.name === 'AbortError') return;                  // lecture interrompue par un changement de piste
      this.#view.loading = false;
      this.#renderPlay();
      if (error?.name === 'NotAllowedError') say('Appuie sur lecture pour démarrer.', true);
    });
  }

  toggle() { if (audio.paused) this.play(); else audio.pause(); }

  seekBy(seconds) {
    if (!Number.isFinite(audio.duration)) return;
    audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + seconds));
  }

  /* ----- lecture et enchaînement ----- */
  start(index, wantPlay) {
    clearTimeout(this.#errorTimer);
    this.#index = index;
    const track = tracks[index];
    $('l-count').textContent = `Piste ${index + 1} sur ${tracks.length}`;
    $('l-dl').href = `/raw?dl=1&f=${track.q}`;
    try { history.replaceState(null, '', `/listen?f=${track.q}`); } catch { /* adresse inchangée */ }
    this.#view.applyTitle(null, index);
    this.#view.setCover(null, index);
    this.#showInfo(index);
    this.#position.begin(index);                                 // la piste quittée est mémorisée avant de charger la suivante, dont on cherche la position à reprendre
    audio.src = `/raw?f=${track.q}`;
    audio.defaultPlaybackRate = audio.playbackRate = this.#rate;
    say('');
    this.#list.markCurrent(index, false);
    this.#list.reveal(index);
    this.#view.loading = !!wantPlay;
    if (wantPlay) this.play();
    this.#view.renderSeek();
    this.#renderPlay();
  }

  /** Titre, pochette et durée de la piste, dès que le serveur les a fournis. */
  async #showInfo(index) {
    const info = await this.#info.get(index);
    if (index !== this.#index) return;                           // une autre piste a été choisie entre-temps
    this.#view.applyTitle(info, index);
    this.#view.setCover(info, index);
    this.#list.showDuration(index, info?.duration);
  }

  /** Clic sur une piste de la liste. La piste déjà chargée n'est pas rechargée (elle repartirait du début) : si elle est en pause, on la relance. */
  playIndex(index) {
    if (index === this.#index && audio.src && !audio.error) {
      if (audio.paused) this.play();
      return;
    }
    this.#order.rebuild(this.#shuffle, index);
    this.start(index, true);
  }

  /** Piste suivante ; `auto` : fin de lecture (et non une demande de l'utilisateur). */
  next(auto = false) {
    if (this.#order.hasNext) return this.start(this.#order.advance(), true);
    if (this.#repeat === 'all' || (!auto && this.#order.count > 1)) return this.start(this.#order.wrap(this.#shuffle, this.#index), true);
    if (!auto) { audio.currentTime = 0; return this.play(); }    // une seule piste : « suivant » la relance
    audio.pause();
    audio.currentTime = 0;
    this.#renderPlay();
    say('Fin de la liste.');
  }

  previous() {
    if (audio.currentTime > 3) { audio.currentTime = 0; return; }
    if (this.#order.hasPrevious) return this.start(this.#order.retreat(), true);
    if (this.#order.count > 1) return this.start(this.#order.jumpToLast(), true);
    audio.currentTime = 0;
  }

  /* ----- aléatoire, répétition, volume, vitesse ----- */
  setShuffle(on) {
    this.#shuffle = on;
    prefs.set('shuffle', on ? '1' : '0');
    this.#order.rebuild(on, this.#index);
    this.#view.renderModes(this.#shuffle, this.#repeat);
    say(on ? 'Lecture aléatoire activée.' : "Lecture dans l'ordre.");
  }

  cycleRepeat() {
    this.#repeat = {off: 'all', all: 'one', one: 'off'}[this.#repeat];
    prefs.set('repeat', this.#repeat);
    this.#view.renderModes(this.#shuffle, this.#repeat);
    say({off: 'Répétition désactivée.', all: 'Répétition de toutes les pistes.', one: 'Répétition de la piste.'}[this.#repeat]);
  }

  setVolume(volume) {
    volume = Math.max(0, Math.min(1, volume));
    audio.volume = volume;
    if (volume > 0) audio.muted = false;
    prefs.set('vol', volume);
    prefs.set('muted', '0');
  }

  toggleMute() {
    audio.muted = !audio.muted;
    prefs.set('muted', audio.muted ? '1' : '0');
  }

  setRate(rate) {
    this.#rate = rate;
    audio.defaultPlaybackRate = audio.playbackRate = rate;
    prefs.set('rate', rate);
    this.#view.renderRate(rate);
    say(`Vitesse : ${String(rate).replace('.', ',')}×`);
  }

  stepRate(direction) {
    this.setRate(RATES[Math.max(0, Math.min(RATES.length - 1, RATES.indexOf(this.#rate) + direction))]);
  }

  /* ----- événements du lecteur audio ----- */
  #updatePositionState() {
    if (!('mediaSession' in navigator) || !navigator.mediaSession.setPositionState || !Number.isFinite(audio.duration)) return;
    try {
      navigator.mediaSession.setPositionState({
        duration: audio.duration, playbackRate: audio.playbackRate, position: Math.min(audio.currentTime, audio.duration),
      });
    } catch { /* position non transmise à l'écran de verrouillage */ }
  }

  #setPlaybackState(state) {
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = state;
  }

  #bindAudioEvents() {
    const view = this.#view;
    const loaded = () => { view.loading = false; this.#renderPlay(); this.#position.confirm(); };
    audio.addEventListener('loadedmetadata', () => {
      this.#errorRun = 0;
      this.#list.showDuration(this.#index, audio.duration);
      this.#position.onMetadata();
      view.renderSeek();
      this.#updatePositionState();
    });
    audio.addEventListener('durationchange', () => view.renderSeek());
    audio.addEventListener('progress', () => view.renderSeek());
    audio.addEventListener('timeupdate', () => { view.renderSeek(); this.#position.tick(); });
    audio.addEventListener('waiting', () => { if (!audio.paused) { view.loading = true; this.#renderPlay(); } });
    audio.addEventListener('canplay', loaded);
    audio.addEventListener('playing', loaded);
    audio.addEventListener('play', () => { this.#renderPlay(); this.#setPlaybackState('playing'); });
    audio.addEventListener('pause', () => {
      loaded();
      this.#setPlaybackState('paused');
      this.#position.save();
    });
    audio.addEventListener('ended', () => {
      this.#position.finish();
      if (this.#repeat === 'one') { audio.currentTime = 0; this.play(); return; }
      this.next(true);
    });
    audio.addEventListener('error', () => this.#onError());
    audio.addEventListener('volumechange', () => view.renderVolume());
    audio.addEventListener('ratechange', () => this.#updatePositionState());
    audio.addEventListener('seeked', () => { view.renderSeek(); this.#updatePositionState(); });
  }

  /** Piste illisible : on le dit, et on passe à la suivante si possible. */
  #onError() {
    this.#view.loading = false;
    const reason = {2: 'Erreur réseau', 3: 'Fichier audio endommagé', 4: 'Format non pris en charge'}[audio.error?.code] ?? 'Lecture impossible';
    this.#list.markBad(this.#index);
    this.#errorRun++;
    const canSkip = this.#order.count > 1 && this.#errorRun < this.#order.count && (this.#order.hasNext || this.#repeat === 'all');
    say(`${reason} : ${tracks[this.#index].n}${canSkip ? ' — passage à la piste suivante…' : ''}`, true);
    this.#renderPlay();
    if (canSkip) {
      clearTimeout(this.#errorTimer);
      this.#errorTimer = setTimeout(() => this.next(true), 1400);
    }
  }

  /* ----- boutons ----- */
  #bindControls() {
    const seek = this.#seek;
    const view = this.#view;
    seek.addEventListener('input', () => { view.seeking = true; view.renderSeek(); });
    seek.addEventListener('change', () => {
      if (Number.isFinite(audio.duration)) audio.currentTime = seek.value / 1000 * audio.duration;
      view.seeking = false;
      view.renderSeek();
      seek.blur();
    });
    seek.addEventListener('pointercancel', () => { view.seeking = false; view.renderSeek(); });
    $('l-vol').addEventListener('input', ({target}) => this.setVolume(target.value / 100));
    $('l-vol').addEventListener('change', ({target}) => target.blur());
    $('b-play').addEventListener('click', () => this.toggle());
    $('b-next').addEventListener('click', () => this.next());
    $('b-prev').addEventListener('click', () => this.previous());
    $('b-back').addEventListener('click', () => this.seekBy(-10));
    $('b-fwd').addEventListener('click', () => this.seekBy(10));
    $('b-shuffle').addEventListener('click', () => this.setShuffle(!this.#shuffle));
    $('b-repeat').addEventListener('click', () => this.cycleRepeat());
    $('b-mute').addEventListener('click', () => this.toggleMute());
    $('b-rate').addEventListener('click', () => this.setRate(RATES[(RATES.indexOf(this.#rate) + 1) % RATES.length]));
  }

  /* ----- clavier ----- */
  #bindKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const tag = (e.target.tagName || '').toLowerCase();
      const type = (e.target.type || '').toLowerCase();
      const {key} = e;
      const lower = key.toLowerCase();
      if (tag === 'textarea' || (tag === 'input' && type !== 'range' && type !== 'checkbox')) {
        if (key === 'Escape') {
          if (e.target.id === 'l-filter') { e.target.value = ''; this.#list.applyFilter(); }
          e.target.blur();
        }
        return;
      }
      if (tag === 'button' && (key === ' ' || key === 'Enter')) return;
      // le curseur de volume garde ses flèches natives ; sur le curseur de position, elles avancent de 5 s
      if (e.target.id === 'l-vol' && key.startsWith('Arrow')) return;

      const volume = audio.muted ? 0 : audio.volume;
      const actions = {
        ' ': () => this.toggle(),
        k: () => this.toggle(),
        n: () => this.next(),
        p: () => this.previous(),
        s: () => this.setShuffle(!this.#shuffle),
        r: () => this.cycleRepeat(),
        m: () => this.toggleMute(),
        ArrowLeft: () => this.seekBy(-5),
        ArrowRight: () => this.seekBy(5),
        j: () => this.seekBy(-10),
        l: () => this.seekBy(10),
        ArrowUp: () => this.setVolume(volume + 0.05),
        ArrowDown: () => this.setVolume(volume - 0.05),
        '<': () => this.stepRate(-1),
        ',': () => this.stepRate(-1),
        '>': () => this.stepRate(1),
        '.': () => this.stepRate(1),
        '/': () => $('l-filter').focus(),
      };
      let action = actions[key] ?? actions[lower];
      if (!action && /^[0-9]$/.test(key)) {                      // 0 à 9 : saute à 0 %, 10 %… 90 % de la piste
        action = () => { if (Number.isFinite(audio.duration)) audio.currentTime = audio.duration * Number(key) / 10; };
      }
      if (!action) return;
      action();
      e.preventDefault();
    });
  }

  /** Touches multimédia du téléphone / du clavier et écran de verrouillage. */
  #bindMediaSession() {
    if (!('mediaSession' in navigator)) return;
    const handlers = {
      play: () => this.play(),
      pause: () => audio.pause(),
      previoustrack: () => this.previous(),
      nexttrack: () => this.next(),
      seekbackward: ({seekOffset} = {}) => this.seekBy(-(seekOffset || 10)),
      seekforward: ({seekOffset} = {}) => this.seekBy(seekOffset || 10),
      seekto: ({seekTime} = {}) => { if (Number.isFinite(seekTime)) audio.currentTime = seekTime; },
    };
    for (const [name, handler] of Object.entries(handlers)) {
      try { navigator.mediaSession.setActionHandler(name, handler); } catch { /* action non prise en charge */ }
    }
  }
}

new AudioPlayer();
