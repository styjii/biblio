
/** Édition refusée tant que l'accès est verrouillé : on l'indique, sans demander de mot de passe ici. */
class EditLockedDialog {
  #sheet;

  constructor(sheet) {
    this.#sheet = sheet;
    $('edtcancel').addEventListener('click', () => sheet.close());
  }

  ask(item) {
    $('edt-name').textContent = item.dataset.title;
    this.#sheet.show('edtdlg');
  }
}
