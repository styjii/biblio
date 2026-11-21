
/** Plein écran : c'est le conteneur du lecteur qui passe en plein écran, jamais la balise <video> qui reste la même (ni recréée, ni rechargée) :
    sa position, son état lecture/pause, son volume, son mode muet et sa vitesse sont donc conservés d'eux-mêmes.
    Cette garde ne sert qu'aux navigateurs qui, à l'entrée ou à la sortie, font reculer la lecture, la remettent à 0:00 ou la mettent en
    pause (typiquement le plein écran natif d'iOS, qui interrompt la lecture à sa fermeture) : elle rétablit alors UNE seule fois l'état
    d'avant la transition, puis s'efface. Quand tout s'est bien passé, ou quand l'utilisateur a agi entre-temps, elle ne touche à rien.
    L'état de référence est pris au moment où le lecteur demande la transition (expect), sinon (plein écran lancé par le navigateur :
    commandes natives, touche Échap, geste « retour ») dans les échantillons pris à chaque événement de lecture, d'avant la transition
    (alors, la garde ne fait que relancer une lecture interrompue ou remonter une position perdue : elle ne force jamais une pause). */
class FullscreenKeeper {
  static LOOKBACK = 600;                                  // ms : sans demande du lecteur, l'état rétabli date d'au moins ce délai avant l'événement (une pause provoquée par la transition le précède souvent)
  static SETTLE = 500;                                    // ms : temps laissé au navigateur pour finir la transition avant de comparer
  static MAX_JUMP = 1.5;                                  // s : un recul plus grand que cela est une perte de position (une lecture normale n'en fait jamais)
  static HISTORY = 4000;                                  // ms d'échantillons conservés

  #history = [];                                          // [{at, time, playing, src, acted}]
  #pending = null;                                        // {base, at, exact} : transition en cours de vérification
  #timer = 0;
  #acted = 0;                                             // dernière action de l'utilisateur dans la page (clavier, doigt, souris)

  constructor() {
    for (const type of ['timeupdate', 'play', 'pause', 'seeked']) video.addEventListener(type, () => this.#sample());
    video.addEventListener('loadstart', () => { this.#history = []; });                 // autre média : les anciens échantillons ne le concernent pas
    for (const type of ['webkitbeginfullscreen', 'webkitendfullscreen']) video.addEventListener(type, () => this.#begin());   // plein écran natif d'iOS
    for (const type of ['fullscreenchange', 'webkitfullscreenchange']) document.addEventListener(type, () => this.#begin());
    for (const type of ['pointerdown', 'keydown']) document.addEventListener(type, () => { this.#acted = Date.now(); }, true);
  }

  #state(at = Date.now()) {
    return {at, time: video.currentTime, playing: !video.paused && !video.ended, src: video.currentSrc, acted: this.#acted};
  }

  #sample() {
    if (video.seeking || video.readyState < 1 || !Number.isFinite(video.currentTime)) return;     // en plein saut ou avant les métadonnées : position sans valeur
    const sample = this.#state();
    this.#history.push(sample);
    while (this.#history.length > 1 && sample.at - this.#history[0].at > FullscreenKeeper.HISTORY) this.#history.shift();
  }

  /** Le lecteur va entrer ou sortir du plein écran (bouton, touche F, double-clic) : l'état d'avant est retenu tel quel. */
  expect() {
    if (video.readyState < 1) return;
    this.#arm(this.#state(), Date.now(), true);
  }

  /** Événement de plein écran : sans demande préalable du lecteur, l'état de référence vient des échantillons, avec prudence :
      pas d'échantillon récent, ou pause / saut voulu par l'utilisateur juste avant la transition = rien à rétablir ; et on ne force jamais une pause. */
  #begin() {
    if (this.#pending) return this.#arm(this.#pending.base, this.#pending.at, this.#pending.exact);   // plusieurs événements pour une même transition
    const at = Date.now();
    const cutoff = at - FullscreenKeeper.LOOKBACK;
    const base = [...this.#history].reverse().find((sample) => sample.at <= cutoff);
    if (!base || at - base.at > FullscreenKeeper.HISTORY) return;
    const wanted = (sample) => sample.at - sample.acted < 1500 && (sample.playing !== base.playing || sample.time < base.time - FullscreenKeeper.MAX_JUMP);
    if (this.#history.some((sample) => sample.at > cutoff && wanted(sample))) return;
    this.#arm(base, at, false);
  }

  #arm(base, at, exact) {
    this.#pending = {base, at, exact};
    clearTimeout(this.#timer);
    this.#timer = setTimeout(() => this.#check(), FullscreenKeeper.SETTLE);
  }

  #check() {
    const {base, at, exact} = this.#pending ?? {};
    this.#pending = null;
    if (!base || this.#acted > at || video.currentSrc !== base.src) return;            // l'utilisateur a agi, ou c'est un autre média : rien à rétablir
    const restore = () => {
      if (video.ended) return;
      const expected = base.time + (base.playing ? (Date.now() - base.at) / 1000 * (video.playbackRate || 1) : 0);
      if (Number.isFinite(video.duration) && base.time - video.currentTime > FullscreenKeeper.MAX_JUMP) {
        video.currentTime = Math.min(expected, Math.max(0, video.duration - END_GUARD));        // une seule fois, jamais en boucle
      }
      if (base.playing && video.paused) play();
      else if (exact && !base.playing && !video.paused) video.pause();
    };
    if (video.readyState >= 1) restore(); else video.addEventListener('loadedmetadata', restore, {once: true});     // média rechargé par le navigateur : on attend ses métadonnées
  }
}
const fullscreenKeeper = new FullscreenKeeper();
