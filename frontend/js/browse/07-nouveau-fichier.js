
  /** Création d'un fichier : on choisit son nom ici, puis l'éditeur s'ouvre. */
  class NewFileDialog {
    #sheet;

    constructor(sheet) {
      this.#sheet = sheet;
      $('newfile').addEventListener('click', () => this.#open());
      $('newcancel').addEventListener('click', () => sheet.close());
      $('newform').addEventListener('submit', (e) => { e.preventDefault(); this.#submit(); });
    }

    get #locked() { return !!cfg.protect && !cfg.unlocked; }

    #open() {
      const locked = this.#locked;
      this.#sheet.show('newdlg');
      $('new-locked').hidden = !locked;
      $('newname').hidden = locked;
      $('newok').hidden = locked;
      $('newname').value = '';
      $('newerr').textContent = '';
      if (!locked) setTimeout(() => $('newname').focus(), 50);
    }

    #submit() {
      if (this.#locked) return;
      const name = $('newname').value.trim();
      if (!isValidName(name)) { $('newerr').textContent = 'Nom invalide (sans « / »).'; return; }
      location.href = `/edit?new=1&f=${encodeURIComponent(cfg.folder ? `${cfg.folder}/${name}` : name)}`;
    }
  }

  /* ----- mise en route ----- */
  new Listing();
  const sheet = new Sheet();
  const deleteDialog = new DeleteDialog(sheet);
  const renameDialog = new RenameDialog(sheet);
  const editDialog = new EditLockedDialog(sheet);
  const menu = new ItemMenu(sheet, {
    delete: (item) => deleteDialog.ask(item),
    rename: (item) => renameDialog.ask(item),
    edit: (item) => editDialog.ask(item),
  });

  // fichiers : un clic ouvre le menu, sauf pour les types qu'on ouvre directement (le bouton « ⋯ » ouvre toujours le menu)
  document.querySelectorAll('.fcard').forEach((card) => {
    card.addEventListener('click', (e) => {
      if (!e.target.closest('.more')) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
        if (card.dataset.direct === '1') return;
      }
      e.preventDefault();
      menu.open(card);
    });
  });
  // dossiers : un clic ailleurs que sur « ⋯ » ouvre le dossier
  document.querySelectorAll('.item[data-kind="folder"]').forEach((folder) => {
    folder.addEventListener('click', (e) => {
      if (!e.target.closest('.more')) return;
      e.preventDefault();
      menu.open(folder);
    });
  });

  if (window.Transfers) window.Transfers.currentFolder = cfg.folder || '';      // pour actualiser la liste à la fin d'un envoi ici
  if ($('uploadbtn') && window.Transfers) new UploadDialog(sheet);
  if ($('newdir')) new MkdirDialog(sheet);
  if ($('newfile')) new NewFileDialog(sheet);
})();
