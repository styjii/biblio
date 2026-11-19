/**
 * Visionneuse : une image à la fois, ajustée à l'écran ; zoom (boutons, clavier, molette, double-clic, pincement), déplacement
 * (glisser), image précédente / suivante (boutons, clavier, balayage), plein écran, retour à la liste.
 *
 * Géométrie : l'image est positionnée en (0, 0) et transformée par translate(x, y) scale(s) ; (x, y) est le coin haut gauche de
 * l'image dans la scène. « Ajusté » = échelle qui fait tenir l'image entière (sans jamais l'agrandir au-delà de 100 %).
 */
class ImageViewer {
  static STEP = 1.25;                                    // facteur d'un cran de zoom
  static MAX_SCALE = 16;
  static SWIPE_MIN = 60;                                 // px : balayage horizontal pour changer d'image
  static ZOOM_KEYS = {'+': 1, '=': 1, '-': -1, _: -1};

  #items;
  #index = 0;
  #img = $('iv-img');
  #stage = $('iv-stage');
  #natural = {w: 0, h: 0};
  #scale = 1;
  #x = 0;
  #y = 0;
  #fitted = true;                                        // vrai tant que l'image est ajustée à l'écran (suit alors les redimensionnements)
  #pointers = new Map();
  #gesture = null;                                       // {kind: 'pan' | 'pinch' | 'swipe', …}
  #spinner = 0;
  #preloaded = null;

  constructor() {
    this.#items = ImageOrder.sorted(cfg.items, cfg.current);
    this.#index = Math.max(0, this.#items.findIndex((item) => item.f === cfg.current));
    this.#bindButtons();
    this.#bindPointer();
    this.#bindKeys();
    new ResizeObserver(() => this.#relayout()).observe(this.#stage);
    document.addEventListener('fullscreenchange', () => {
      $('iv-fs').innerHTML = ICO[document.fullscreenElement ? 'shrink' : 'expand'] ?? '';
      this.#relayout();
    });
    this.#img.addEventListener('load', () => this.#loaded());
    this.#img.addEventListener('error', () => this.#failed());
    this.show(this.#index);
  }

  get #stageSize() { return {w: this.#stage.clientWidth, h: this.#stage.clientHeight}; }
  get #fitScale() {
    const {w, h} = this.#stageSize;
    return this.#natural.w ? Math.min(1, w / this.#natural.w, h / this.#natural.h) : 1;
  }
  get #minScale() { return Math.min(this.#fitScale, 0.2); }

  /* ----- images ----- */
  /** Affiche l'image n° `index` de la liste. */
  show(index) {
    if (index < 0 || index >= this.#items.length) return;
    this.#index = index;
    const item = this.#items[index];
    this.#img.style.visibility = 'hidden';
    $('iv-error').hidden = true;
    clearTimeout(this.#spinner);
    this.#spinner = setTimeout(() => { $('iv-loading').hidden = false; }, 150);   // pas de clignotement pour une image rapide
    this.#img.alt = item.n;
    this.#img.src = `/raw?f=${encodeURIComponent(item.f)}`;
    $('iv-name').textContent = item.n;
    $('iv-name').title = item.n;
    $('iv-count').textContent = `${index + 1} / ${this.#items.length}`;
    document.title = `${item.n} — Ma bibliothèque`;
    try { history.replaceState(null, '', `/image?f=${encodeURIComponent(item.f)}`); } catch { /* adresse inchangée */ }
    for (const id of ['iv-prev', 'iv-nav-prev']) $(id).disabled = index === 0;
    for (const id of ['iv-next', 'iv-nav-next']) $(id).disabled = index === this.#items.length - 1;
    this.#preload(index + 1);
  }

  next() { this.show(this.#index + 1); }
  prev() { this.show(this.#index - 1); }
  first() { this.show(0); }
  last() { this.show(this.#items.length - 1); }

  #preload(index) {
    const item = this.#items[index];
    if (!item) return;
    this.#preloaded = new Image();                       // garde une référence : l'image suivante est déjà en cache à l'affichage
    this.#preloaded.src = `/raw?f=${encodeURIComponent(item.f)}`;
  }

  #loaded() {
    clearTimeout(this.#spinner);
    $('iv-loading').hidden = true;
    this.#natural = {w: this.#img.naturalWidth, h: this.#img.naturalHeight};
    this.#img.style.width = `${this.#natural.w}px`;
    this.#img.style.height = `${this.#natural.h}px`;
    this.#fit();
    this.#img.style.visibility = 'visible';
  }

  #failed() {
    clearTimeout(this.#spinner);
    $('iv-loading').hidden = true;
    $('iv-error').hidden = false;
    this.#natural = {w: 0, h: 0};
  }

  /* ----- zoom et position ----- */
  #fit() {
    this.#fitted = true;
    this.#scale = this.#fitScale;
    this.#center();
    this.#paint();
  }

  #center() {
    const {w, h} = this.#stageSize;
    this.#x = (w - this.#natural.w * this.#scale) / 2;
    this.#y = (h - this.#natural.h * this.#scale) / 2;
  }

  /** Aucun bord vide inutile : une image plus petite que la scène est centrée, une plus grande ne peut pas quitter le cadre. */
  #constrain() {
    const {w, h} = this.#stageSize;
    const iw = this.#natural.w * this.#scale;
    const ih = this.#natural.h * this.#scale;
    this.#x = iw <= w ? (w - iw) / 2 : clamp(this.#x, w - iw, 0);
    this.#y = ih <= h ? (h - ih) / 2 : clamp(this.#y, h - ih, 0);
  }

  #paint() {
    this.#img.style.transform = `translate(${this.#x}px, ${this.#y}px) scale(${this.#scale})`;
    this.#img.classList.toggle('px', this.#scale >= 3);
    const zoomed = this.#scale > this.#fitScale * 1.001;
    this.#stage.classList.toggle('zoomed', zoomed);
    $('iv-zoom').textContent = `${Math.round(this.#scale * 100)} %`;
    $('iv-zin').disabled = this.#scale >= ImageViewer.MAX_SCALE - 1e-6;
    $('iv-zout').disabled = this.#scale <= this.#minScale + 1e-6;
  }

  #relayout() {
    if (!this.#natural.w) return;
    if (this.#fitted) this.#fit();
    else { this.#constrain(); this.#paint(); }
  }

  /** Zoom de `factor` autour du point (cx, cy) de la scène (le point reste sous le doigt / le curseur). */
  zoomBy(factor, cx = this.#stageSize.w / 2, cy = this.#stageSize.h / 2) {
    if (!this.#natural.w) return;
    const target = clamp(this.#scale * factor, this.#minScale, ImageViewer.MAX_SCALE);
    const ratio = target / this.#scale;
    this.#x = cx - (cx - this.#x) * ratio;
    this.#y = cy - (cy - this.#y) * ratio;
    this.#scale = target;
    this.#fitted = Math.abs(target - this.#fitScale) < 1e-3;
    this.#constrain();
    this.#paint();
  }

  zoomIn() { this.zoomBy(ImageViewer.STEP); }
  zoomOut() { this.zoomBy(1 / ImageViewer.STEP); }
  actualSize(cx, cy) { this.zoomBy(1 / this.#scale, cx, cy); this.#fitted = false; }
  fit() { if (this.#natural.w) this.#fit(); }
  /** Bascule ajusté <-> taille réelle (bouton du niveau de zoom, double-clic) ; image plus petite que la scène : rien à changer. */
  toggleFit(cx, cy) {
    if (this.#fitted && this.#fitScale < 1) this.actualSize(cx, cy); else this.fit();
  }

  /* ----- plein écran et retour ----- */
  toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else this.#stage.requestFullscreen?.().catch(() => { /* plein écran refusé */ });
  }

  back() { location.href = cfg.back; }

  /* ----- commandes ----- */
  #bindButtons() {
    const on = (id, action) => $(id).addEventListener('click', action);
    on('iv-prev', () => this.prev());
    on('iv-next', () => this.next());
    on('iv-nav-prev', () => this.prev());
    on('iv-nav-next', () => this.next());
    on('iv-zin', () => this.zoomIn());
    on('iv-zout', () => this.zoomOut());
    on('iv-zoom', () => this.toggleFit());
    on('iv-fit', () => this.fit());
    on('iv-fs', () => this.toggleFullscreen());
    $('iv-fs').hidden = !document.fullscreenEnabled;
  }

  /** Raccourcis : une touche par action. */
  #bindKeys() {
    document.addEventListener('keydown', (event) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
      const key = event.key;
      const lower = key.length === 1 ? key.toLowerCase() : key;
      const actions = {
        ArrowLeft: () => this.prev(), p: () => this.prev(), PageUp: () => this.prev(),
        ArrowRight: () => this.next(), n: () => this.next(), PageDown: () => this.next(),
        Home: () => this.first(), End: () => this.last(),
        0: () => this.fit(), 1: () => this.actualSize(),
        f: () => this.toggleFullscreen(),
        Escape: () => { if (!document.fullscreenElement) this.back(); },
        Backspace: () => this.back(), l: () => this.back(),
      };
      const zoom = ImageViewer.ZOOM_KEYS[key];
      const action = zoom ? (zoom > 0 ? () => this.zoomIn() : () => this.zoomOut()) : actions[lower];
      if (!action) return;
      event.preventDefault();
      action();
    });
  }

  /** Souris, doigt, stylet : glisser pour déplacer, pincer pour zoomer, balayer pour changer d'image, molette et double-clic. */
  #bindPointer() {
    const stage = this.#stage;
    const local = (event) => { const r = stage.getBoundingClientRect(); return {x: event.clientX - r.left, y: event.clientY - r.top}; };
    stage.addEventListener('wheel', (event) => {
      event.preventDefault();
      const {x, y} = local(event);
      this.zoomBy(event.deltaY < 0 ? ImageViewer.STEP : 1 / ImageViewer.STEP, x, y);
    }, {passive: false});
    stage.addEventListener('dblclick', (event) => {
      if (event.target.closest('.iv-nav')) return;
      const {x, y} = local(event);
      this.toggleFit(x, y);
    });
    stage.addEventListener('pointerdown', (event) => {
      if (event.target.closest('.iv-nav') || (event.pointerType === 'mouse' && event.button !== 0)) return;
      stage.setPointerCapture(event.pointerId);
      this.#pointers.set(event.pointerId, local(event));
      this.#startGesture(event);
    });
    stage.addEventListener('pointermove', (event) => {
      if (!this.#pointers.has(event.pointerId)) return;
      this.#pointers.set(event.pointerId, local(event));
      this.#moveGesture();
    });
    const release = (event) => {
      if (!this.#pointers.has(event.pointerId)) return;
      this.#endGesture(event);
      this.#pointers.delete(event.pointerId);
      stage.classList.remove('panning');
      if (this.#pointers.size) this.#startGesture(event);   // un doigt reste posé : on repart de sa position
    };
    stage.addEventListener('pointerup', release);
    stage.addEventListener('pointercancel', (event) => { this.#gesture = null; release(event); });
  }

  #startGesture(event) {
    const points = [...this.#pointers.values()];
    if (points.length >= 2) {
      const [a, b] = points;
      this.#gesture = {kind: 'pinch', distance: Math.hypot(a.x - b.x, a.y - b.y) || 1};
    } else {
      const zoomed = this.#scale > this.#fitScale * 1.001;
      const kind = zoomed ? 'pan' : event.pointerType === 'mouse' ? 'none' : 'swipe';   // à la souris : boutons et clavier, pas de balayage
      this.#gesture = {kind, start: {...points[0]}, last: {...points[0]}, at: event.timeStamp};
      if (zoomed) this.#stage.classList.add('panning');
    }
  }

  #moveGesture() {
    const gesture = this.#gesture;
    if (!gesture) return;
    const points = [...this.#pointers.values()];
    if (gesture.kind === 'pinch' && points.length >= 2) {
      const [a, b] = points;
      const distance = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      this.zoomBy(distance / gesture.distance, (a.x + b.x) / 2, (a.y + b.y) / 2);
      gesture.distance = distance;
    } else if (gesture.kind === 'pan') {
      const point = points[0];
      this.#x += point.x - gesture.last.x;
      this.#y += point.y - gesture.last.y;
      gesture.last = {...point};
      this.#fitted = false;
      this.#constrain();
      this.#paint();
    }
  }

  #endGesture(event) {
    const gesture = this.#gesture;
    this.#gesture = null;
    if (gesture?.kind !== 'swipe') return;
    const point = this.#pointers.get(event.pointerId) ?? gesture.last;
    const dx = point.x - gesture.start.x;
    const dy = point.y - gesture.start.y;
    if (Math.abs(dx) >= ImageViewer.SWIPE_MIN && Math.abs(dx) > 1.5 * Math.abs(dy) && event.timeStamp - gesture.at < 700) {
      if (dx < 0) this.next(); else this.prev();
    }
  }
}

new ImageViewer();
