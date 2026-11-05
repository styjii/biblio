  /** Définitions du document utilisées par le rendu en ligne : références de liens et notes de bas de page. */
  class DocumentRefs {
    links = Object.create(null); // identifiant (en minuscules) -> {u: adresse, t: titre}
    footnotes = Object.create(null); // identifiant -> texte de la note
    order = []; // notes dans l'ordre où elles sont citées
  }
  const refs = new DocumentRefs();

  /** Texte en ligne -> HTML : code, liens, images, notes, emphases. Le HTML sûr est mis de côté (« stash ») pendant l'échappement. */
  class InlineRenderer {
    #stash = [];

    #keep(h) {
      this.#stash.push(h);
      return `\u0001${this.#stash.length - 1}\u0002`;
    }
    #unstash(s) {
      let guard = 0;
      while (/\u0001\d+\u0002/.test(s) && guard++ < 24) {
        s = s.replace(/\u0001(\d+)\u0002/g, (m, n) => this.#stash[+n]);
      }
      return s;
    }
    #inline(s) {
      s = s.replace(/(?: {2,}|\\)\n/g, () => `${this.#keep('<br>')}\n`);
      s = s.replace(/(`+)([\s\S]*?[^`])\1(?!`)/g, (m, a, c) => {
        c = c.replace(/\n/g, ' ');
        if (/^ [\s\S]* $/.test(c) && /\S/.test(c)) c = c.slice(1, -1);
        return this.#keep(`<code>${esc(c)}</code>`);
      });
      s = s.replace(/\\([\\`*_{}\[\]()#+\-.!|~<>=$"'&])/g, (m, c) => this.#keep(esc(c)));
      s = s.replace(/!\[([^\]]*)\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+"([^"]*)")?\s*\)/g, (m, alt, u, t) => this.#keep(LinkResolver.imgTag(alt, u, t)));
      s = s.replace(/!\[([^\]]*)\]\[([^\]]*)\]/g, (m, alt, id) => {
        const r = refs.links[(id || alt).toLowerCase()];
        return r ? this.#keep(LinkResolver.imgTag(alt, r.u, r.t)) : m;
      });
      s = s.replace(/\[\^([^\]\s]+)\]/g, (m, id) => {
        if (!(id in refs.footnotes)) return m;
        let n = refs.order.indexOf(id);
        if (n < 0) {
          refs.order.push(id);
          n = refs.order.length - 1;
        }
        return this.#keep(`<sup class="fnref"><a href="#fn-${esc(id)}" id="fnref-${esc(id)}">${n + 1}</a></sup>`);
      });
      s = s.replace(/\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*(<[^>]*>|[^)\s]*)(?:\s+"([^"]*)")?\s*\)/g, (m, text, u, t) =>
        this.#keep(LinkResolver.linkTag(this.#inline(text), u, t)),
      );
      s = s.replace(/\[((?:[^\[\]]|\[[^\]]*\])*)\]\[([^\]]*)\]/g, (m, text, id) => {
        const r = refs.links[(id || text).toLowerCase()];
        return r ? this.#keep(LinkResolver.linkTag(this.#inline(text), r.u, r.t)) : m;
      });
      s = s.replace(/\[([^\[\]]+)\](?!\()/g, (m, id) => {
        const r = refs.links[id.toLowerCase()];
        return r ? this.#keep(LinkResolver.linkTag(esc(id), r.u, r.t)) : m;
      });
      s = s.replace(/<((?:https?:\/\/|mailto:)[^\s<>]+)>/gi, (m, u) => this.#keep(LinkResolver.linkTag(esc(u), u)));
      s = s.replace(/<([^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)>/g, (m, u) => this.#keep(LinkResolver.linkTag(esc(u), `mailto:${u}`)));
      s = s.replace(/(^|[\s(>])(https?:\/\/[^\s<]*[^\s<.,;:!?'")\]])/g, (m, pre, u) => pre + this.#keep(LinkResolver.linkTag(esc(u), u)));
      s = s.replace(/<!--[\s\S]*?-->/g, '');
      s = s.replace(/<br\s*\/?>/gi, () => this.#keep('<br>'));
      s = s.replace(/<(\/?)(kbd|sub|sup|mark|b|i|u|em|strong|del|ins|small|s|abbr|cite|q)>/gi, (m, sl, t) => this.#keep(`<${sl}${t.toLowerCase()}>`));
      s = esc(s);
      s = s
        .replace(/\*\*\*(?=\S)([\s\S]*?\S)\*\*\*/g, '<strong><em>$1</em></strong>')
        .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>')
        .replace(/(^|[^\w])__(?=\S)([\s\S]*?\S)__(?!\w)/g, '$1<strong>$2</strong>')
        .replace(/\*(?=[^\s*])([\s\S]*?[^\s*])\*/g, '<em>$1</em>')
        .replace(/(^|[^\w])_(?=[^\s_])([\s\S]*?[^\s_])_(?!\w)/g, '$1<em>$2</em>')
        .replace(/~~(?=\S)([\s\S]*?\S)~~/g, '<del>$1</del>')
        .replace(/==(?=\S)([\s\S]*?\S)==/g, '<mark>$1</mark>');
      return s;
    }
    /** HTML d'un texte en ligne (gras, liens, code…). */
    html(s) {
      return this.#unstash(this.#inline(s));
    }
  }

  const inlineRenderer = new InlineRenderer();

  
