
  /** Position de lecture de CHAQUE piste : mémorisée pendant la visite et par le serveur (voir progress.js), reprise dès qu'on revient sur la piste. */
  class PositionKeeper {
    static SAVE_EVERY = 5000;                                // ms entre deux enregistrements pendant la lecture
    static MIN = 3;                                          // s : avant, la piste « vient de commencer » (rien à reprendre)
    static END_MARGIN = 5;                                   // s : à moins de ça de la fin, la piste est « terminée »

    #rel = null;                                             // piste chargée dans le lecteur
    #memory = new Map();                                     // piste -> position où on l'a quittée pendant cette visite (0 = repartir du début) ; prime sur le serveur
    #target = null;                                          // position à rejoindre pour la piste chargée
    #known = false;                                          // la position à reprendre est connue (mémoire ou serveur)
    #metadata = false;                                       // les métadonnées de la piste chargée sont arrivées
    #applied = false;                                        // la reprise est tranchée : tant qu'elle ne l'est pas, on n'enregistre rien (la position mémorisée serait écrasée)
    #wanted = null;                                          // position demandée au lecteur, à revérifier quand il peut lire (certains navigateurs ignorent le saut trop tôt)
    #token = 0;                                              // identifie la piste chargée : une réponse du serveur arrivée trop tard est ignorée
    #first = true;                                           // première piste de la page : ancien stockage du navigateur à reprendre
    #lastSave = 0;

    /** Une piste va être chargée : la précédente est mémorisée, puis on cherche où reprendre la nouvelle. À appeler AVANT de changer `audio.src`. */
    begin(index) {
      this.#leave();
      const rel = tracks[index].f;
      const token = ++this.#token;
      this.#rel = rel;
      this.#target = null;
      this.#known = this.#metadata = this.#applied = false;
      this.#wanted = null;
      if (this.#memory.has(rel)) {                           // déjà écoutée pendant cette visite : la mémoire est plus fraîche que le serveur
        this.#target = this.#memory.get(rel);
        this.#known = true;
      } else {
        this.#fetch(rel, token);
      }
    }

    /** Position mémorisée par le serveur pour cet appareil (ou, une dernière fois, l'ancien stockage du navigateur pour la toute première piste). */
    async #fetch(rel, token) {
      const first = this.#first;
      this.#first = false;
      const legacyKey = `al:pos:${cfg.key}:${rel}`;
      let target = (await Progress.get(rel))?.t ?? 0;
      if (first) {
        if (!(target > 0)) {
          try {
            const old = JSON.parse(localStorage.getItem(legacyKey));
            if (old?.t > PositionKeeper.MIN) target = old.t;
          } catch { /* pas d'ancienne position */ }
        }
        try { localStorage.removeItem(legacyKey); } catch { /* rien à nettoyer */ }
      }
      if (token !== this.#token) return;                     // une autre piste a été choisie entre-temps
      this.#target = target > 0 ? target : null;
      this.#known = true;
      this.#apply();
    }

    /** À appeler quand les métadonnées de la piste chargée sont arrivées. */
    onMetadata() {
      this.#metadata = true;
      this.#apply();
    }

    /** Rejoint la position à reprendre, dès qu'elle est connue ET que la piste est prête. */
    #apply() {
      if (this.#applied || !this.#known || !this.#metadata || !isReady()) return;
      this.#applied = true;
      const target = this.#target;
      this.#target = null;
      if (target > PositionKeeper.MIN && target < audio.duration - PositionKeeper.END_MARGIN && audio.currentTime < PositionKeeper.MIN) {
        this.#wanted = target;
        audio.currentTime = target;
        say(`Reprise à ${Progress.fmt(target)}.`);
      }
    }

    /** Le lecteur peut lire : si le saut a été ignoré (certains navigateurs mobiles), on le refait une fois. */
    confirm() {
      const wanted = this.#wanted;
      this.#wanted = null;
      if (wanted != null && audio.currentTime < wanted - 2 && isReady()) audio.currentTime = wanted;
    }

    /** Piste quittée : on garde où elle en était (ou 0 si elle vient de commencer / est presque finie) et on l'enregistre côté serveur. */
    #leave() {
      const rel = this.#rel;
      if (!rel) return;
      if (this.#applied && isReady()) {
        this.save(true);
        const t = audio.currentTime;
        const resumable = !audio.ended && t > PositionKeeper.MIN && t < audio.duration - PositionKeeper.END_MARGIN;
        this.#memory.set(rel, resumable ? t : 0);
      } else if (this.#known && this.#target != null) {      // quittée avant d'avoir pu reprendre : on garde la position qu'on voulait rejoindre
        this.#memory.set(rel, this.#target);
      }
    }

    save(keepalive = false) {
      if (!this.#applied || !this.#rel || !isReady() || audio.ended) return;
      if (audio.currentTime > audio.duration - PositionKeeper.END_MARGIN) Progress.done(this.#rel);   // presque fini : on repartira du début
      else Progress.save(this.#rel, audio.currentTime, audio.duration, keepalive);
    }

    /** Appelé pendant la lecture : enregistre au plus toutes les 5 s. */
    tick() {
      if (Date.now() - this.#lastSave > PositionKeeper.SAVE_EVERY) { this.#lastSave = Date.now(); this.save(); }
    }

    /** Piste lue jusqu'au bout : on oublie sa position, ici comme sur le serveur. */
    finish() {
      if (!this.#rel) return;
      this.#memory.set(this.#rel, 0);
      Progress.done(this.#rel);
    }
  }
