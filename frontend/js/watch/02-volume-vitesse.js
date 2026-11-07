
/** Volume, muet et vitesse : appliqués au chargement, mémorisés d'une vidéo à l'autre (même quand on les change avec les contrôles natifs). */
class PlaybackSettings {
  static RATES = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

  #rate;
  #slider = $('vp-vol');
  #mute = $('vp-mute');

  constructor() {
    const rate = parseFloat(prefs.get('rate', '1'));
    this.#rate = PlaybackSettings.RATES.includes(rate) ? rate : 1;
    let volume = parseFloat(prefs.get('vol', '1'));
    if (!(volume >= 0 && volume <= 1)) volume = 1;
    video.volume = volume;
    video.muted = prefs.get('muted', '0') === '1';
    video.defaultPlaybackRate = video.playbackRate = this.#rate;

    video.addEventListener('volumechange', () => {
      this.#renderVolume();
      prefs.set('vol', video.volume);
      prefs.set('muted', video.muted ? '1' : '0');
    });
    video.addEventListener('ratechange', () => {            // vitesse changée depuis le menu du lecteur natif : on la retient aussi
      if (PlaybackSettings.RATES.includes(video.playbackRate) && video.playbackRate !== this.#rate) {
        this.#rate = video.playbackRate;
        prefs.set('rate', this.#rate);
      }
    });
    this.#slider.addEventListener('input', ({target}) => this.setVolume(target.value / 100));
    this.#slider.addEventListener('change', ({target}) => target.blur());
    this.#renderVolume();
  }

  get rate() { return this.#rate; }

  /** Volume réellement audible (0 si muet). */
  get volume() { return video.muted ? 0 : video.volume; }

  setVolume(volume) {
    video.volume = Math.max(0, Math.min(1, volume));
    if (video.volume > 0) video.muted = false;
  }

  toggleMute() { video.muted = !video.muted; }

  setRate(rate) {
    this.#rate = rate;
    video.defaultPlaybackRate = video.playbackRate = rate;
    prefs.set('rate', rate);
    say(`Vitesse : ${this.#format(rate)}`);
  }

  stepRate(direction) {
    const {RATES} = PlaybackSettings;
    this.setRate(RATES[Math.max(0, Math.min(RATES.length - 1, RATES.indexOf(this.#rate) + direction))]);
  }

  #format(rate) { return `${String(rate).replace('.', ',')}×`; }

  #renderVolume() {
    const muted = video.muted || video.volume === 0;
    const percent = Math.round(this.volume * 100);
    setIcon(this.#mute, muted ? 'mute' : 'volume');
    this.#mute.setAttribute('aria-pressed', String(muted));
    this.#mute.setAttribute('aria-label', muted ? 'Réactiver le son' : 'Muet');
    this.#slider.value = percent;
    this.#slider.style.setProperty('--p', `${percent}%`);
    this.#slider.setAttribute('aria-valuetext', `${percent} %`);
  }
}
