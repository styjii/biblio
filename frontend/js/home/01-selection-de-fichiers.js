/**
 * Accueil : modes Vidéo / Audio, choix et dépôt de fichiers pour le lecteur multimédia local.
 * Le lecteur lui-même est celui de la page de lecture vidéo (frontend/js/watch/, mode « local ») : ce script ne fait
 * que lui transmettre les fichiers de l'appareil et le mode choisi (window.BiblioLocal), refléter son état (onglets, compteurs,
 * zone de dépôt tant que le mode affiché est vide) et amener la vue sur le lecteur quand l'utilisateur le demande.
 */
class LocalPicker {
  static MODES = {
    video: {name: 'Vidéo', noun: 'vidéo', title: 'Glisse une vidéo ici', pick: 'Choisir des vidéos', label: 'Choisir ou déposer un fichier vidéo',
      accept: 'video/*,.mkv,.avi,.mov,.ts,.m4v,.ogv,.3gp'},
    audio: {name: 'Audio', noun: 'audio', title: 'Glisse un son ici', pick: 'Choisir des sons', label: 'Choisir ou déposer un fichier audio',
      accept: 'audio/*,.mp3,.m4a,.aac,.flac,.wav,.ogg,.oga,.opus,.mka,.weba'},
  };
  static KEYS = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1};

  #dragDepth = 0;
  #mode = 'video';

  constructor() {
    this.zone = $('mp-zone');
    this.drop = $('mp-drop');
    this.input = $('mp-input');
    this.error = $('mp-error');
    this.tabs = [...document.querySelectorAll('.mp-tab')];
    this.#bindPicker();
    this.#bindDrop();
    this.#bindTabs();
    this.#bindJump();
    document.addEventListener('biblio:local', ({detail}) => this.#paint(detail));
    this.#paint({count: 0, mode: this.#mode, counts: {video: 0, audio: 0}});
  }

  /* ----- modes ----- */
  #bindTabs() {
    for (const tab of this.tabs) tab.addEventListener('click', () => this.setMode(tab.dataset.mode));
    $('mp-tabs').addEventListener('keydown', (event) => {      // flèches : onglet voisin ; Début / Fin : premier / dernier
      const modes = this.tabs.map((tab) => tab.dataset.mode);
      const at = modes.indexOf(this.#mode);
      const target = event.key === 'Home' ? 0 : event.key === 'End' ? modes.length - 1 : LocalPicker.KEYS[event.key] !== undefined ? (at + LocalPicker.KEYS[event.key] + modes.length) % modes.length : -1;
      if (target < 0) return;
      event.preventDefault();
      event.stopPropagation();                                 // les flèches ne doivent pas atteindre les raccourcis du lecteur (avance / recul)
      this.setMode(modes[target]);
      this.tabs[target].focus();
    });
  }

  setMode(mode) {
    if (!LocalPicker.MODES[mode] || mode === this.#mode) return;
    this.#hideError();
    window.BiblioLocal.setMode(mode);                          // le lecteur renvoie l'événement « biblio:local » : l'affichage suit (#paint)
  }

  /** Reflète l'état du lecteur : onglet choisi, compteurs, textes du mode, types de fichiers proposés, zone de dépôt. */
  #paint({count, mode, counts}) {
    this.#mode = mode;
    const text = LocalPicker.MODES[mode];
    for (const tab of this.tabs) {
      const selected = tab.dataset.mode === mode;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      $(`mp-n-${tab.dataset.mode}`).textContent = counts[tab.dataset.mode] ?? 0;
    }
    $('mp-panel').setAttribute('aria-labelledby', `mp-tab-${mode}`);
    $('mp-drop-title').textContent = text.title;
    $('mp-pick-label').textContent = text.pick;
    this.drop.setAttribute('aria-label', text.label);
    this.input.accept = text.accept;
    this.drop.hidden = count > 0;
  }

  /* ----- choix et dépôt de fichiers ----- */
  #bindPicker() {
    const openPicker = () => this.input.click();
    $('mp-pick').addEventListener('click', (event) => { event.stopPropagation(); openPicker(); });
    $('mp-add').addEventListener('click', openPicker);
    $('mp-clear').addEventListener('click', () => { this.#hideError(); window.BiblioLocal.clear(); });
    this.drop.addEventListener('click', openPicker);
    this.drop.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openPicker(); }
    });
    this.input.addEventListener('change', () => { this.accept([...this.input.files]); this.input.value = ''; });
  }

  /** Toute la page accepte un fichier déposé (sinon le navigateur l'ouvrirait et quitterait la page). */
  #bindDrop() {
    const hasFiles = (event) => [...(event.dataTransfer?.types ?? [])].includes('Files');
    window.addEventListener('dragenter', (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      this.#dragDepth += 1;
      this.zone.classList.add('dragging');
    });
    window.addEventListener('dragover', (event) => { if (hasFiles(event)) event.preventDefault(); });
    window.addEventListener('dragleave', (event) => {
      if (!hasFiles(event)) return;
      this.#dragDepth = Math.max(0, this.#dragDepth - 1);
      if (this.#dragDepth === 0) this.zone.classList.remove('dragging');
    });
    window.addEventListener('drop', (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      this.#dragDepth = 0;
      this.zone.classList.remove('dragging');
      this.accept([...event.dataTransfer.files]);
      this.reveal();
    });
  }

  accept(files) {
    this.#hideError();
    const {mode, rejected, other} = window.BiblioLocal.add(files);
    const plural = (n) => (n > 1 ? 's' : '');
    const notes = [];
    if (other) {                                               // un fichier de l'autre mode : jamais mélangé, on indique où le lire
      const away = LocalPicker.MODES[mode === 'video' ? 'audio' : 'video'];
      notes.push(`${other} fichier${plural(other)} ${away.noun} ignoré${plural(other)} : passe en mode ${away.name} pour ${other > 1 ? 'les' : 'le'} lire.`);
    }
    if (rejected) notes.push(`${rejected} fichier${plural(rejected)} ignoré${plural(rejected)} : ni vidéo ni audio.`);
    if (notes.length) { this.error.textContent = notes.join(' '); this.error.hidden = false; }
  }

  #hideError() { this.error.hidden = true; this.error.textContent = ''; }

  /* ----- positionnement de la vue ----- */
  /** Le lien « Aller au lecteur » : défilement doux et précis jusqu'à la section (sans aller-retour dans l'historique du navigateur). */
  #bindJump() {
    document.querySelector('a[href="#lecteur"]')?.addEventListener('click', (event) => {
      event.preventDefault();
      this.reveal({always: true});
      history.replaceState(null, '', '#lecteur');
    });
  }

  /** Amène la section du lecteur en haut de la zone visible, sous la barre fixe (marge : « scroll-margin-top » de la section, voir home.css).
      Un défilement n'a lieu que sur une action de l'utilisateur (lien, dépôt de fichiers), et seulement si la section est mal placée
      (cachée sous la barre ou trop bas) ; `always` : même si elle est déjà bien placée, pour la caler exactement. Sans animation
      si le navigateur demande de réduire les animations. */
  reveal({always = false} = {}) {
    const section = $('lecteur');
    if (!section) return;
    const margin = Number.parseFloat(getComputedStyle(section).scrollMarginTop) || 0;
    const {top} = section.getBoundingClientRect();
    const placed = top >= margin - 8 && top <= innerHeight * 0.3;
    if (placed && !(always && Math.abs(top - margin) > 2)) return;
    section.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
  }
}

// Démarrage : window.BiblioLocal est posé par le script du lecteur, chargé avant celui-ci.
new LocalPicker();
