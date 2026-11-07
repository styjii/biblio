
/** Ordre de lecture des pistes : dans l'ordre, ou mélangé (la piste en cours passe en premier). */
class PlayOrder {
  #count = tracks.length;
  #order = [];
  #pos = 0;

  /** Reconstruit l'ordre autour de la piste `current`. */
  rebuild(shuffle, current) {
    if (shuffle) {
      const rest = [...Array(this.#count).keys()].filter((i) => i !== current);
      for (let i = rest.length - 1; i > 0; i--) {         // mélange de Fisher-Yates
        const j = Math.floor(Math.random() * (i + 1));
        [rest[i], rest[j]] = [rest[j], rest[i]];
      }
      this.#order = [current, ...rest];
      this.#pos = 0;
    } else {
      this.#order = [...Array(this.#count).keys()];
      this.#pos = current;
    }
  }

  get count() { return this.#count; }
  get hasNext() { return this.#pos + 1 < this.#count; }
  get hasPrevious() { return this.#pos > 0; }
  advance() { return this.#order[++this.#pos]; }
  retreat() { return this.#order[--this.#pos]; }
  jumpToLast() { this.#pos = this.#count - 1; return this.#order[this.#pos]; }

  /** Fin de liste : on repart du début ; en aléatoire, nouvelle série dont la piste qui vient de finir passe en dernier. */
  wrap(shuffle, current) {
    this.rebuild(shuffle, current);
    if (shuffle) this.#order.push(this.#order.shift());
    this.#pos = 0;
    return this.#order[0];
  }
}
