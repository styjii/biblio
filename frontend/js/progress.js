/* Dernière position de lecture : mémorisée par le SERVEUR pour chaque appareil (adresse IP), pas par le navigateur.
   La reprise fonctionne donc aussi après avoir vidé le navigateur ou changé de navigateur sur le même appareil. */
(() => {
  class PlaybackProgress {
    #sent = new Map();                       // fichier -> dernière position envoyée (évite les envois inutiles)

    static url(rel, extra = '') {
      return `/progress?f=${encodeURIComponent(rel)}${extra}`;
    }

    #post(rel, extra, keepalive = false) {
      try {
        fetch(PlaybackProgress.url(rel, extra), {
          method: 'POST', headers: {'X-Requested-With': 'biblio'}, credentials: 'same-origin', keepalive,
        }).catch(() => {});
      } catch { /* envoi impossible : la position sera renvoyée plus tard */ }
    }

    /** Position mémorisée pour cet appareil -> {t, d}, ou null si le serveur ne répond pas. */
    async get(rel) {
      try {
        const r = await fetch(PlaybackProgress.url(rel), {credentials: 'same-origin'});
        const j = r.ok ? await r.json() : null;
        return j?.ok ? {t: j.t || 0, d: j.d || 0} : null;
      } catch {
        return null;
      }
    }

    /** `keepalive` : l'envoi aboutit même si la page se ferme. Une position proche du début efface la mémoire (côté serveur). */
    save(rel, t, d, keepalive = false) {
      if (!Number.isFinite(t) || t < 0) return;
      if (Math.abs((this.#sent.get(rel) ?? Infinity) - t) < 1) return;
      this.#sent.set(rel, t);
      this.#post(rel, `&t=${t.toFixed(1)}&d=${(Number.isFinite(d) ? d : 0).toFixed(1)}`, keepalive);
    }

    /** Lu jusqu'au bout : on oublie la position. */
    done(rel) {
      this.#sent.set(rel, 0);
      this.#post(rel, '&done=1', true);
    }

    /** Secondes -> « m:ss » ou « h:mm:ss ». */
    fmt(s) {
      s = Math.max(0, Math.floor(s));
      const h = Math.floor(s / 3600);
      const m = Math.floor(s % 3600 / 60);
      const r = s % 60;
      return `${h ? `${h}:${String(m).padStart(2, '0')}` : m}:${String(r).padStart(2, '0')}`;
    }
  }

  window.Progress = new PlaybackProgress();
})();
