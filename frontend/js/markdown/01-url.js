  /** Adresses : chemins relatifs résolus dans la bibliothèque, liens et images sûrs (jamais de javascript:). */
  class LinkResolver {
    static extOf(p) {
      const m = /\.([A-Za-z0-9]+)$/.exec(p);
      return m ? m[1].toLowerCase() : '';
    }
    static has(list, e) {
      return !!e && list.includes(e);
    }
    static joinPath(base, rel) {
      const parts = (base ? base.split('/') : []).concat(rel.split('/'));
      const out = [];
      parts.forEach((s) => {
        if (s === '' || s === '.') return;
        if (s === '..') out.pop();
        else out.push(s);
      });
      return out.join('/');
    }
    /** Adresse sûre pour un lien ou une image -> {href, ext?}, ou null si elle est refusée. */
    static safeUrl(u, isImg) {
      u = String(u || '').trim();
      if (!u) return null;
      if (/^(?:https?:)?\/\//i.test(u)) return {href: u, ext: true};
      if (u.charAt(0) === '#') return isImg ? null : {href: u};
      if (/^(?:mailto|tel):/i.test(u)) return isImg ? null : {href: u};
      if (/^data:image\/(?:png|jpe?g|gif|webp|avif|svg\+xml)[;,]/i.test(u)) return isImg ? {href: u} : null;
      if (/^[a-z][a-z0-9+.-]*:/i.test(u)) return null;
      const m = /^([^?#]*)([?#][\s\S]*)?$/.exec(u);
      let path = m[1];
      const tail = m[2] || '';
      try {
        path = decodeURIComponent(path);
      } catch {
        /* adresse non encodée : telle quelle */
      }
      const full = path.charAt(0) === '/' ? LinkResolver.joinPath('', path) : LinkResolver.joinPath(cfg.dir, path);
      const hi = tail.indexOf('#');
      const hash = hi >= 0 ? tail.slice(hi) : '';
      if (!full) return hash ? {href: hash} : null;
      const q = encodeURIComponent(full);
      const e = LinkResolver.extOf(full);
      let href;
      if (isImg) href = e === 'svg' ? cfg.site + full.split('/').map(encodeURIComponent).join('/') : `/raw?f=${q}`;
      else if (LinkResolver.has(EXT.md, e) || LinkResolver.has(EXT.web, e)) href = `/preview?f=${q}${hash}`;
      else if (e === 'pdf') href = `/pdf?f=${q}${hash}`;
      else if (LinkResolver.has(EXT.video, e)) href = `/watch?f=${q}`;
      else if (LinkResolver.has(EXT.audio, e)) href = `/listen?f=${q}`;
      else if (LinkResolver.has(EXT.image, e)) href = `/raw?f=${q}`;
      else if (LinkResolver.has(EXT.binary, e)) href = `/raw?dl=1&f=${q}`;
      else href = `/view?f=${q}${hash}`;
      return {href};
    }
    static linkTag(inner, u, t) {
      u = String(u || '').replace(/^<|>$/g, '');
      const r = LinkResolver.safeUrl(u, false);
      if (!r) return inner;
      return `<a href="${esc(r.href)}"${t ? ` title="${esc(t)}"` : ''}${r.ext ? ' target="_blank" rel="noopener noreferrer"' : ''}>${inner}</a>`;
    }
    static imgTag(alt, u, t) {
      u = String(u || '').replace(/^<|>$/g, '');
      const r = LinkResolver.safeUrl(u, true);
      if (!r) return esc(alt);
      return `<img src="${esc(r.href)}" alt="${esc(alt)}"${t ? ` title="${esc(t)}"` : ''} loading="lazy">`;
    }
  }

  
