/**
 * Lecteur multimédia local : lit des fichiers vidéo et audio de l'appareil (sélection ou glisser-déposer).
 * Le navigateur lit le fichier directement depuis le disque (URL d'objet) : rien n'est copié ni envoyé au serveur,
 * et la lecture démarre sans attendre, même pour un gros fichier.
 */
class LocalPlayer {
  static VIDEO_EXT = new Set(['mp4', 'm4v', 'webm', 'mkv', 'mov', 'avi', 'ogv', 'ts', '3gp']);
  static AUDIO_EXT = new Set(['mp3', 'm4a', 'aac', 'flac', 'wav', 'ogg', 'oga', 'opus', 'mka', 'weba']);

  #queue = [];          // { file, kind: 'video' | 'audio' }
  #index = -1;
  #url = null;          // URL d'objet du média en cours (libérée à chaque changement)
  #dragDepth = 0;

  constructor() {
    this.stage = $('mp-stage');
    this.video = $('mp-video');
    this.audio = $('mp-audio');
    this.audioBox = $('mp-audio-box');
    this.audioTitle = $('mp-audio-title');
    this.drop = $('mp-drop');
    this.bar = $('mp-bar');
    this.now = $('mp-now');
    this.list = $('mp-list');
    this.error = $('mp-error');
    this.input = $('mp-input');
    this.#bind();
  }

  static kindOf(file) {
    if (file.type.startsWith('video/')) return 'video';
    if (file.type.startsWith('audio/')) return 'audio';
    const ext = file.name.split('.').pop().toLowerCase();
    if (LocalPlayer.VIDEO_EXT.has(ext)) return 'video';
    if (LocalPlayer.AUDIO_EXT.has(ext)) return 'audio';
    return null;
  }

  get current() { return this.#queue[this.#index] ?? null; }
  get media() { return this.current?.kind === 'audio' ? this.audio : this.video; }

  #bind() {
    const openPicker = () => this.input.click();
    $('mp-pick').addEventListener('click', (event) => { event.stopPropagation(); openPicker(); });
    $('mp-add').addEventListener('click', openPicker);
    this.drop.addEventListener('click', openPicker);
    this.drop.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openPicker(); }
    });
    this.input.addEventListener('change', () => { this.add([...this.input.files]); this.input.value = ''; });
    $('mp-prev').addEventListener('click', () => this.step(-1));
    $('mp-next').addEventListener('click', () => this.step(1));
    $('mp-clear').addEventListener('click', () => this.clear());

    for (const media of [this.video, this.audio]) {
      media.addEventListener('ended', () => { if (this.#index < this.#queue.length - 1) this.step(1); });
      media.addEventListener('error', () => this.#showError(media));
    }

    // Glisser-déposer : toute la page accepte un fichier (sinon le navigateur ouvrirait le fichier et quitterait la page).
    const hasFiles = (event) => [...(event.dataTransfer?.types ?? [])].includes('Files');
    window.addEventListener('dragenter', (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      this.#dragDepth += 1;
      this.stage.classList.add('dragging');
    });
    window.addEventListener('dragover', (event) => { if (hasFiles(event)) event.preventDefault(); });
    window.addEventListener('dragleave', (event) => {
      if (!hasFiles(event)) return;
      this.#dragDepth = Math.max(0, this.#dragDepth - 1);
      if (this.#dragDepth === 0) this.stage.classList.remove('dragging');
    });
    window.addEventListener('drop', (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      this.#dragDepth = 0;
      this.stage.classList.remove('dragging');
      this.add([...event.dataTransfer.files]);
      this.stage.scrollIntoView({behavior: 'smooth', block: 'center'});
    });
    window.addEventListener('pagehide', () => this.#release());

    if ('mediaSession' in navigator) {   // commandes de l'écran de verrouillage / du clavier multimédia
      navigator.mediaSession.setActionHandler('previoustrack', () => this.step(-1));
      navigator.mediaSession.setActionHandler('nexttrack', () => this.step(1));
    }
  }

  /** Ajoute des fichiers à la liste ; lance le premier s'il n'y a pas de lecture en cours. */
  add(files) {
    const accepted = [];
    let rejected = 0;
    for (const file of files) {
      const kind = LocalPlayer.kindOf(file);
      if (kind) accepted.push({file, kind}); else rejected += 1;
    }
    this.#hideError();
    if (accepted.length) {
      const wasEmpty = this.#queue.length === 0;
      this.#queue.push(...accepted);
      if (wasEmpty) this.play(0); else this.#render();
    }
    // après le démarrage de la lecture, qui efface les anciens messages
    if (rejected) this.#setError(`${rejected} fichier${rejected > 1 ? 's' : ''} ignoré${rejected > 1 ? 's' : ''} : ni vidéo ni audio.`);
  }

  play(index) {
    const entry = this.#queue[index];
    if (!entry) return;
    this.#release();
    this.#index = index;
    this.#hideError();
    this.#url = URL.createObjectURL(entry.file);
    const isAudio = entry.kind === 'audio';
    const [active, idle] = isAudio ? [this.audio, this.video] : [this.video, this.audio];
    idle.removeAttribute('src');
    idle.load();
    active.src = this.#url;
    this.video.hidden = isAudio;
    this.audioBox.hidden = !isAudio;
    this.drop.hidden = true;
    this.audioTitle.textContent = entry.file.name;
    active.play().catch(() => { /* lecture automatique refusée : les commandes restent disponibles */ });
    this.#render();
    this.#updateSession(entry);
  }

  step(delta) {
    const next = this.#index + delta;
    if (next >= 0 && next < this.#queue.length) this.play(next);
  }

  remove(index) {
    const wasCurrent = index === this.#index;
    this.#queue.splice(index, 1);
    if (!this.#queue.length) { this.clear(); return; }
    if (wasCurrent) {
      this.#index = -1;
      this.play(Math.min(index, this.#queue.length - 1));
    } else {
      if (index < this.#index) this.#index -= 1;
      this.#render();
    }
  }

  clear() {
    this.#release();
    this.#queue = [];
    this.#index = -1;
    for (const media of [this.video, this.audio]) { media.removeAttribute('src'); media.load(); }
    this.video.hidden = true;
    this.audioBox.hidden = true;
    this.drop.hidden = false;
    this.#hideError();
    this.#render();
  }

  #release() {
    if (this.#url) { URL.revokeObjectURL(this.#url); this.#url = null; }
  }

  #render() {
    const active = this.#queue.length > 0;
    this.bar.hidden = !active;
    this.list.hidden = this.#queue.length < 2;
    this.list.textContent = '';
    if (!active) return;
    this.now.textContent = `${this.#index + 1} / ${this.#queue.length} · ${this.current.file.name}`;
    $('mp-prev').disabled = this.#index <= 0;
    $('mp-next').disabled = this.#index >= this.#queue.length - 1;
    this.#queue.forEach(({file, kind}, i) => {
      const row = el('div', `mp-row${i === this.#index ? ' cur' : ''}`);
      const play = el('button', 'mp-row-main');
      play.type = 'button';
      play.append(el('span', 'mp-row-name', file.name), el('span', 'mp-row-meta', `${kind === 'video' ? 'Vidéo' : 'Audio'} · ${formatSize(file.size)}`));
      play.addEventListener('click', () => { if (i !== this.#index) this.play(i); });
      const del = el('button', 'mp-row-del', '×');
      del.type = 'button';
      del.title = 'Retirer de la liste';
      del.setAttribute('aria-label', `Retirer ${file.name} de la liste`);
      del.addEventListener('click', () => this.remove(i));
      row.append(play, del);
      this.list.appendChild(row);
    });
  }

  #updateSession(entry) {
    if ('mediaSession' in navigator && 'MediaMetadata' in window) {
      navigator.mediaSession.metadata = new MediaMetadata({title: entry.file.name});
    }
  }

  #showError(media) {
    if (!this.current || media !== this.media) return;   // l'élément inactif vidé n'est pas une erreur de lecture
    this.#setError(`Lecture impossible pour « ${this.current.file.name} » : format ou codec non pris en charge par ce navigateur.`);
  }

  #setError(message) { this.error.textContent = message; this.error.hidden = false; }
  #hideError() { this.error.hidden = true; this.error.textContent = ''; }
}
