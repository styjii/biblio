
/** Défilement de la page et plein écran. En plein écran, le conteneur du lecteur sort du flux de la page : celle-ci raccourcit de sa hauteur, le
    navigateur ramène alors le défilement dans les nouvelles limites, et la page ne retrouve pas sa position à la sortie (elle semble remonter).
    Cette garde retient la position juste avant l'entrée, maintient la hauteur de la page pendant le plein écran (le défilement n'est plus ramené
    en arrière), puis rétablit la position à la sortie si elle a bougé. Elle ne fait rien d'autre : pas de défilement à l'entrée, rien si la page n'a pas bougé.
    Plein écran lancé par le navigateur (commandes natives, iOS) : la position est celle d'avant la transition, relevée dans l'historique du défilement. */
class FullscreenScroll {
  static LOOKBACK = 400;                                  // ms : sans demande du lecteur, la position retenue date d'au moins ce délai avant l'événement (le recadrage du navigateur le précède souvent)
  static HISTORY = 3000;                                  // ms de positions conservées
  static GIVE_UP = 1500;                                  // ms : plein écran refusé ou jamais arrivé, la hauteur de la page est rendue

  #history = [];                                          // [{at, x, y}] positions hors plein écran
  #saved = null;                                          // {x, y} : position d'avant le plein écran en cours
  #held = false;                                          // la hauteur de la page est maintenue

  constructor() {
    addEventListener('scroll', () => this.#track(), {passive: true});
    for (const type of ['fullscreenchange', 'webkitfullscreenchange']) document.addEventListener(type, () => this.#sync());
    for (const type of ['webkitbeginfullscreen', 'webkitendfullscreen']) video.addEventListener(type, () => this.#sync());     // plein écran natif d'iOS
    this.#track();
  }

  get #active() { return Boolean(document.fullscreenElement ?? document.webkitFullscreenElement ?? video.webkitDisplayingFullscreen); }

  #track() {
    if (this.#active) return;
    const at = Date.now();
    this.#history.push({at, x: scrollX, y: scrollY});
    while (this.#history.length > 1 && at - this.#history[0].at > FullscreenScroll.HISTORY) this.#history.shift();
  }

  /** Le lecteur va entrer en plein écran (bouton, touche F, double-clic) : la position est retenue et la hauteur de la page maintenue. */
  expect() {
    if (this.#active || this.#saved) return;
    this.#saved = {x: scrollX, y: scrollY};
    const root = document.documentElement;
    root.style.minHeight = `${root.scrollHeight}px`;
    this.#held = true;
    setTimeout(() => { if (!this.#active) this.#release(); }, FullscreenScroll.GIVE_UP);     // le plein écran n'est pas venu
  }

  #release() {
    this.#saved = null;
    if (!this.#held) return;
    this.#held = false;
    document.documentElement.style.minHeight = '';
  }

  #sync() {
    if (this.#active) {                                   // entrée : sans demande du lecteur, on prend la position d'avant dans l'historique
      if (!this.#saved) {
        const cutoff = Date.now() - FullscreenScroll.LOOKBACK;
        const before = [...this.#history].reverse().find((entry) => entry.at <= cutoff) ?? this.#history[0];
        if (before) this.#saved = {x: before.x, y: before.y};
      }
      return;
    }
    const saved = this.#saved;                            // sortie : la page retrouve exactement sa position
    if (!saved) return this.#release();
    const back = () => { if (Math.abs(scrollY - saved.y) > 1 || Math.abs(scrollX - saved.x) > 1) scrollTo(saved.x, saved.y); };
    back();
    requestAnimationFrame(() => { back(); this.#release(); });      // la mise en page reprend sa forme d'origine après l'événement : on vérifie encore une fois
  }
}
const fullscreenScroll = new FullscreenScroll();
