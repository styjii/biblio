
/** Tout ce que le lecteur affiche : bouton lecture, modes, volume, vitesse, barre de position, titre, pochette, écran de verrouillage. */
class PlayerView {
  #cover = $('l-cover');
  #image = $('l-img');
  #seek = $('l-seek');
  #volume = $('l-vol');
  loading = false;                                         // en attente de données : le bouton lecture tourne
  seeking = false;                                         // le curseur de position est tenu par l'utilisateur

  constructor() {
    this.#image.addEventListener('load', () => { this.#cover.classList.add('has-img'); this.#image.hidden = false; });
    this.#image.addEventListener('error', () => { this.#cover.classList.remove('has-img'); this.#image.hidden = true; });
  }

  renderPlay(playing) {
    const button = $('b-play');
    setIcon(button, this.loading ? 'loader' : (playing ? 'pause' : 'play'));
    button.classList.toggle('loading', this.loading);
    button.setAttribute('aria-busy', String(this.loading));
    button.setAttribute('aria-label', playing ? 'Pause' : 'Lecture');
    this.#cover.classList.toggle('playing', playing && !this.loading);
  }

  renderModes(shuffle, repeat) {
    const shuffleButton = $('b-shuffle');
    const repeatButton = $('b-repeat');
    const label = {off: 'désactivée', all: 'toutes les pistes', one: 'cette piste'}[repeat];
    shuffleButton.classList.toggle('on', shuffle);
    shuffleButton.setAttribute('aria-pressed', String(shuffle));
    setIcon(repeatButton, repeat === 'one' ? 'repeat1' : 'repeat');
    repeatButton.classList.toggle('on', repeat !== 'off');
    repeatButton.setAttribute('aria-pressed', String(repeat !== 'off'));
    repeatButton.setAttribute('aria-label', `Répétition : ${label}`);
    repeatButton.title = `Répétition (R) : ${{off: 'aucune', all: 'tout', one: 'une piste'}[repeat]}`;
  }

  renderVolume() {
    const muted = audio.muted || audio.volume === 0;
    const percent = Math.round((audio.muted ? 0 : audio.volume) * 100);
    setIcon($('b-mute'), muted ? 'mute' : 'volume');
    $('b-mute').setAttribute('aria-pressed', String(muted));
    this.#volume.value = percent;
    this.#volume.style.setProperty('--p', `${percent}%`);
    this.#volume.setAttribute('aria-valuetext', `${percent} %`);
  }

  renderRate(rate) { $('b-rate').textContent = `${String(rate).replace('.', ',')}×`; }

  renderSeek() {
    const ready = isReady();
    const duration = ready ? audio.duration : 0;
    const percent = ready ? audio.currentTime / duration * 100 : 0;
    if (!this.seeking) this.#seek.value = Math.round(percent * 10);
    const shown = this.seeking ? this.#seek.value / 10 : percent;
    let buffered = 0;
    if (ready) {                                           // fin de la plage déjà en mémoire tampon autour de la position
      for (let i = 0; i < audio.buffered.length; i++) {
        if (audio.buffered.start(i) <= audio.currentTime + 0.25 && audio.buffered.end(i) >= audio.currentTime) {
          buffered = Math.max(buffered, audio.buffered.end(i));
        }
      }
      buffered = buffered / duration * 100;
    }
    this.#seek.style.setProperty('--p', `${shown}%`);
    this.#seek.style.setProperty('--b', `${Math.max(shown, buffered)}%`);
    $('l-cur').textContent = formatTime(this.seeking && ready ? this.#seek.value / 1000 * duration : audio.currentTime);
    $('l-dur').textContent = formatTime(duration);
    this.#seek.setAttribute('aria-valuetext', `${formatTime(audio.currentTime)} sur ${formatTime(duration)}`);
  }

  /* ----- titre, pochette, écran de verrouillage ----- */
  static coverUrl(index) { return `/cover?f=${tracks[index].q}`; }

  applyTitle(info, index) {
    const title = info?.title || tracks[index].n;
    const subtitle = [info?.artist, info?.album].filter(Boolean).join(' · ');
    $('l-title').textContent = title;
    $('l-artist').textContent = subtitle;
    $('l-artist').hidden = !subtitle;
    document.title = `${title} — Lecteur audio`;
    this.#updateSession(title, info, index);
  }

  setCover(info, index) {
    this.#cover.classList.remove('has-img');
    this.#image.hidden = true;
    this.#image.removeAttribute('src');
    if (info?.cover) this.#image.src = PlayerView.coverUrl(index);
  }

  #updateSession(title, info, index) {
    if (!('mediaSession' in navigator) || !window.MediaMetadata) return;
    let artwork = [];
    if (info?.cover) {
      try { artwork = [{src: new URL(PlayerView.coverUrl(index), location.href).href, sizes: '640x640'}]; } catch { /* pas de pochette */ }
    }
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title, artist: info?.artist || cfg.folder, album: info?.album || cfg.folder, artwork,
      });
    } catch { /* écran de verrouillage non mis à jour */ }
  }
}
