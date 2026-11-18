/**
 * Accueil : choix et dépôt de fichiers pour le lecteur multimédia local.
 * Le lecteur lui-même est celui de la page de lecture vidéo (frontend/js/watch/, mode « local ») : ce script ne fait
 * que lui transmettre les fichiers de l'appareil (window.BiblioLocal) et afficher la zone de dépôt tant qu'il n'y en a pas.
 */
class LocalPicker {
  #dragDepth = 0;

  constructor() {
    this.zone = $('mp-zone');
    this.drop = $('mp-drop');
    this.input = $('mp-input');
    this.error = $('mp-error');
    this.#bindPicker();
    this.#bindDrop();
    document.addEventListener('biblio:local', ({detail}) => { this.drop.hidden = detail.count > 0; });
  }

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
      this.zone.scrollIntoView({behavior: 'smooth', block: 'center'});
    });
  }

  accept(files) {
    this.#hideError();
    const {rejected} = window.BiblioLocal.add(files);
    if (rejected) {
      this.error.textContent = `${rejected} fichier${rejected > 1 ? 's' : ''} ignoré${rejected > 1 ? 's' : ''} : ni vidéo ni audio.`;
      this.error.hidden = false;
    }
  }

  #hideError() { this.error.hidden = true; this.error.textContent = ''; }
}

// Démarrage : window.BiblioLocal est posé par le script du lecteur, chargé avant celui-ci.
new LocalPicker();
