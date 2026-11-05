  /** Titres du document : identifiants uniques (ancres) et liste pour le sommaire. */
  class Headings {
    #used = new Set();
    list = []; // {level, id, text}

    static slugify(text) {
      return text
        .toLowerCase()
        .trim()
        .replace(/[^\p{L}\p{N}\p{M}_\- ]/gu, '')
        .replace(/ /g, '-');
    }

    static plain(html) {
      return new DOMParser().parseFromString(`<body>${html}</body>`, 'text/html').body.textContent;
    }

    /** HTML d'un titre (avec son ancre) ; mémorise le titre pour le sommaire. */
    render(level, text) {
      const html = inlineRenderer.html(text.trim());
      const plain = Headings.plain(html).trim();
      const base = Headings.slugify(plain) || 'section';
      let id = base;
      for (let k = 1; this.#used.has(id); k++) id = `${base}-${k}`;
      this.#used.add(id);
      this.list.push({level, id, text: plain});
      return `<h${level} id="${esc(id)}">${html}<a class="anc" href="#${esc(id)}" aria-label="Lien vers cette section">#</a></h${level}>`;
    }
  }

  const headings = new Headings();

  
