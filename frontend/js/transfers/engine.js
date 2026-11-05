/* Moteur d'envoi : file d'attente séquentielle, une requête POST en flux par fichier.
   Aucun accès au DOM : il tourne dans un SharedWorker (l'envoi survit alors à la navigation d'une page à l'autre)
   ou, si le navigateur n'en a pas, directement dans la page.
   `emit(vue)` est appelé à chaque changement (progression limitée à ~7 fois par seconde). */
class TransferEngine {
  static MAX_ROWS = 200;                        // lignes envoyées aux pages (les longues files sont résumées)
  static PROGRESS_DELAY = 150;                  // ms entre deux envois de progression
  static TICKET_MARGIN = 45_000;                // un jeton est renouvelé 45 s avant son expiration

  /** Taille lisible : 1536 -> « 1.5 Ko ». */
  static fmtB(bytes) {
    const units = ['o', 'Ko', 'Mo', 'Go'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
    return `${i ? bytes.toFixed(bytes >= 100 ? 0 : 1) : bytes} ${units[i]}`;
  }

  #emit;
  #items = [];                                  // {id, rel, dest, over, max, size, st: wait|run|ok|skip|bad, loaded, msg}
  #files = new Map();                           // id -> File (libéré dès que l'élément est traité)
  #nextId = 1;
  #series = 0;                                  // numéro de la série d'envois en cours
  #cursor = 0;                                  // tout ce qui précède est déjà traité
  #running = false;
  #cancelled = false;
  #xhr = null;
  #note = '';
  #timer = 0;
  #ticket = null;
  #ticketAt = 0;
  #ticketTtl = 0;

  constructor(emit) {
    this.#emit = emit;
  }

  /* ----- commandes ----- */
  add(list, rels, dest = '', over = false, max = 0) {
    if (!this.#running && this.#items.length) this.#reset();      // nouvelle série : on repart de zéro
    list.forEach((file, i) => {
      const id = this.#nextId++;
      this.#items.push({id, rel: rels[i], dest: dest || '', over: !!over, max: max || 0, size: file.size,
                        st: 'wait', loaded: 0, msg: ''});
      this.#files.set(id, file);
    });
    if (this.#running) return this.#push(true);
    this.#running = true;
    this.#cancelled = false;
    this.#note = '';
    this.#series++;
    this.#push(true);
    this.#process();
  }

  cancel() {
    if (!this.#running) return;
    this.#cancelled = true;
    this.#xhr?.abort();
  }

  clear() {
    if (this.#running) return;
    this.#reset();
    this.#push(true);
  }

  #reset() {
    this.#items = [];
    this.#files.clear();
    this.#note = '';
    this.#cursor = 0;
  }

  /* ----- vue envoyée aux pages (sans les fichiers) ----- */
  view() {
    const items = this.#items;
    const counts = {total: 0, done: 0, ok: 0, skipped: 0, failed: 0, waiting: 0};
    const okDests = new Set();
    for (const it of items) {
      counts.total += it.size;
      switch (it.st) {
        case 'ok': counts.ok++; counts.done += it.size; okDests.add(it.dest); break;
        case 'skip': counts.skipped++; counts.done += it.size; break;
        case 'bad': counts.failed++; counts.done += it.size; break;
        case 'run': counts.done += it.loaded; break;
        default: counts.waiting++;
      }
    }
    const shown = this.#shownItems();
    return {
      run: this.#series, running: this.#running, finished: !this.#running && items.length > 0, note: this.#note,
      count: items.length, ...counts, okDests: [...okDests], more: items.length - shown.length,
      rows: shown.map(({id, rel, dest, st, size, loaded, msg}) => ({
        id, name: rel, dest, st, size, msg,
        pct: size ? Math.min(100, Math.floor(loaded * 100 / size)) : 100,
      })),
    };
  }

  /** Les longues files sont résumées : envoi en cours, échecs et refus d'abord, puis le début de la file et les derniers envoyés. */
  #shownItems() {
    const items = this.#items;
    const {MAX_ROWS} = TransferEngine;
    if (items.length <= MAX_ROWS) return items;
    const picked = new Set();
    const pick = (order, limit, wanted) => {
      for (const i of order) {
        if (picked.size >= limit) return;
        if (!picked.has(i) && wanted(items[i].st)) picked.add(i);
      }
    };
    const forward = [...items.keys()];
    pick(forward, MAX_ROWS, (st) => ['run', 'bad', 'skip'].includes(st));
    pick(forward, MAX_ROWS - 20, (st) => st === 'wait');
    pick(forward.reverse(), MAX_ROWS, (st) => st === 'ok');
    return items.filter((_, i) => picked.has(i));
  }

  #push(now = false) {
    if (now) {
      clearTimeout(this.#timer);
      this.#timer = 0;
      this.#emit(this.view());
    } else if (!this.#timer) {
      this.#timer = setTimeout(() => { this.#timer = 0; this.#emit(this.view()); }, TransferEngine.PROGRESS_DELAY);
    }
  }

  /* ----- jeton d'envoi (renouvelé tout seul, même si la page qui l'a demandé n'existe plus) ----- */
  #ticketValid() {
    return this.#ticket && Date.now() - this.#ticketAt < this.#ticketTtl - TransferEngine.TICKET_MARGIN;
  }

  async #fetchTicket() {
    const r = await fetch('/upload-auth', {method: 'POST', headers: {'X-Requested-With': 'biblio'}, credentials: 'same-origin'});
    const answer = await r.json();
    if (!answer.ok) {
      const error = new Error(answer.error || `Erreur ${r.status}`);
      error.locked = !!answer.locked;
      throw error;
    }
    this.#ticket = answer.ticket;
    this.#ticketTtl = (answer.ttl || 900) * 1000;
    this.#ticketAt = Date.now();
  }

  /* ----- déroulement ----- */
  async #process() {
    for (;;) {
      if (this.#cancelled) return this.#endRun('arrêté');
      const item = this.#nextWaiting();
      if (!item) return this.#endRun('');
      item.st = 'run';
      item.loaded = 0;
      item.msg = '';
      this.#push(true);
      const stopMessage = await this.#transfer(item);
      if (stopMessage !== undefined) return this.#endRun(stopMessage);
    }
  }

  /** Prochain fichier à envoyer ; ceux qui dépassent la taille maximale sont refusés au passage. */
  #nextWaiting() {
    for (let i = this.#cursor; i < this.#items.length; i++) {
      const it = this.#items[i];
      if (it.st !== 'wait') { if (i === this.#cursor) this.#cursor++; continue; }
      if (it.max && it.size > it.max) {
        this.#finish(it, 'bad', `trop volumineux (max ${TransferEngine.fmtB(it.max)})`);
        continue;
      }
      return it;
    }
    return null;
  }

  #finish(item, st, msg = '') {
    item.st = st;
    item.msg = msg;
    this.#files.delete(item.id);
  }

  /** Envoie un fichier. Renvoie un message pour arrêter toute la série, ou undefined pour passer au suivant. */
  async #transfer(item) {
    try {
      if (!this.#ticketValid()) await this.#fetchTicket();
    } catch (err) {
      const message = err.locked ? 'accès verrouillé : déverrouille puis recommence' : (err.message || 'erreur');
      this.#finish(item, 'bad', err.locked ? 'accès verrouillé' : (err.message || 'erreur'));
      return message;
    }
    for (let attempt = 0; attempt < 2; attempt++) {
      if (this.#cancelled) { this.#finish(item, 'skip', 'annulé'); return undefined; }
      let response;
      try {
        response = await this.#post(item);
      } catch (failure) {
        if (failure.aborted) { this.#finish(item, 'bad', 'arrêté'); this.#push(true); return undefined; }
        this.#finish(item, 'bad', 'échec réseau');
        return 'connexion perdue';
      }
      const {status, body} = response;
      if (status === 200 && body.ok) {
        this.#finish(item, 'ok');
        this.#ticketAt = Date.now();
      } else if (status === 409) {
        this.#finish(item, 'skip', body.error || 'déjà présent');
      } else if (body.code === 'locked') {
        this.#ticket = null;
        this.#finish(item, 'bad', 'accès verrouillé');
        return 'accès verrouillé : déverrouille puis recommence';
      } else if (body.code === 'ticket') {
        this.#ticket = null;
        if (attempt === 0) {                                       // jeton expiré : on en demande un autre et on renvoie le même fichier
          try { await this.#fetchTicket(); } catch (err) {
            this.#finish(item, 'bad', err.message || 'erreur');
            return err.message || 'erreur';
          }
          continue;
        }
        this.#finish(item, 'bad', 'session expirée');
        return "session d'envoi expirée";
      } else {
        this.#finish(item, 'bad', body.error || `erreur ${status}`);
      }
      break;
    }
    this.#push(true);
    return undefined;
  }

  /** Une requête POST en flux (le fichier n'est jamais chargé en mémoire) ; la progression met à jour `item.loaded`. */
  #post(item) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      this.#xhr = xhr;
      xhr.open('POST', `/upload?d=${encodeURIComponent(item.dest)}&n=${encodeURIComponent(item.rel)}${item.over ? '&o=1' : ''}`);
      xhr.setRequestHeader('X-Requested-With', 'biblio');
      xhr.setRequestHeader('X-Upload-Ticket', this.#ticket);
      xhr.setRequestHeader('Content-Type', 'application/octet-stream');
      xhr.upload.onprogress = ({lengthComputable, loaded}) => {
        if (lengthComputable) { item.loaded = loaded; this.#push(); }
      };
      xhr.onload = () => {
        this.#xhr = null;
        let body = {};
        try { body = JSON.parse(xhr.responseText); } catch { /* réponse vide ou illisible */ }
        resolve({status: xhr.status, body});
      };
      xhr.onabort = () => { this.#xhr = null; reject({aborted: true}); };
      xhr.onerror = () => { this.#xhr = null; reject({network: true}); };
      xhr.send(this.#files.get(item.id));
    });
  }

  #endRun(message) {
    this.#running = false;
    this.#xhr = null;
    this.#note = message || '';
    for (const it of this.#items) {
      if (it.st === 'wait') { it.st = 'skip'; it.msg = message === 'arrêté' ? 'annulé' : 'non envoyé'; }
    }
    this.#files.clear();
    this.#push(true);
  }
}
