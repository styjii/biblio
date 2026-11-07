
/** Ordre de lecture des vidéos du dossier : dans l'ordre, ou mélangé. Le mélange est conservé d'une vidéo à l'autre (dans cet onglet). */
class PlayOrder {
  #count = items.length;
  #key = `vl:order:${cfg.folder}`;
  #signature = (() => {                                  // change si le contenu du dossier change : l'ancien mélange n'est alors plus valable
    let hash = 0;
    for (const char of items.map((t) => t.f).join('|')) hash = (hash * 31 + char.charCodeAt(0)) | 0;
    return `${hash}:${items.length}`;
  })();
  #order = [];
  #pos = 0;

  /** À l'ouverture de la page : on poursuit l'ordre en cours si on y arrive par « suivante » / « précédente » (ou rechargement). */
  restore(shuffle) {
    if (shuffle) {
      let saved = null;
      try { saved = JSON.parse(sessionStorage.getItem(this.#key)); } catch { /* aucun ordre mémorisé */ }
      const valid = saved?.sig === this.#signature && saved.order?.length === this.#count
        && (saved.cur === index || saved.next === index);
      if (valid && saved.order.includes(index)) {
        this.#order = saved.order;
        this.#pos = this.#order.indexOf(index);
        return this.save();
      }
    }
    this.rebuild(shuffle);
    this.save();
  }

  rebuild(shuffle) {
    if (shuffle) {
      const rest = [...Array(this.#count).keys()].filter((i) => i !== index);
      for (let i = rest.length - 1; i > 0; i--) {         // mélange de Fisher-Yates
        const j = Math.floor(Math.random() * (i + 1));
        [rest[i], rest[j]] = [rest[j], rest[i]];
      }
      this.#order = [index, ...rest];
      this.#pos = 0;
    } else {
      this.#order = [...Array(this.#count).keys()];
      this.#pos = index;
    }
  }

  /** Mémorise l'ordre ; `next` : vidéo vers laquelle on s'apprête à aller. */
  save(next = -1) {
    try { sessionStorage.setItem(this.#key, JSON.stringify({sig: this.#signature, order: this.#order, cur: index, next})); } catch { /* ordre non mémorisé */ }
  }

  get count() { return this.#count; }
  get next() { return this.#order[this.#pos + 1]; }      // undefined en fin de liste
  get previous() { return this.#order[this.#pos - 1]; }  // undefined au début
  get last() { return this.#order.at(-1); }

  /** Fin de liste : on repart du début ; en aléatoire, nouvelle série dont la vidéo qui vient de finir passe en dernier. */
  wrap(shuffle) {
    this.rebuild(shuffle);
    if (shuffle) this.#order.push(this.#order.shift());
    this.#pos = 0;
    return this.#order[0];
  }
}
