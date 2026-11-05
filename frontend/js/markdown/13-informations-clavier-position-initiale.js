  /** Informations (mots, temps de lecture), raccourcis clavier et position de départ. */
  class ReaderPage {
    constructor() {
      this.#showInfo();
      document.addEventListener('keydown', (e) => {
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        if (['INPUT', 'TEXTAREA'].includes(e.target?.tagName)) return;
        if (e.key === 't' && toc.hasButton) toc.toggle();
        else if (e.key === 'Escape' && toc.isOpen) toc.close();
      });
      sc.tabIndex = 0;
      this.#restorePosition();
      progress.update();
      try {
        sc.focus({preventScroll: true});
      } catch {
        /* focus impossible */
      }
    }

    #showInfo() {
      const copy = art.cloneNode(true);
      copy.querySelectorAll('figure.code,.anc').forEach((node) => node.remove()); // ni le code ni les ancres ne comptent comme texte lu
      const words = (copy.textContent.match(/[\p{L}\p{N}]+(?:['\u2019-][\p{L}\p{N}]+)*/gu) || []).length;
      const minutes = Math.max(1, Math.round(words / 220));
      $('md-meta').textContent = `Aperçu · ${cfg.label} · ${minutes} min de lecture · ${words.toLocaleString('fr-FR')} mots`;
    }

    /** Ancre de l'adresse si elle existe, sinon dernière position de lecture. */
    #restorePosition() {
      const start = location.hash.length > 1 ? navigation.find(location.hash.slice(1)) : null;
      if (start) return navigation.scrollTo(start, false);
      const saved = progress.savedPosition;
      if (saved > 0 && saved < 1) sc.scrollTop = saved * sc.scrollHeight;
    }
  }

  new ReaderPage();
})();
