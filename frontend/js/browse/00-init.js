/* Page de navigation : liste (recherche, filtres), menu d'actions des fichiers et dossiers, et boîtes de dialogue
   (suppression, renommage, création, envoi). Les fichiers de ce dossier forment un seul script (concaténés dans l'ordre) :
   le serveur les enveloppe dans une fonction anonyme (portée commune, voir app/assets.py) ;
   le dernier crée les objets. */
const cfg = window.FLCFG;
const ICO = window.ICO;
const $ = (id) => document.getElementById(id);
const escapeHtml = (text) => String(text).replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]);
const isValidName = (name) => !!name && !/[\\/]/.test(name) && name !== '.' && name !== '..';

/** Envoie une action au serveur -> {status, answer}. */
const postAction = async (url) => {
  const r = await fetch(url, {method: 'POST', headers: {'X-Requested-With': 'biblio'}});
  return {status: r.status, answer: await r.json()};
};

/** Action protégée : en cas de succès la page est rechargée ; sinon l'erreur s'affiche sous le formulaire. */
async function runAction({url, button, errorBox, onLocked, networkError}) {
  button.disabled = true;
  errorBox.textContent = '';
  try {
    const {status, answer} = await postAction(url);
    button.disabled = false;
    if (!answer.ok) {
      if (answer.locked) { cfg.unlocked = false; onLocked(); return; }
      errorBox.textContent = answer.error || `Erreur ${status}`;
      return;
    }
    location.reload();
  } catch {
    button.disabled = false;
    errorBox.textContent = networkError;
  }
}

/** La liste : fichiers cachés, recherche par nom et filtres par catégorie, avec les compteurs. Le tri est dans ListSort (00-tri.js). */
class Listing {
  #active = 'all';
  #hiddenToggle = $('toggle-hidden');
  #search = $('search');

  constructor() {
    try { if (localStorage.getItem('fl:hidden') === '1') document.body.classList.add('show-hidden'); } catch { /* préférence par défaut */ }
    document.querySelectorAll('.fchip').forEach((chip) => {
      chip.addEventListener('click', () => { this.#active = chip.dataset.g; this.refresh(); });
    });
    if (this.#hiddenToggle) {
      this.#hiddenToggle.checked = document.body.classList.contains('show-hidden');
      this.#hiddenToggle.addEventListener('change', () => {
        document.body.classList.toggle('show-hidden', this.#hiddenToggle.checked);
        try { localStorage.setItem('fl:hidden', this.#hiddenToggle.checked ? '1' : '0'); } catch { /* préférence non mémorisée */ }
        this.refresh();
      });
    }
    this.#search?.addEventListener('input', () => {
      const query = this.#search.value.trim().toLowerCase();
      document.querySelectorAll('[data-name]').forEach((el) => { el.hidden = !el.dataset.name.includes(query); });
      this.refresh();
    });
    this.refresh();
  }

  #isShown(el) {
    return !el.hidden && (!el.classList.contains('dot') || document.body.classList.contains('show-hidden'));
  }

  refresh() {
    let shown = 0;
    const perGroup = {};
    document.querySelectorAll('.section').forEach((section) => {
      const items = [...section.querySelectorAll('[data-name]')].filter((el) => this.#isShown(el));
      if (section.dataset.group === 'files') {         // une seule liste : le filtre masque les fichiers des autres catégories
        for (const el of section.querySelectorAll('[data-name]')) el.classList.toggle('off', this.#active !== 'all' && el.dataset.group !== this.#active);
        for (const el of items) perGroup[el.dataset.group] = (perGroup[el.dataset.group] ?? 0) + 1;
      }
      const count = items.filter((el) => !el.classList.contains('off')).length;
      section.querySelector('.count').textContent = count;
      section.hidden = count === 0;
      shown += count;
    });
    document.querySelectorAll('.fchip').forEach((chip) => {
      const group = chip.dataset.g;
      const count = group === 'all' ? Object.values(perGroup).reduce((a, b) => a + b, 0) : (perGroup[group] ?? 0);
      chip.querySelector('b').textContent = count;
      chip.classList.toggle('on', group === this.#active);
    });
    const none = $('no-result');
    if (none) none.hidden = shown !== 0;
  }
}
