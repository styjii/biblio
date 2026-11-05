  /** Liens internes (#ancre) : défilement doux dans la zone de lecture, tolérant aux accents et aux majuscules. */
  class InternalNavigation {
    #reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    constructor() {
      document.addEventListener('click', (e) => {
        const link = e.target.closest?.('a[href^="#"]');
        if (!link || e.ctrlKey || e.metaKey || e.shiftKey) return;
        const target = this.find(link.getAttribute('href').slice(1));
        if (!target) return;
        e.preventDefault();
        this.scrollTo(target, true);
        try {
          history.replaceState(null, '', `#${encodeURIComponent(target.id)}`);
        } catch {
          /* adresse inchangée */
        }
        if (!toc.isWide) toc.close();
      });
    }

    static fold(text) {
      return text
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
    }

    /** Élément ciblé par une ancre : identifiant exact, sinon titre dont le nom « simplifié » correspond. */
    find(id) {
      try {
        id = decodeURIComponent(id);
      } catch {
        /* ancre telle quelle */
      }
      const element = document.getElementById(id);
      if (element && art.contains(element)) return element;
      const key = InternalNavigation.fold(id);
      const match = headings.list.find((heading) => InternalNavigation.fold(heading.id) === key);
      return match ? document.getElementById(match.id) : null;
    }

    scrollTo(element, smooth) {
      const top = sc.scrollTop + element.getBoundingClientRect().top - sc.getBoundingClientRect().top - 14;
      sc.scrollTo({top: Math.max(0, top), behavior: smooth && !this.#reduceMotion ? 'smooth' : 'auto'});
    }
  }

  const navigation = new InternalNavigation();

  
