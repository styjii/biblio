/** Tri de la liste (dossiers et fichiers) : nom, date, taille, durée ou type, croissant ou décroissant. Le choix est mémorisé.
    Par défaut : par nom (ordre naturel du serveur, repéré par data-order), tous types mélangés ; les filtres par catégorie restent
    gérés par Listing. Les valeurs inconnues (durée d'un PDF, taille d'un dossier…) passent toujours en dernier. */
class ListSort {
  static KEY = 'fl:sort';
  static DEFAULT_DIR = {name: 'asc', date: 'desc', size: 'desc', duration: 'desc', type: 'asc'};   // sens proposé à chaque changement de critère
  static FOLDER_KEYS = ['name', 'date'];                 // un dossier n'a ni taille, ni durée, ni type : il reste alors trié par nom
  static WORKERS = 4;                                    // requêtes /meta simultanées pour lire les durées

  #key = 'name';
  #dir = 'asc';
  #select = $('sort');
  #button = $('sort-dir');
  #note = $('sort-note');
  #timer = 0;

  constructor() {
    if (!this.#select || !this.#button) return;
    try {
      const [key, dir] = (localStorage.getItem(ListSort.KEY) ?? '').split(':');
      if (key in ListSort.DEFAULT_DIR) { this.#key = key; this.#dir = dir === 'desc' ? 'desc' : 'asc'; }
    } catch { /* tri par défaut */ }
    this.#select.value = this.#key;
    this.#select.addEventListener('change', () => { this.#key = this.#select.value; this.#dir = ListSort.DEFAULT_DIR[this.#key]; this.#changed(); });
    this.#button.addEventListener('click', () => { this.#dir = this.#dir === 'asc' ? 'desc' : 'asc'; this.#changed(); });
    // une durée vient d'être lue par les vignettes : on remet en ordre (une seule fois pour un lot)
    document.addEventListener('biblio:duration', () => { if (this.#key === 'duration') this.#later(); });
    this.#render();
    this.apply();
    if (this.#key === 'duration') this.#loadDurations();
  }

  #changed() {
    try { localStorage.setItem(ListSort.KEY, `${this.#key}:${this.#dir}`); } catch { /* choix non mémorisé */ }
    this.#render();
    this.apply();
    if (this.#key === 'duration') this.#loadDurations();
  }

  #render() {
    const asc = this.#dir === 'asc';
    this.#button.innerHTML = ICO[asc ? 'arrow_up' : 'arrow_down'] ?? '';
    const text = `${asc ? 'Ordre croissant' : 'Ordre décroissant'} — cliquer pour inverser`;
    this.#button.title = text;
    this.#button.setAttribute('aria-label', text);
  }

  #later() {
    clearTimeout(this.#timer);
    this.#timer = setTimeout(() => this.apply(), 250);
  }

  /** Valeur de tri d'un élément ; NaN / '' = inconnue. */
  #value(el, key) {
    switch (key) {
      case 'date': return Number.parseFloat(el.dataset.mtime);
      case 'size': return Number.parseFloat(el.dataset.bytes);
      case 'duration': return Number.parseFloat(el.dataset.dur);
      case 'type': return el.dataset.ext ?? '';
      default: return Number.parseFloat(el.dataset.order);
    }
  }

  #compare(key) {
    const sign = this.#dir === 'asc' ? 1 : -1;
    const byName = (a, b) => Number.parseFloat(a.dataset.order) - Number.parseFloat(b.dataset.order);
    return (a, b) => {
      if (key === 'name') return sign * byName(a, b);
      const x = this.#value(a, key);
      const y = this.#value(b, key);
      const unknownX = x === '' || Number.isNaN(x);
      const unknownY = y === '' || Number.isNaN(y);
      if (unknownX || unknownY) return unknownX === unknownY ? byName(a, b) : (unknownX ? 1 : -1);   // inconnu : toujours à la fin
      if (x === y) return byName(a, b);
      return sign * (typeof x === 'string' ? x.localeCompare(y) : x - y);
    };
  }

  apply() {
    document.querySelectorAll('.section').forEach((section) => {
      const box = section.querySelector('.files, .grid');
      if (!box) return;
      const folders = section.dataset.group === 'folders';
      const key = folders && !ListSort.FOLDER_KEYS.includes(this.#key) ? 'name' : this.#key;
      const sorted = [...box.children].sort(this.#compare(key));
      if (sorted.some((el, i) => el !== box.children[i])) box.append(...sorted);
    });
  }

  /** Durée de chaque vidéo / piste audio du dossier (les vignettes ne lisent que celles qui défilent à l'écran). */
  async #loadDurations() {
    const todo = [...document.querySelectorAll('[data-kind="video"], [data-kind="audio"]')].filter((el) => el.dataset.dur === undefined);
    if (!todo.length) return;
    this.#note.hidden = false;
    const worker = async () => {
      for (let card = todo.shift(); card; card = todo.shift()) {
        try {
          const {duration} = await (await fetch(`/meta?f=${card.dataset.f}`)).json();
          card.dataset.dur = duration ? String(duration) : '';
        } catch { card.dataset.dur = ''; }
      }
    };
    await Promise.all(Array.from({length: ListSort.WORKERS}, worker));
    this.#note.hidden = true;
    if (this.#key === 'duration') this.apply();
  }
}
