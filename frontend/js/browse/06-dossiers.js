
/** Création d'un dossier (mêmes droits que la création d'un fichier : cadenas si un mot de passe existe). */
class MkdirDialog {
  #sheet;

  constructor(sheet) {
    this.#sheet = sheet;
    $('newdir').addEventListener('click', () => this.#open());
    $('mkcancel').addEventListener('click', () => sheet.close());
    $('mkform').addEventListener('submit', (e) => { e.preventDefault(); this.#submit(); });
  }

  get #locked() { return !!cfg.protect && !cfg.unlocked; }

  #paint() {
    const locked = this.#locked;
    $('mk-locked').hidden = !locked;
    $('mkname').hidden = locked;
    $('mkok').hidden = locked;
  }

  #open() {
    this.#sheet.show('mkdlg');
    $('mk-dest').textContent = cfg.folder ? `Dans « ${cfg.folder} »` : 'À la racine de la bibliothèque';
    $('mkerr').textContent = '';
    $('mkname').value = '';
    this.#paint();
    if (!this.#locked) setTimeout(() => $('mkname').focus(), 50);
  }

  #submit() {
    if (this.#locked) return;
    const name = $('mkname').value.trim();
    if (!isValidName(name)) { $('mkerr').textContent = 'Nom invalide (sans « / »).'; return; }
    return runAction({
      url: `/mkdir?d=${encodeURIComponent(cfg.folder)}&to=${encodeURIComponent(name)}`, button: $('mkok'), errorBox: $('mkerr'),
      onLocked: () => this.#paint(), networkError: 'Échec réseau, le dossier n’a pas été créé.',
    });
  }
}
