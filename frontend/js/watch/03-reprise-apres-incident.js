
  /** Garde-fou de la lecture : retient la dernière bonne position, repart de là si le flux se coupe (réseau, sauts rapprochés…)
      et empêche « lecture » de relancer la vidéo à 0:00 après un arrêt inattendu. */
  class PlaybackGuard {
    static STALL_LIMIT = 20000;                             // ms d'attente de données avant de recharger la vidéo
    static MAX_RETRIES = 3;                                 // rechargements d'affilée avant d'abandonner

    #good = 0;                                              // dernière position où la lecture était réellement en cours (ou visée par un saut)
    #wantPlay = false;                                      // la lecture était voulue (pas mise en pause par l'utilisateur)
    #finished = false;                                      // la vidéo est allée jusqu'au bout : « lecture » la relance alors volontairement à 0:00
    #everLoaded = false;                                    // les métadonnées sont déjà arrivées une fois : toute erreur ensuite est une coupure en cours de route
    #recovering = false;
    #restore = null;                                        // {position, play} : à rejoindre dès que la vidéo rechargée est prête
    #retries = 0;
    #recoveredAt = 0;
    #stallTimer = 0;

    constructor() {
      const on = (type, handler) => video.addEventListener(type, handler);
      on('loadedmetadata', () => this.#onMetadata());
      on('timeupdate', () => this.#onTime());
      on('seeking', () => { if (!this.#recovering && Number.isFinite(video.currentTime)) this.#good = video.currentTime; });   // un saut raté reprend à sa destination
      on('seeked', () => this.#clearStall());
      on('canplay', () => this.#clearStall());
      on('playing', () => { this.#wantPlay = true; this.#clearStall(); });
      on('play', () => this.#onPlay());
      on('pause', () => { this.#clearStall(); if (!video.ended && !this.#recovering) this.#wantPlay = false; });
      on('waiting', () => this.#armStall());
      on('ended', () => { this.#finished = true; this.#clearStall(); });
      on('error', () => this.#onError());
    }

    #onMetadata() {
      this.#everLoaded = true;
      const restore = this.#restore;
      if (!restore) return;
      this.#restore = null;
      this.#recovering = false;
      if (restore.position > 0 && restore.position < video.duration - 0.5) video.currentTime = restore.position;
      if (restore.play) play();
    }

    #onTime() {
      if (this.#recovering || video.seeking || video.readyState < 2) return;
      this.#good = video.currentTime;
      if (this.#retries && video.currentTime > this.#recoveredAt + 10) this.#retries = 0;     // la lecture est de nouveau stable
    }

    /** « Lecture » : si la vidéo est revenue à 0:00 sans que personne ne l'ait demandé, on repart de la dernière bonne position. */
    #onPlay() {
      this.#wantPlay = true;
      const lost = !this.#finished && !this.#recovering && this.#good > 5 && video.currentTime < 1;
      this.#finished = false;
      if (!lost) return;
      video.currentTime = this.#good;
      say(`Reprise à ${Progress.fmt(this.#good)}.`);
    }

    #onError() {
      if (video.error?.code === 4 && !this.#everLoaded) return;   // format non pris en charge dès le départ : un rechargement n'y changerait rien
      this.#recover('Lecture interrompue.');
    }

    /** Aucune donnée n'arrive alors que la lecture est censée avancer : on finit par recharger la vidéo. */
    #armStall() {
      if (this.#stallTimer || video.paused) return;
      this.#stallTimer = setTimeout(() => {
        this.#stallTimer = 0;
        if (!video.paused && video.readyState < 3) this.#recover('Connexion interrompue.');
      }, PlaybackGuard.STALL_LIMIT);
    }

    #clearStall() {
      clearTimeout(this.#stallTimer);
      this.#stallTimer = 0;
    }

    /** Recharge la vidéo, rejoint la dernière bonne position et relance la lecture si elle était en cours. */
    #recover(reason) {
      this.#clearStall();
      if (this.#retries >= PlaybackGuard.MAX_RETRIES) {
        this.#recovering = false;
        this.#restore = null;
        say(`${reason} Recharge la page pour reprendre.`);
        return;
      }
      this.#retries++;
      const wantPlay = this.#recovering ? this.#restore?.play : this.#wantPlay;
      this.#recovering = true;
      this.#recoveredAt = this.#good;
      this.#restore = {position: this.#good, play: !!wantPlay};
      say(`${reason} Reprise à ${Progress.fmt(this.#good)}…`);
      video.autoplay = !!wantPlay;                              // sans cela, la lecture démarrerait seule même si elle était en pause
      video.load();
    }
  }
