
/** Garde-fou de la lecture : retient la dernière bonne position, repart de là si le flux se coupe (réseau, sauts rapprochés…)
    et empêche « lecture » de relancer la vidéo à 0:00 après un arrêt inattendu.
    Une coupure du réseau n'est jamais définitive : les rechargements se poursuivent à intervalles croissants, et reprennent
    aussitôt au retour de la connexion ou de la page (événement « online », onglet de nouveau visible, clic sur la vidéo). */
class PlaybackGuard {
  static STALL_LIMIT = 30000;                             // ms SANS AUCUNE donnée reçue avant de recharger la vidéo (un flux lent mais vivant n'est jamais rechargé)
  static IDLE_ONLINE = 1500;                              // ms de silence du flux à partir desquels un retour du réseau relance la vidéo
  static IDLE_VISIBLE = 4000;                             // idem pour un retour sur la page
  static RETRY_DELAYS = [0, 2000, 5000, 10000, 15000];    // ms avant chaque rechargement ; le dernier délai se répète tant que la vidéo ne repart pas
  static DECODE_BACKOFF = [0, 5, 15];                     // erreur de décodage : 1er essai à la même position, puis 5 s plus tôt, puis 15 s plus tôt, puis depuis 0:00
                                                          // (un saut vers une position précise peut échouer alors que la lecture continue passe : on repart d'un point sûr)

  onFatal = null;                                         // appelé avec un message quand plus rien n'est tenté (l'interface affiche alors l'écran d'erreur)
  #good = 0;                                              // dernière position où la lecture était réellement en cours (ou visée par un saut)
  #wantPlay = false;                                      // la lecture était voulue (pas mise en pause par l'utilisateur)
  #finished = false;                                      // la vidéo est allée jusqu'au bout : « lecture » la relance alors volontairement à 0:00
  #everLoaded = false;                                    // les métadonnées sont déjà arrivées une fois : toute erreur ensuite est une coupure en cours de route
  #recovering = false;
  #restore = null;                                        // {position, play} : à rejoindre dès que la vidéo rechargée est prête
  #retries = 0;
  #recoveredAt = 0;
  #stallTimer = 0;
  #retryTimer = 0;                                        // prochain rechargement programmé
  #lastData = Date.now();                                 // dernier signe de vie du flux (données reçues, lecture qui avance)

  constructor() {
    const on = (type, handler) => video.addEventListener(type, handler);
    on('loadedmetadata', () => this.#onMetadata());
    on('timeupdate', () => this.#onTime());
    on('seeking', () => { if (!this.#recovering && Number.isFinite(video.currentTime)) this.#good = video.currentTime; });   // un saut raté reprend à sa destination
    on('seeked', () => { this.#alive(); this.#clearStall(); });
    on('canplay', () => { this.#alive(); this.#clearStall(); });
    on('playing', () => { this.#wantPlay = true; this.#alive(); this.#clearStall(); });
    for (const type of ['progress', 'loadstart', 'loadeddata', 'durationchange']) on(type, () => this.#alive());      // des données arrivent : le flux est vivant, même lentement
    on('play', () => this.#onPlay());
    on('pause', () => { this.#clearStall(); if (!video.ended && !this.#recovering) this.#wantPlay = false; });
    on('waiting', () => this.#armStall());
    on('ended', () => { this.#finished = true; this.#clearStall(); });
    on('error', () => this.#onError());
    on('pointerdown', () => { if (video.error) this.#retryNow(true); });        // lecteur resté en erreur : un clic sur la vidéo relance tout de suite

    // retour du réseau ou de la page : on ne laisse pas la vidéo bloquée là où la coupure l'a laissée
    window.addEventListener('online', () => this.#checkAlive(PlaybackGuard.IDLE_ONLINE));
    window.addEventListener('pageshow', () => this.#checkAlive(PlaybackGuard.IDLE_VISIBLE));
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') this.#checkAlive(PlaybackGuard.IDLE_VISIBLE); });
  }

  #alive() { this.#lastData = Date.now(); }

  /** Autre vidéo chargée dans le même lecteur : on oublie tout de la précédente (position, reprises en cours, erreurs). */
  reset() {
    this.#clearStall();
    clearTimeout(this.#retryTimer);
    this.#retryTimer = 0;
    this.#good = 0;
    this.#wantPlay = true;                                  // la nouvelle vidéo démarre d'elle-même
    this.#finished = false;
    this.#everLoaded = false;
    this.#recovering = false;
    this.#restore = null;
    this.#retries = 0;
    this.#recoveredAt = 0;
    this.#alive();
  }

  #onMetadata() {
    this.#everLoaded = true;
    this.#alive();
    const restore = this.#restore;
    if (!restore) return;
    this.#restore = null;
    this.#recovering = false;
    clearTimeout(this.#retryTimer);
    this.#retryTimer = 0;
    if (restore.position > 0 && restore.position < video.duration - 0.5) video.currentTime = restore.position;
    if (restore.play) play();
  }

  #onTime() {
    if (this.#recovering || video.seeking || video.readyState < 2) return;
    this.#good = video.currentTime;
    this.#alive();
    if (this.#retries && video.currentTime > this.#recoveredAt + 10) this.#retries = 0;     // la lecture est de nouveau stable
  }

  /** « Lecture » : si la vidéo est revenue à 0:00 sans que personne ne l'ait demandé, on repart de la dernière bonne position. */
  #onPlay() {
    this.#wantPlay = true;
    if (this.#restore) this.#restore.play = true;                  // « lecture » demandée pendant une reprise : elle repartira d'elle-même
    const lost = !this.#finished && !this.#recovering && this.#good > 5 && video.currentTime < 1;
    this.#finished = false;
    if (!lost) return;
    video.currentTime = this.#good;
    say(`Reprise à ${Progress.fmt(this.#good)}.`);
  }

  #onError() {
    console.warn(`Lecture : erreur ${video.error?.code} (${video.error?.message || 'sans détail'}) à ${Progress.fmt(video.currentTime || 0)}`);   // pour le diagnostic (console du navigateur)
    if (video.error?.code === 4 && !this.#everLoaded && navigator.onLine !== false) return;   // format non pris en charge dès le départ : un rechargement n'y changerait rien
    this.#recover('Lecture interrompue.');
  }

  /** Le flux ne donne plus signe de vie depuis `idle` ms alors que la lecture est voulue, ou le lecteur est en erreur. */
  #isStuck(idle) {
    if (video.error) return true;
    return this.#wantPlay && !video.paused && !video.ended && video.readyState < 3 && Date.now() - this.#lastData > idle;
  }

  /** Retour du réseau ou de la page : si la lecture est réellement bloquée, on relance sans attendre.
      Une vidéo qui charge encore (même lentement) ou qui joue normalement n'est jamais rechargée : ce serait repartir de zéro. */
  #checkAlive(idle) {
    if (this.#recovering) {
      if (this.#retryTimer || video.error || Date.now() - this.#lastData > idle) this.#retryNow();    // attente entre deux essais, ou rechargement resté sans réponse
      return;
    }
    if (this.#isStuck(idle)) this.#retryNow();
  }

  /** La lecture attend des données : on ne recharge qu'après un long silence complet du flux, pas tant qu'il avance, même lentement. */
  #armStall() {
    if (this.#stallTimer || video.paused) return;
    this.#alive();
    this.#watchStall(PlaybackGuard.STALL_LIMIT);
  }

  #watchStall(wait) {
    this.#stallTimer = setTimeout(() => {
      this.#stallTimer = 0;
      if (video.paused || video.readyState >= 3) return;
      const silence = Date.now() - this.#lastData;
      if (silence < PlaybackGuard.STALL_LIMIT) { this.#watchStall(PlaybackGuard.STALL_LIMIT - silence); return; }     // des données sont arrivées entre-temps : on attend encore
      this.#recover('Connexion interrompue.');
    }, wait);
  }

  #clearStall() {
    clearTimeout(this.#stallTimer);
    this.#stallTimer = 0;
  }

  /** Relance immédiatement la reprise (réseau revenu, page de nouveau visible) ; `play` : l'utilisateur veut lire la vidéo. */
  #retryNow(play = false) {
    this.#retries = 0;
    this.#recover('Connexion rétablie.', true);
    if (play && this.#restore) this.#restore.play = true;
  }

  /** Recharge la vidéo, rejoint la dernière bonne position et relance la lecture si elle était en cours.
      Si le rechargement échoue (réseau encore coupé), l'erreur qui suit reprogramme un nouvel essai, un peu plus tard :
      on n'abandonne jamais, la lecture repart d'elle-même dès que le serveur répond de nouveau. */
  #recover(reason, now = false) {
    this.#clearStall();
    const decode = video.error?.code === 3 && navigator.onLine !== false;
    if (decode && this.#retries > PlaybackGuard.DECODE_BACKOFF.length) {
      this.#giveUp();                                        // même depuis le début : le fichier lui-même est en cause
      return;
    }
    if (this.#retryTimer && !now) return;                    // un rechargement est déjà programmé
    clearTimeout(this.#retryTimer);
    this.#retryTimer = 0;
    if (!this.#recovering) {                                 // première coupure : on retient où on en était (et si la lecture était voulue)
      this.#recovering = true;
      this.#recoveredAt = this.#good;
      this.#restore = {position: this.#good, play: this.#wantPlay};
    }
    if (decode && this.#retries > 0 && this.#restore) {
      this.#restore.position = this.#fallbackPosition(this.#retries);
      this.#good = this.#restore.position;                   // repli voulu : sans cela, « lecture » croirait la position perdue et ramènerait à l'endroit fautif
    }
    const delays = PlaybackGuard.RETRY_DELAYS;
    const delay = now ? 0 : delays[Math.min(this.#retries, delays.length - 1)];
    this.#retries++;
    say(`${reason} Reprise à ${Progress.fmt(this.#restore?.position ?? this.#good)}…`);
    this.#retryTimer = setTimeout(() => this.#reload(), delay);
  }

  /** Position de repli après `step` échecs de décodage : de plus en plus tôt, puis le début. Au début, la position mémorisée par le serveur
      est effacée : sinon chaque rechargement de la page (même « hard refresh ») retournerait se heurter au même endroit. */
  #fallbackPosition(step) {
    const back = PlaybackGuard.DECODE_BACKOFF[step];
    if (back !== undefined && this.#recoveredAt - back > 0) return this.#recoveredAt - back;
    Progress.done(items[index].f);
    return 0;
  }

  /** Plus rien à tenter : on s'arrête là, sans rechargements sans fin. Un clic sur la vidéo réessaie, depuis le début. */
  #giveUp() {
    this.#recovering = false;
    this.#restore = null;
    this.#good = 0;
    Progress.done(items[index].f);                            // la position mémorisée est oubliée : le prochain chargement repart de 0:00
    say('Cette vidéo ne peut pas être décodée par ce navigateur, même depuis le début. Clique sur la vidéo pour réessayer.');
    this.onFatal?.('Cette vidéo ne peut pas être décodée par ce navigateur.');
  }

  #reload() {
    this.#retryTimer = 0;
    if (!this.#recovering) return;
    video.autoplay = !!this.#restore?.play;                  // sans cela, la lecture démarrerait seule même si elle était en pause
    video.load();
  }
}
