
/** Suppression d'un fichier ou d'un dossier (déverrouillage requis ; aucun mot de passe n'est demandé ici). */
class DeleteDialog {
  #sheet;
  #target = null;

  constructor(sheet) {
    this.#sheet = sheet;
    $('delcancel').addEventListener('click', () => sheet.close());
    $('delform').addEventListener('submit', (e) => { e.preventDefault(); this.#submit(); });
  }

  #paint() {
    const locked = !cfg.unlocked;
    $('del-locked').hidden = !locked;
    $('delok').hidden = locked;
  }

  ask(item) {
    this.#target = item;
    const folder = item.dataset.kind === 'folder';
    $('del-title').textContent = folder ? 'Supprimer ce dossier ?' : 'Supprimer ce fichier ?';
    $('del-warn').hidden = !folder;
    $('del-locked').textContent = `Accès verrouillé : déverrouille l'accès (cadenas en haut de la page) pour supprimer ${folder ? 'ce dossier.' : 'ce fichier.'}`;
    $('del-name').textContent = item.dataset.title;
    $('delerr').textContent = '';
    this.#paint();
    this.#sheet.show('deldlg');
  }

  #submit() {
    if (!this.#target || !cfg.canDelete || !cfg.unlocked) return;
    return runAction({
      url: `/delete?f=${this.#target.dataset.f}`, button: $('delok'), errorBox: $('delerr'),
      onLocked: () => this.#paint(), networkError: 'Échec réseau, rien n’a été supprimé.',
    });
  }
}
