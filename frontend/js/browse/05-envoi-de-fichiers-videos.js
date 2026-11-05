
  /** Envoi de fichiers, vidéos et dossiers (déverrouillage requis). La feuille ne sert qu'à choisir les fichiers : l'envoi est
      confié à Transfers (js/transfers), qui le poursuit en arrière-plan dans un SharedWorker, même si l'on change de dossier ou de page. */
  class UploadDialog {
    #sheet;

    constructor(sheet) {
      this.#sheet = sheet;
      $('uploadbtn').addEventListener('click', () => this.#open());
      $('upcancel').addEventListener('click', () => sheet.close());
      $('up-pick-files').addEventListener('click', (e) => { e.preventDefault(); $('up-in-files').click(); });
      $('up-pick-dir').addEventListener('click', (e) => { e.preventDefault(); $('up-in-dir').click(); });
      for (const id of ['up-in-files', 'up-in-dir']) {
        $(id).addEventListener('change', ({target}) => {
          const files = [...target.files];
          target.value = '';
          if (!files.length) return;
          window.Transfers.start(files, cfg.folder || '', $('upover').checked, cfg.maxUpload || 0);
          sheet.close();
        });
      }
    }

    #step(id) {
      for (const step of ['upform', 'uppick']) $(step).hidden = step !== id;
    }

    #open() {
      this.#sheet.show('updlg');
      $('up-dest').textContent = `/${cfg.folder || ''}`;
      if (!cfg.unlocked) {
        $('uperr').textContent = 'Accès verrouillé : déverrouille l’accès (cadenas en haut de la page) pour envoyer des fichiers.';
        this.#step('upform');
        return;
      }
      this.#step('uppick');
    }
  }
