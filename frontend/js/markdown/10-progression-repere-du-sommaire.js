/** Barre de progression, repère de la section courante dans le sommaire, et mémorisation de la position de lecture. */
class ReadingProgress {
  #current = -1; // section courante dans le sommaire
  #ticking = false;
  #saveTimer = 0;
  #positionKey = `md-pos:${cfg.q}`;

  constructor() {
    sc.addEventListener(
      'scroll',
      () => {
        if (!this.#ticking) {
          this.#ticking = true;
          requestAnimationFrame(() => this.update());
        }
        clearTimeout(this.#saveTimer);
        this.#saveTimer = setTimeout(
          () => store.set(this.#positionKey, String(sc.scrollHeight > 0 ? (sc.scrollTop / sc.scrollHeight).toFixed(4) : 0)),
          400,
        );
      },
      {passive: true},
    );
    window.addEventListener('resize', () => this.update());
  }

  /** Position mémorisée, de 0 à 1 (0 : aucune). */
  get savedPosition() {
    return parseFloat(store.get(this.#positionKey) || '0');
  }

  update() {
    this.#ticking = false;
    const max = sc.scrollHeight - sc.clientHeight;
    bar.style.width = `${max > 0 ? (sc.scrollTop / max) * 100 : 100}%`;
    const elements = toc.headingElements;
    if (!elements.length) return;
    const limit = sc.getBoundingClientRect().top + 40;
    let current = -1;
    for (let i = 0; i < elements.length && elements[i].getBoundingClientRect().top <= limit; i++) current = i;
    if (current === this.#current) return;
    this.#current = current;
    const links = toc.links;
    links.forEach((link, k) => link.classList.toggle('on', k === current));
    const link = links[current];
    if (link && toc.nav.offsetParent !== null) {
      // garde le repère visible dans le sommaire
      const nav = toc.nav;
      if (link.offsetTop < nav.scrollTop + 40 || link.offsetTop + link.offsetHeight > nav.scrollTop + nav.clientHeight - 20) {
        nav.scrollTop = Math.max(0, link.offsetTop - nav.clientHeight / 3);
      }
    }
  }
}

const progress = new ReadingProgress();
