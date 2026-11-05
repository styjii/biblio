
  /** Informations des pistes (durée, titre, artiste, pochette) : demandées au serveur à la demande, une seule fois par piste. */
  class TrackInfo {
    #cache = new Map();

    get(index) {
      if (!this.#cache.has(index)) this.#cache.set(index, this.#fetch(index));
      return this.#cache.get(index);
    }

    async #fetch(index) {
      try {
        const r = await fetch(`/meta?f=${tracks[index].q}`);
        return r.ok ? await r.json() : {};
      } catch {
        return {};
      }
    }
  }
