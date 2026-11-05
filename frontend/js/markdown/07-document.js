  /** Le document Markdown : préparation du texte et notes de bas de page. */
  class MarkdownDocument {
    /** Prépare le texte : métadonnées (en-tête YAML), définitions de liens et de notes mises de côté, tabulations remplacées. -> {lines, fm} */
    static prepare(text) {
      const lines = [];
      let fence = null;
      let curFn = null;
      let m;
      let fm = '';
      const f = /^---[ \t]*\n([\s\S]*?)\n(?:---|\.\.\.)[ \t]*(?:\n|$)/.exec(text);
      if (f) {
        text = text.slice(f[0].length);
        let rows = '';
        f[1].split('\n').forEach((l) => {
          const kv = /^([\w.-]+):[ \t]*(.*)$/.exec(l);
          if (kv && kv[2]) rows += `<dt>${esc(kv[1])}</dt><dd>${esc(kv[2].replace(/^["']|["']$/g, ''))}</dd>`;
        });
        if (rows) fm = `<details class="fm"><summary>Métadonnées</summary><dl>${rows}</dl></details>`;
      }
      text.split('\n').forEach((l) => {
        if (fence) {
          lines.push(l);
          if (new RegExp(`^\\s*${fence.charAt(0)}{${fence.length},}\\s*$`).test(l)) fence = null;
          return;
        }
        if ((m = /^\s*(`{3,}|~{3,})(.*)$/.exec(l)) && !(m[1].charAt(0) === '`' && m[2].includes('`'))) {
          fence = m[1];
          curFn = null;
          lines.push(l);
          return;
        }
        l = l.replace(/^\t+/, (t) => ' '.repeat(t.length * 4));
        if ((m = /^ {0,3}\[\^([^\]\s]+)\]:[ \t]?(.*)$/.exec(l))) {
          curFn = m[1];
          refs.footnotes[curFn] = m[2];
          return;
        }
        if (curFn && /^ {2,}\S/.test(l)) {
          refs.footnotes[curFn] += ` ${l.trim()}`;
          return;
        }
        curFn = null;
        if ((m = /^ {0,3}\[([^\]^][^\]]*)\]:[ \t]*(<[^>]+>|\S+)(?:[ \t]+(?:"([^"]*)"|'([^']*)'|\(([^)]*)\)))?[ \t]*$/.exec(l))) {
          refs.links[m[1].toLowerCase()] = {u: m[2].replace(/^<|>$/g, ''), t: m[3] || m[4] || m[5] || ''};
          return;
        }
        lines.push(l);
      });
      return {lines, fm};
    }
    /** Section des notes de bas de page, dans l'ordre où elles sont citées. */
    static footnotes() {
      if (!refs.order.length) return '';
      return `<section class="footnotes"><ol>${refs.order.map((id) => `<li id="fn-${esc(id)}">${inlineRenderer.html(refs.footnotes[id])} <a class="fnback" href="#fnref-${esc(id)}" aria-label="Retour au texte">retour</a></li>`).join('')}</ol></section>`;
    }
  }

  const art = $('md-art');
  const sc = $('md-scroll');
  const bar = $('md-bar');
  const tocNav = $('md-toc');
  const tocList = $('md-toc-list');
  const prep = MarkdownDocument.prepare(source);
  const body = blockParser.blocks(prep.lines);
  art.innerHTML = body.trim() || prep.fm ? prep.fm + body + MarkdownDocument.footnotes() : '<p class="empty">Ce fichier est vide.</p>';

  
