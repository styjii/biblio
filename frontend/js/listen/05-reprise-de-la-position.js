
  /** Reprise de la lecture : dernière position de CET appareil pour la piste ouverte au chargement, mémorisée par le serveur (voir progress.js). */
  class PositionKeeper {
    static SAVE_EVERY = 5000;                                // ms entre deux enregistrements pendant la lecture

    #rel = tracks[cfg.start].f;                              // piste dont on enregistre la position
    #firstIndex = cfg.start;                                 // seule piste reprise : celle ouverte au chargement de la page
    #resume = null;
    #fetched = false;
    #pending = true;                                         // tant que la reprise n'est pas tranchée, on n'enregistre rien (la position mémorisée serait écrasée)
    #lastSave = 0;

    constructor() {
      this.#load();
    }

    async #load() {
      const legacyKey = `al:pos:${cfg.key}:${this.#rel}`;    // ancien stockage dans le navigateur : repris une dernière fois, puis oublié
      const saved = await Progress.get(this.#rel);
      if (saved?.t > 0) {
        this.#resume = saved;
      } else {
        try {
          const old = JSON.parse(localStorage.getItem(legacyKey));
          if (old?.t > 3) this.#resume = {t: old.t, d: 0};
        } catch { /* pas d'ancienne position */ }
      }
      try { localStorage.removeItem(legacyKey); } catch { /* rien à nettoyer */ }
      this.#fetched = true;
      this.tryResume(cfg.start);
    }

    /** À appeler quand les métadonnées de la piste `index` sont chargées. */
    tryResume(index) {
      if (!this.#pending || !this.#fetched || !isReady()) return;
      this.#pending = false;
      const position = this.#resume?.t;
      if (index === this.#firstIndex && position > 3 && position < audio.duration - 5 && audio.currentTime < 3) {
        audio.currentTime = position;
        say(`Reprise à ${Progress.fmt(position)}.`);
      }
    }

    /** Une autre piste est chargée : l'ancienne est enregistrée d'abord. */
    switchTo(rel) {
      this.save(true);
      this.#rel = rel;
    }

    save(keepalive = false) {
      if (this.#pending || !this.#rel || !isReady() || audio.ended) return;
      if (audio.currentTime > audio.duration - 5) Progress.done(this.#rel);      // presque fini : on repartira du début
      else Progress.save(this.#rel, audio.currentTime, audio.duration, keepalive);
    }

    /** Appelé pendant la lecture : enregistre au plus toutes les 5 s. */
    tick() {
      if (Date.now() - this.#lastSave > PositionKeeper.SAVE_EVERY) { this.#lastSave = Date.now(); this.save(); }
    }

    /** Piste lue jusqu'au bout : on oublie sa position. */
    finish() { if (this.#rel) Progress.done(this.#rel); }
  }
