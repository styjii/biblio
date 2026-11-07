
/** Interface du lecteur façon YouTube : barre de commandes qui se masque, position (plage chargée, survol, glissement),
    précédente / suivante, ±10 s, aléatoire, répétition, volume, plein écran, mode cinéma, image dans l'image, et menu des
    paramètres (lecture automatique, aléatoire, répétition, vitesse, sous-titres, téléchargement), gestes tactiles
    (tape = commandes, double tape sur les côtés = ±10 s). Aucune commande n'est placée hors du lecteur.
    Sans ce script, les commandes natives restent. */
class PlayerUI {
  static HIDE_AFTER = 3000;                              // ms sans activité avant de masquer les commandes (pendant la lecture)
  static SKIP = 10;                                      // s : double tape sur un côté de l'image
  static DOUBLE_TAP = 300;                               // ms entre deux tapes d'un double tape

  #box = $('vbox');
  #page = $('watch');
  #ui = $('vp-ui');
  #seek = $('vp-seek');
  #tip = $('vp-tip');
  #buf = $('vp-buf');
  #menu = $('vp-menu');
  #cap = $('vp-cap');
  #settings;
  #host;
  #hideTimer = 0;
  #raf = 0;
  #overBar = false;
  #dragging = false;
  #ratio = 0;                                            // position visée pendant un glissement (0 à 1)
  #pointerType = 'mouse';
  #panel = 'root';
  #tracks = [...(video.textTracks ?? [])];
  #active = null;                                        // piste de sous-titres affichée
  #lastSecond = -1;
  #skipFx = {left: {total: 0, timer: 0}, right: {total: 0, timer: 0}};

  /** `settings` : PlaybackSettings (volume, vitesse) ; `host` : VideoPlayer (vidéo suivante / précédente). */
  constructor(settings, host) {
    this.#settings = settings;
    this.#host = host;
    video.controls = false;
    this.#box.classList.add('vp-on');
    this.#bindButtons();
    this.#bindPlayback();
    this.#bindSeekBar();
    this.#bindGestures();
    this.#bindAutoHide();
    this.#bindMenu();
    this.#bindCaptions();
    this.#bindScreen();
    this.#renderPlay();
    this.#renderBusy();
    this.#renderProgress();
  }

  static clock(seconds) {
    const total = Number.isFinite(seconds) && seconds > 0 ? Math.floor(seconds) : 0;
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = String(total % 60).padStart(2, '0');
    return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
  }

  /* ----- actions (aussi appelées par le clavier) ----- */
  toggle() {
    this.#flash(video.paused || video.ended ? 'play' : 'pause');
    if (video.paused || video.ended) play(); else video.pause();
  }

  /** Saut relatif avec retour visuel sur le côté concerné. */
  skip(seconds) {
    seekBy(seconds);
    this.#showSkip(seconds < 0 ? 'left' : 'right', seconds);
    this.#poke();
  }

  /** Aller à un pourcentage de la vidéo (touches 0 à 9). */
  jumpTo(ratio) {
    if (!Number.isFinite(video.duration)) return;
    video.currentTime = Math.min(video.duration - END_GUARD, Math.max(0, video.duration * ratio));
    this.#poke();
  }

  async toggleFullscreen() {
    const active = document.fullscreenElement ?? document.webkitFullscreenElement;
    if (active) { (document.exitFullscreen ?? document.webkitExitFullscreen)?.call(document); return; }
    try {
      if (this.#box.requestFullscreen) {
        await this.#box.requestFullscreen({navigationUI: 'hide'});
        if (matchMedia('(pointer:coarse)').matches) await screen.orientation?.lock?.('landscape');      // téléphone : paysage
      } else if (this.#box.webkitRequestFullscreen) this.#box.webkitRequestFullscreen();
      else video.webkitEnterFullscreen?.();              // iPhone : plein écran natif de la vidéo (sans nos commandes)
    } catch { /* plein écran refusé ou orientation non verrouillable : sans conséquence */ }
  }

  toggleTheater(force) {
    const on = force ?? !this.#page.classList.contains('theater');
    this.#page.classList.toggle('theater', on);
    this.#ui.querySelector('[data-act="theater"]')?.setAttribute('aria-pressed', String(on));
    prefs.set('theater', on ? '1' : '0');
  }

  async togglePip() {
    try {
      if (document.pictureInPictureElement) await document.exitPictureInPicture();
      else await video.requestPictureInPicture();
    } catch { say("Image dans l'image indisponible."); }
  }

  toggleCaptions() {
    if (!this.#tracks.length) return say('Aucun sous-titre pour cette vidéo.');
    if (this.#active) return this.#selectTrack(-1, true);
    const wanted = this.#tracks.findIndex((t) => t.label === prefs.get('cc', ''));
    this.#selectTrack(wanted >= 0 ? wanted : 0, true);
  }

  /** Télécharge la vidéo en cours (lien de téléchargement du serveur, sans quitter la page). */
  download() {
    const link = document.createElement('a');
    link.href = cfg.download;
    link.download = '';
    document.body.append(link);
    link.click();
    link.remove();
    say('Téléchargement lancé.');
  }

  /** Reflète l'aléatoire et la répétition sur les boutons de la barre (et dans le menu s'il est ouvert). */
  renderModes({shuffle, repeat}) {
    const names = {off: 'désactivée', all: 'toutes les vidéos', one: 'cette vidéo'};
    const shuffleButton = $('vp-shuffle');
    const repeatButton = $('vp-repeat');
    shuffleButton.classList.toggle('on', shuffle);
    shuffleButton.setAttribute('aria-pressed', String(shuffle));
    setIcon(repeatButton, repeat === 'one' ? 'repeat1' : 'repeat');
    repeatButton.classList.toggle('on', repeat !== 'off');
    repeatButton.setAttribute('aria-pressed', String(repeat !== 'off'));
    repeatButton.setAttribute('aria-label', `Répétition : ${names[repeat]}`);
    repeatButton.title = `Répétition (R) : ${{off: 'aucune', all: 'tout', one: 'une vidéo'}[repeat]}`;
    if (!this.#menu.hidden) this.#renderMenu(true);
  }

  /** Affiche un instant le curseur de volume (réglage au clavier). */
  peekVolume() {
    const box = $('vp-volbox');
    box.classList.add('peek');
    clearTimeout(this.#peekTimer);
    this.#peekTimer = setTimeout(() => box.classList.remove('peek'), 1500);
    this.#poke();
  }
  #peekTimer = 0;

  /* ----- boutons ----- */
  #bindButtons() {
    this.#ui.addEventListener('click', (e) => {
      const button = e.target.closest('[data-act]');
      if (!button) return;
      ({
        play: () => this.toggle(),
        prev: () => this.#host.previous(),
        next: () => this.#host.next(),
        back: () => this.skip(-PlayerUI.SKIP),
        fwd: () => this.skip(PlayerUI.SKIP),
        shuffle: () => this.#host.setShuffle(!this.#host.shuffle),
        repeat: () => this.#host.cycleRepeat(),
        mute: () => { this.#settings.toggleMute(); this.peekVolume(); },       // en très petit lecteur, le curseur s'ouvre un instant
        cc: () => this.toggleCaptions(),
        settings: () => this.#toggleMenu(),
        theater: () => this.toggleTheater(),
        pip: () => this.togglePip(),
        fs: () => this.toggleFullscreen(),
      })[button.dataset.act]?.();
      if (e.detail > 0) button.blur();                   // clic à la souris : le focus ne reste pas sur le bouton (la barre d'espace garde son rôle)
    });
    if (prefs.get('theater', '0') === '1') this.toggleTheater(true);
    else this.toggleTheater(false);
    if (document.pictureInPictureEnabled && !video.disablePictureInPicture) $('vp-pip').hidden = false;
  }

  /* ----- état de la lecture ----- */
  #bindPlayback() {
    const on = (type, handler) => video.addEventListener(type, handler);
    for (const type of ['play', 'pause', 'ended', 'emptied']) on(type, () => this.#renderPlay());
    for (const type of ['waiting', 'seeking', 'seeked', 'canplay', 'playing', 'loadstart', 'loadeddata', 'error', 'emptied']) on(type, () => this.#renderBusy());
    on('play', () => { this.#poke(); this.#kick(); });
    on('playing', () => this.#kick());
    on('pause', () => this.#showUI());
    on('ended', () => this.#showUI());
    on('timeupdate', () => { if (!this.#raf) this.#renderProgress(); });
    for (const type of ['durationchange', 'loadedmetadata', 'seeked', 'emptied']) on(type, () => this.#renderProgress());
    for (const type of ['progress', 'loadedmetadata', 'seeked', 'canplay', 'emptied']) on(type, () => this.#renderBuffered());
    on('enterpictureinpicture', () => { if (this.#active) this.#active.mode = 'showing'; this.#cap.hidden = true; });
    on('leavepictureinpicture', () => { if (this.#active) this.#active.mode = 'hidden'; this.#cap.hidden = false; this.#renderCue(); });
  }

  #renderPlay() {
    const state = video.ended ? 'replay' : video.paused ? 'play' : 'pause';
    const label = {replay: 'Revoir (K)', play: 'Lecture (K)', pause: 'Pause (K)'}[state];
    for (const button of this.#ui.querySelectorAll('[data-act="play"]')) {
      setIcon(button, state);
      button.dataset.state = state;
      button.setAttribute('aria-label', label.replace(' (K)', ''));
      button.title = label;
    }
    this.#box.classList.toggle('paused', video.paused || video.ended);
  }

  /** Roue de chargement : lecture qui attend des données, saut en cours, ou vidéo en cours de chargement. */
  #renderBusy() {
    const starving = video.readyState < 3 && !video.error && !video.ended;
    const busy = starving && (video.seeking || !video.paused || (video.readyState === 0 && video.networkState === 2));
    this.#box.classList.toggle('busy', busy);
  }

  /** Retour visuel géant au centre (lecture, pause). */
  #flash(name) {
    const fx = $('vp-fx');
    fx.innerHTML = icons[name] ?? '';
    fx.classList.remove('go');
    void fx.offsetWidth;                                 // relance l'animation même si elle est déjà en cours
    fx.classList.add('go');
  }

  /** Retour visuel d'un saut : les sauts rapprochés s'additionnent (+10 s, +20 s…). */
  #showSkip(side, seconds) {
    const state = this.#skipFx[side];
    state.total += Math.abs(seconds);
    const fx = $(side === 'left' ? 'vp-sk-l' : 'vp-sk-r');
    fx.textContent = `${side === 'left' ? '−' : '+'}${state.total} s`;
    fx.classList.remove('go');
    void fx.offsetWidth;
    fx.classList.add('go');
    clearTimeout(state.timer);
    state.timer = setTimeout(() => { state.total = 0; }, 900);
  }

  /* ----- position ----- */
  #bindSeekBar() {
    const seek = this.#seek;
    const ratioAt = (e) => {
      const rect = seek.getBoundingClientRect();
      return rect.width > 0 ? Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)) : 0;
    };
    const preview = (e) => {
      const rect = seek.getBoundingClientRect();
      const ratio = ratioAt(e);
      const half = this.#tip.offsetWidth / 2;
      this.#tip.textContent = PlayerUI.clock(ratio * (video.duration || 0));
      this.#tip.style.left = `${Math.min(rect.width - half, Math.max(half, ratio * rect.width))}px`;
      return ratio;
    };
    seek.addEventListener('pointerdown', (e) => {
      if (e.button) return;
      seek.setPointerCapture?.(e.pointerId);
      this.#dragging = true;
      this.#box.classList.add('scrub');
      this.#ratio = preview(e);
      this.#paintPosition(this.#ratio);
    });
    seek.addEventListener('pointermove', (e) => {
      if (!this.#dragging && e.pointerType !== 'mouse') return;
      const ratio = preview(e);
      if (this.#dragging) { this.#ratio = ratio; this.#paintPosition(ratio); }
    });
    const finish = (e, commit) => {
      if (!this.#dragging) return;
      this.#dragging = false;
      this.#box.classList.remove('scrub');
      if (commit) this.jumpTo(this.#ratio);
      this.#renderProgress();
      if (e.pointerId !== undefined) seek.releasePointerCapture?.(e.pointerId);
    };
    seek.addEventListener('pointerup', (e) => finish(e, true));
    seek.addEventListener('pointercancel', (e) => finish(e, false));
  }

  #paintPosition(ratio) {
    this.#seek.style.setProperty('--p', ratio);
    $('vp-time').textContent = `${PlayerUI.clock(ratio * (video.duration || 0))} / ${PlayerUI.clock(video.duration)}`;
  }

  #renderProgress() {
    if (this.#dragging) return;
    const {duration, currentTime} = video;
    const known = Number.isFinite(duration) && duration > 0;
    this.#seek.style.setProperty('--p', known ? Math.min(1, currentTime / duration) : 0);
    const second = Math.floor(currentTime);
    if (second !== this.#lastSecond || !known) {          // le texte ne change qu'une fois par seconde
      this.#lastSecond = second;
      $('vp-time').textContent = `${PlayerUI.clock(currentTime)} / ${PlayerUI.clock(known ? duration : 0)}`;
      this.#seek.setAttribute('aria-valuenow', String(known ? Math.round((currentTime / duration) * 100) : 0));
      this.#seek.setAttribute('aria-valuetext', `${PlayerUI.clock(currentTime)} sur ${PlayerUI.clock(known ? duration : 0)}`);
    }
  }

  /** Plages déjà en mémoire tampon (il peut y en avoir plusieurs après des sauts). */
  #renderBuffered() {
    const {duration, buffered} = video;
    const parts = [];
    if (Number.isFinite(duration) && duration > 0) {
      for (let i = 0; i < buffered.length; i++) {
        const part = document.createElement('i');
        part.style.left = `${(buffered.start(i) / duration) * 100}%`;
        part.style.width = `${((buffered.end(i) - buffered.start(i)) / duration) * 100}%`;
        parts.push(part);
      }
    }
    this.#buf.replaceChildren(...parts);
  }

  /** Pendant la lecture, la barre est redessinée à chaque image affichée (fluide), et seulement si elle est visible. */
  #kick() {
    if (this.#raf || typeof requestAnimationFrame !== 'function') return;
    const step = () => {
      this.#raf = 0;
      this.#renderProgress();
      if (!video.paused && !document.hidden && !this.#box.classList.contains('ui-off')) this.#raf = requestAnimationFrame(step);
    };
    this.#raf = requestAnimationFrame(step);
  }

  /* ----- gestes (souris et tactile) ----- */
  #bindGestures() {
    const box = this.#box;
    let lastTap = {time: 0, zone: ''};
    let tapTimer = 0;
    box.addEventListener('pointerup', (e) => {
      this.#pointerType = e.pointerType;
      if (e.target !== video) return;                    // boutons, barre, menu : ils ont leurs propres actions
      if (!this.#menu.hidden) { this.#closeMenu(); return; }
      if (e.pointerType === 'mouse') { if (e.button === 0) this.toggle(); return; }
      const rect = video.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const zone = x < 0.33 ? 'left' : x > 0.67 ? 'right' : 'center';
      const now = Date.now();
      clearTimeout(tapTimer);
      if (now - lastTap.time < PlayerUI.DOUBLE_TAP && lastTap.zone === zone) {        // double tape
        lastTap = {time: 0, zone: ''};
        if (zone === 'center') this.toggle(); else this.skip(zone === 'left' ? -PlayerUI.SKIP : PlayerUI.SKIP);
        return;
      }
      lastTap = {time: now, zone};
      tapTimer = setTimeout(() => this.#toggleUI(), PlayerUI.DOUBLE_TAP - 20);       // simple tape : afficher / masquer les commandes
    });
    box.addEventListener('dblclick', (e) => {
      if (e.target === video && this.#pointerType === 'mouse') this.toggleFullscreen();   // (les deux clics ont déjà rétabli l'état lecture / pause)
    });
  }

  /* ----- masquage automatique des commandes ----- */
  #bindAutoHide() {
    const box = this.#box;
    box.addEventListener('pointermove', (e) => { if (e.pointerType === 'mouse') this.#poke(); });
    box.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') { this.#overBar = false; this.#schedule(800); } });
    for (const part of this.#ui.querySelectorAll('.vp-bar,.vp-mid,.vp-menu')) {
      part.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') this.#overBar = true; });
      part.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') this.#overBar = false; });
    }
    this.#ui.addEventListener('pointerdown', () => this.#poke());
    box.addEventListener('focusin', () => this.#poke());
    document.addEventListener('keydown', () => this.#poke());
    document.addEventListener('visibilitychange', () => { if (!document.hidden) this.#kick(); });
  }

  get #hidden() { return this.#box.classList.contains('ui-off'); }
  #showUI() { clearTimeout(this.#hideTimer); this.#box.classList.remove('ui-off'); this.#kick(); }
  #hideUI() { if (!video.paused && this.#menu.hidden && !this.#dragging) this.#box.classList.add('ui-off'); }
  #poke() { this.#showUI(); this.#schedule(); }
  #schedule(delay = PlayerUI.HIDE_AFTER) {
    clearTimeout(this.#hideTimer);
    if (video.paused || !this.#menu.hidden || this.#overBar || this.#dragging) return;
    this.#hideTimer = setTimeout(() => this.#hideUI(), delay);
  }
  #toggleUI() { if (this.#hidden) this.#poke(); else this.#hideUI(); }

  /* ----- menu des paramètres ----- */
  #bindMenu() {
    document.addEventListener('pointerdown', (e) => {    // un clic ailleurs referme le menu
      if (!this.#menu.hidden && !e.target.closest('.vp-menu,[data-act="settings"]')) this.#closeMenu();
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !this.#menu.hidden) this.#closeMenu(); });
    this.#menu.addEventListener('keydown', (e) => {      // flèches haut / bas : on parcourt les choix
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      const choices = [...this.#menu.querySelectorAll('button')];
      const next = choices.indexOf(document.activeElement) + (e.key === 'ArrowDown' ? 1 : -1);
      choices[(next + choices.length) % choices.length]?.focus();
      e.preventDefault();
    });
  }

  #toggleMenu() { if (this.#menu.hidden) this.#openMenu(); else this.#closeMenu(); }

  #openMenu(panel = 'root') {
    this.#panel = panel;
    this.#menu.hidden = false;
    this.#box.classList.add('menu');
    $('vp-set').setAttribute('aria-expanded', 'true');
    this.#renderMenu();
    this.#showUI();
  }

  #closeMenu() {
    this.#menu.hidden = true;
    this.#box.classList.remove('menu');
    $('vp-set').setAttribute('aria-expanded', 'false');
    this.#schedule();
  }

  /** `keepFocus` : un réglage vient d'être basculé, le focus reste sur la même ligne (sinon il va sur la première). */
  #renderMenu(keepFocus = false) {
    const rows = [];
    const focused = keepFocus ? [...this.#menu.querySelectorAll('button')].indexOf(document.activeElement) : -1;
    const row = (label, {value = '', checked, icon, onClick, header, toggle} = {}) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('role', header ? 'menuitem' : toggle ? 'menuitemcheckbox' : checked !== undefined ? 'menuitemradio' : 'menuitem');
      if (header) button.className = 'hd';
      if (checked !== undefined || toggle) button.classList.toggle('on', Boolean(checked ?? toggle.on));
      if (checked !== undefined || header) {
        const mark = document.createElement('span');
        mark.className = 'ck';
        mark.innerHTML = header ? (icons.chevron_left ?? '') : (icons.check ?? '');
        button.append(mark);
      } else if (icon) {
        const mark = document.createElement('span');
        mark.className = 'ck ic';
        mark.innerHTML = icon;
        button.append(mark);
      }
      const text = document.createElement('span');
      text.textContent = label;
      button.append(text);
      if (toggle) { const sw = document.createElement('span'); sw.className = 'sw'; button.append(sw); }
      else if (value) { const v = document.createElement('span'); v.className = 'val'; v.textContent = value; button.append(v); }
      if (checked !== undefined) button.setAttribute('aria-checked', String(Boolean(checked)));
      else if (toggle) button.setAttribute('aria-checked', String(Boolean(toggle.on)));
      button.addEventListener('click', onClick);
      rows.push(button);
    };
    const rateLabel = (r) => (r === 1 ? 'Normale' : `${String(r).replace('.', ',')}×`);
    const repeatLabel = {off: 'Désactivée', all: 'Toutes les vidéos', one: 'Cette vidéo'};
    const host = this.#host;
    if (this.#panel === 'speed') {
      row('Vitesse de lecture', {header: true, onClick: () => this.#openMenu('root')});
      for (const rate of PlaybackSettings.RATES) {
        row(rateLabel(rate), {checked: rate === this.#settings.rate, onClick: () => { this.#settings.setRate(rate); this.#closeMenu(); }});
      }
    } else if (this.#panel === 'subs') {
      row('Sous-titres', {header: true, onClick: () => this.#openMenu('root')});
      row('Désactivés', {checked: !this.#active, onClick: () => { this.#selectTrack(-1, true); this.#closeMenu(); }});
      this.#tracks.forEach((track, i) => row(track.label || `Piste ${i + 1}`, {checked: track === this.#active, onClick: () => { this.#selectTrack(i, true); this.#closeMenu(); }}));
    } else if (this.#panel === 'repeat') {
      row('Répétition', {header: true, onClick: () => this.#openMenu('root')});
      for (const mode of ['off', 'all', 'one']) {
        row(repeatLabel[mode], {checked: mode === host.repeat, onClick: () => { host.setRepeat(mode); this.#closeMenu(); }});
      }
    } else {
      const ic = (name) => icons[name] ?? '';
      row('Lecture automatique', {icon: ic('queue'), toggle: {on: host.autoNext}, onClick: () => { host.setAutoNext(!host.autoNext); this.#renderMenu(true); }});
      row('Lecture aléatoire', {icon: ic('shuffle'), toggle: {on: host.shuffle}, onClick: () => host.setShuffle(!host.shuffle)});
      row('Répétition', {icon: ic('repeat'), value: repeatLabel[host.repeat], onClick: () => this.#openMenu('repeat')});
      row('Vitesse de lecture', {icon: ic('gauge'), value: rateLabel(this.#settings.rate), onClick: () => this.#openMenu('speed')});
      if (this.#tracks.length) row('Sous-titres', {icon: ic('captions'), value: this.#active?.label || 'Désactivés', onClick: () => this.#openMenu('subs')});
      row('Télécharger la vidéo', {icon: ic('download'), onClick: () => { this.#closeMenu(); this.download(); }});
    }
    this.#menu.replaceChildren(...rows);
    (rows[focused] ?? rows[0])?.focus({preventScroll: true});
  }

  /** Autre vidéo chargée dans le même lecteur (plein écran conservé) : sous-titres relus, menu fermé, barre affichée un instant. */
  reload() {
    this.#closeMenu();
    this.#tracks = [...(video.textTracks ?? [])];
    this.#active = null;
    this.#cap.replaceChildren();
    this.#lastSecond = -1;
    this.#bindCaptions();
    this.#poke();
  }

  /* ----- sous-titres : dessinés par le script, au-dessus de la barre de commandes ----- */
  #bindCaptions() {
    $('vp-cc').hidden = !this.#tracks.length;
    for (const track of this.#tracks) track.addEventListener('cuechange', () => this.#renderCue());
    const wanted = this.#tracks.findIndex((t) => t.label === prefs.get('cc', '\u0000'));
    this.#selectTrack(wanted, false);                    // dernière langue choisie, sinon aucun sous-titre (comme YouTube)
  }

  /** `byUser` : choix de l'utilisateur (il est mémorisé et annoncé) ; sinon simple application de la préférence au chargement. */
  #selectTrack(index, byUser) {
    this.#tracks.forEach((track, i) => { track.mode = i === index ? 'hidden' : 'disabled'; });
    this.#active = this.#tracks[index] ?? null;
    $('vp-cc').setAttribute('aria-pressed', String(Boolean(this.#active)));
    this.#renderCue();
    if (!byUser) return;
    prefs.set('cc', this.#active?.label ?? '');
    say(this.#active ? `Sous-titres : ${this.#active.label}` : 'Sous-titres désactivés');
  }

  #renderCue() {
    const lines = [];
    for (const cue of this.#active?.activeCues ?? []) {
      const line = document.createElement('div');
      line.className = 'vp-cue';
      line.append(cue.getCueAsHTML());
      lines.push(line);
    }
    this.#cap.replaceChildren(...lines);
  }

  /* ----- plein écran ----- */
  #bindScreen() {
    const sync = () => {
      const full = (document.fullscreenElement ?? document.webkitFullscreenElement) === this.#box;
      const button = $('vp-fs');
      setIcon(button, full ? 'shrink' : 'expand');
      button.setAttribute('aria-label', full ? 'Quitter le plein écran' : 'Plein écran');
      button.title = full ? 'Quitter le plein écran (F)' : 'Plein écran (F)';
      if (!full) screen.orientation?.unlock?.();
      this.#poke();
    };
    document.addEventListener('fullscreenchange', sync);
    document.addEventListener('webkitfullscreenchange', sync);
  }
}
