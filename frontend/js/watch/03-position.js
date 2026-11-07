
/** Reprise de la lecture : dernière position de CET appareil, mémorisée par le serveur (voir progress.js). */
class ResumeTracker {
  static SAVE_EVERY = 5000;                               // ms entre deux enregistrements pendant la lecture

  #rel = items[index].f;
  #resume = null;                                         // position mémorisée {t, d}
  #fetched = false;
  #resumed = false;                                       // à partir d'ici seulement, on peut enregistrer sans écraser la position mémorisée
  #lastSave = 0;

  constructor() {
    this.#load();
    video.addEventListener('loadedmetadata', () => this.#tryResume());
    video.addEventListener('timeupdate', () => {
      if (Date.now() - this.#lastSave > ResumeTracker.SAVE_EVERY) { this.#lastSave = Date.now(); this.save(); }
    });
    video.addEventListener('pause', () => this.save());
    video.addEventListener('seeked', () => { if (video.paused) this.save(); });
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') this.save(true); });
    window.addEventListener('pagehide', () => this.save(true));
  }

  async #load() {
    const legacyKey = `vl:pos:${cfg.key}`;                // ancienne position gardée par ce navigateur : reprise une dernière fois, puis oubliée
    const saved = await Progress.get(this.#rel);
    if (saved?.t > 0) {
      this.#resume = saved;
    } else {
      try {
        const old = JSON.parse(localStorage.getItem(legacyKey));
        if (old?.t > 3) this.#resume = {t: old.t, d: old.d || 0};
      } catch { /* pas d'ancienne position */ }
    }
    try { localStorage.removeItem(legacyKey); } catch { /* rien à nettoyer */ }
    this.#fetched = true;
    this.#tryResume();
  }

  #tryResume() {
    if (this.#resumed || !this.#fetched || !video.duration || Number.isNaN(video.duration)) return;
    this.#resumed = true;
    const position = this.#resume?.t;
    if (position > 3 && position < video.duration - 8 && video.currentTime < 3) {
      video.currentTime = position;
      say(`Reprise à ${Progress.fmt(position)}.`);
    }
  }

  save(keepalive = false) {
    if (!this.#resumed || !video.duration || video.ended) return;
    if (video.currentTime > video.duration - 8) Progress.done(this.#rel);      // presque fini : on repartira du début
    else Progress.save(this.#rel, video.currentTime, video.duration, keepalive);
  }

  /** Lue jusqu'au bout : on oublie la position. */
  finish() { Progress.done(this.#rel); }
}
