
  /** Renommage d'un fichier ou d'un dossier (déverrouillage requis ; aucun mot de passe n'est demandé ici). */
  class RenameDialog {
    #sheet;
    #target = null;

    constructor(sheet) {
      this.#sheet = sheet;
      $('rencancel').addEventListener('click', () => sheet.close());
      $('renform').addEventListener('submit', (e) => { e.preventDefault(); this.#submit(); });
    }

    #paint() {
      const locked = !cfg.unlocked;
      $('ren-locked').hidden = !locked;
      $('rennew').hidden = locked;
      $('renok').hidden = locked;
    }

    ask(item) {
      this.#target = item;
      const folder = item.dataset.kind === 'folder';
      const input = $('rennew');
      $('ren-title').textContent = folder ? 'Renommer ce dossier' : 'Renommer ce fichier';
      $('ren-locked').textContent = `Accès verrouillé : déverrouille l'accès (cadenas en haut de la page) pour renommer ${folder ? 'ce dossier.' : 'ce fichier.'}`;
      $('ren-name').textContent = item.dataset.title;
      $('renerr').textContent = '';
      input.value = item.dataset.title;
      this.#paint();
      this.#sheet.show('rendlg');
      if (cfg.unlocked) {
        setTimeout(() => {
          input.focus();
          const dot = input.value.lastIndexOf('.');
          input.setSelectionRange(0, dot > 0 ? dot : input.value.length);      // on sélectionne le nom, pas l'extension
        }, 30);
      }
    }

    #submit() {
      const name = $('rennew').value.trim();
      if (!this.#target || !cfg.canDelete || !cfg.unlocked) return;
      if (!name) { $('renerr').textContent = 'Saisis un nom.'; return; }
      if (name === this.#target.dataset.title) return this.#sheet.close();
      return runAction({
        url: `/rename?f=${this.#target.dataset.f}&to=${encodeURIComponent(name)}`, button: $('renok'), errorBox: $('renerr'),
        onLocked: () => this.#paint(), networkError: 'Échec réseau, rien n’a été renommé.',
      });
    }
  }
