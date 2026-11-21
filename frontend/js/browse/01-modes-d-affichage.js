/** Mode d'affichage de la liste : grandes icônes, icônes moyennes (par défaut), petites icônes, liste ou détails.
    Réglage global : le même mode s'applique à tous les dossiers et sous-dossiers parcourus, et reste choisi d'une page à l'autre
    (mémorisé dans le navigateur sous « fl:view » ; les autres onglets ouverts le suivent). La mise en page est dans
    frontend/css/main/13-modes-d-affichage.css, selon l'attribut data-view de <main id="listing">.
    Le mode est posé avant le premier affichage par un script en ligne, premier enfant de <main> (templates/browse/main.html) ;
    cette classe prend ensuite le relais (changement de mode, autres onglets, page restaurée par le bouton Retour). */
class ViewMode {
  static KEY = 'fl:view';
  static MODES = ['large', 'medium', 'small', 'list', 'details'];
  static DEFAULT = 'medium';

  #main = $('listing');
  #select = $('view');

  constructor() {
    if (!this.#main) return;
    this.#fillDates();
    this.#apply(this.#saved());
    this.#select?.addEventListener('change', () => this.set(this.#select.value));
    window.addEventListener('storage', (event) => { if (event.key === ViewMode.KEY) this.#apply(event.newValue); });   // un autre onglet a changé de mode
    // page restaurée telle quelle par le bouton Retour (cache de navigation) : aucun événement « storage » n'a pu l'atteindre, le mode a pu changer entre-temps
    window.addEventListener('pageshow', (event) => { if (event.persisted) this.#apply(this.#saved()); });
  }

  #saved() {
    try { return localStorage.getItem(ViewMode.KEY); } catch { return null; }
  }

  #apply(mode) {
    const valid = ViewMode.MODES.includes(mode) ? mode : ViewMode.DEFAULT;
    this.#main.dataset.view = valid;
    if (this.#select) this.#select.value = valid;
    return valid;
  }

  /** Change le mode de la liste et le mémorise pour tous les dossiers (le mode par défaut n'a pas besoin d'être stocké). */
  set(mode) {
    const valid = this.#apply(mode);
    try {
      if (valid === ViewMode.DEFAULT) localStorage.removeItem(ViewMode.KEY); else localStorage.setItem(ViewMode.KEY, valid);
    } catch { /* choix non mémorisé */ }
  }

  /** Colonne « Modifié le » du mode Détails : date et heure locales de l'appareil, d'après data-mtime. */
  #fillDates() {
    const day = {day: '2-digit', month: '2-digit', year: 'numeric'};
    const time = {hour: '2-digit', minute: '2-digit'};
    document.querySelectorAll('.cols .c-date').forEach((cell) => {
      const seconds = Number(cell.closest('[data-mtime]')?.dataset.mtime);
      if (!seconds) { cell.textContent = '—'; return; }
      const date = new Date(seconds * 1000);
      cell.textContent = `${date.toLocaleDateString(undefined, day)} ${date.toLocaleTimeString(undefined, time)}`;
    });
  }
}
