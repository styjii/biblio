  const RE_ATX = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/;
  const RE_HR = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
  const RE_LIST = /^( *)([-*+]|\d{1,9}[.)])( +|$)(.*)$/;
  const RE_QUOTE = /^ {0,3}> ?/;
  const RE_TBL_SEP = /^ *\|? *:?-+:? *(?:\| *:?-+:? *)*\|? *$/;
  const RE_HTML_BLOCK = /^ {0,3}<(?:p|div|center|table|h[1-6]|ul|ol|hr|img|picture|figure|section|a|br|blockquote|dl|pre)(?:[\s>\/]|$)/i;
  const RE_HTML_INT = /^ {0,3}<(?:details|table|div|p|center|h[1-6]|ul|ol|hr|picture|figure|section|blockquote|dl|pre)(?:[\s>\/]|$)|^ {0,3}<!--/i;
  const ALERTS = {
    note: {i: 'info', l: 'Note'},
    tip: {i: 'bulb', l: 'Astuce'},
    important: {i: 'msg_alert', l: 'Important'},
    warning: {i: 'alert', l: 'Avertissement'},
    caution: {i: 'octagon', l: 'Attention'},
  };
  /** Analyse des blocs Markdown : titres, listes (imbriquées, à cocher), citations et alertes, tableaux, code, HTML brut, <details>, paragraphes. */
  class BlockParser {
    static isBlank(l) {
      return /^\s*$/.test(l);
    }
    static leadSp(l) {
      return /^ */.exec(l)[0].length;
    }
    static startsBlock(l) {
      return (
        /^ {0,3}(?:`{3,}|~{3,})/.test(l) ||
        RE_ATX.test(l) ||
        RE_HR.test(l) ||
        /^ {0,3}>/.test(l) ||
        /^ {0,3}(?:[-*+]|1[.)])(?: +\S)/.test(l) ||
        RE_HTML_INT.test(l)
      );
    }
    static splitRow(l) {
      l = l.trim();
      if (l.charAt(0) === '|') l = l.slice(1);
      if (/(^|[^\\])\|$/.test(l)) l = l.slice(0, -1);
      const cells = [];
      let cur = '';
      let i;
      let c;
      for (i = 0; i < l.length; i++) {
        c = l.charAt(i);
        if (c === '\\' && l.charAt(i + 1) === '|') {
          cur += '|';
          i++;
          continue;
        }
        if (c === '|') {
          cells.push(cur.trim());
          cur = '';
        } else cur += c;
      }
      cells.push(cur.trim());
      return cells;
    }
    static isTableAt(lines, i) {
      if (i + 1 >= lines.length || !lines[i].includes('|')) return false;
      const sep = lines[i + 1];
      if (!RE_TBL_SEP.test(sep) || (!sep.includes('|') && !sep.includes(':'))) return false;
      return BlockParser.splitRow(lines[i]).length === BlockParser.splitRow(sep).length;
    }
    table(lines, i) {
      const n = lines.length;
      const head = BlockParser.splitRow(lines[i]);
      const al = BlockParser.splitRow(lines[i + 1]).map((c) => {
        const l = c.charAt(0) === ':';
        const r = c.slice(-1) === ':';
        return l && r ? 'center' : r ? 'right' : l ? 'left' : '';
      });
      const cell = (tag, c, k) => {
        return `<${tag}${al[k] ? ` style="text-align:${al[k]}"` : ''}>${inlineRenderer.html(c)}</${tag}>`;
      };
      let h = `<div class="tblwrap"><table><thead><tr>${head.map((c, k) => cell('th', c, k)).join('')}</tr></thead><tbody>`;
      i += 2;
      while (i < n && !BlockParser.isBlank(lines[i]) && !BlockParser.startsBlock(lines[i])) {
        const row = BlockParser.splitRow(lines[i]);
        while (row.length < head.length) row.push('');
        row.length = head.length;
        h += `<tr>${row.map((c, k) => cell('td', c, k)).join('')}</tr>`;
        i++;
      }
      return {html: `${h}</tbody></table></div>`, next: i};
    }
    quote(qb) {
      const m = /^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*(.*)$/i.exec(qb[0] || '');
      if (m) {
        const t = m[1].toLowerCase();
        const rest = qb.slice(1);
        const A = ALERTS[t];
        if (m[2]) rest.unshift(m[2]);
        return `<div class="alert alert-${t}"><p class="alert-t">${ICO[A.i] || ''}<span>${A.l}</span></p>${this.blocks(rest)}</div>`;
      }
      return `<blockquote>${this.blocks(qb)}</blockquote>`;
    }
    static sameKind(m, ordered, ch) {
      return !!m && /^\d/.test(m[2]) === ordered && (ordered ? m[2].slice(-1) : m[2]) === ch;
    }
    parseList(lines, i) {
      const n = lines.length;
      const first = RE_LIST.exec(lines[i]);
      const ordered = /^\d/.test(first[2]);
      const ch = ordered ? first[2].slice(-1) : first[2];
      const start = ordered ? parseInt(first[2], 10) : 1;
      const items = [];
      let loose = false;
      while (i < n) {
        const m = RE_LIST.exec(lines[i]);
        if (!BlockParser.sameKind(m, ordered, ch)) break;
        const pad = m[3].length;
        const w = m[1].length + m[2].length + (pad === 0 || pad > 4 ? 1 : pad);
        const item = [m[4]];
        i++;
        while (i < n) {
          const l = lines[i];
          if (BlockParser.isBlank(l)) {
            let j = i + 1;
            while (j < n && BlockParser.isBlank(lines[j])) j++;
            if (j < n && BlockParser.leadSp(lines[j]) >= w) {
              for (; i < j; i++) item.push('');
              continue;
            }
            break;
          }
          if (BlockParser.leadSp(l) >= w) {
            item.push(l.slice(w));
            i++;
            continue;
          }
          if (!BlockParser.isBlank(item[item.length - 1]) && !BlockParser.startsBlock(l) && !RE_LIST.test(l)) {
            item.push(l.replace(/^ +/, ''));
            i++;
            continue;
          }
          break;
        }
        items.push(item);
        if (i < n && BlockParser.isBlank(lines[i])) {
          let k = i;
          while (k < n && BlockParser.isBlank(lines[k])) k++;
          const m2 = k < n ? RE_LIST.exec(lines[k]) : null;
          if (BlockParser.sameKind(m2, ordered, ch) && BlockParser.leadSp(lines[k]) < 4) {
            loose = true;
            i = k;
            continue;
          }
          break;
        }
      }
      const rendered = items.map((item) => {
        let task = null;
        const tm = /^\[([ xX])\](?:[ \t]+|$)/.exec(item[0]);
        if (tm) {
          task = tm[1] !== ' ';
          item = [item[0].slice(tm[0].length)].concat(item.slice(1));
        }
        const info = {};
        const h = this.blocks(item, true, info);
        if (info.gap) loose = true;
        return {h, task};
      });
      const tag = ordered ? 'ol' : 'ul';
      const hasTask = rendered.some((r) => r.task !== null);
      const html = `<${tag}${ordered && start !== 1 ? ` start="${start}"` : ''}${hasTask ? ' class="contains-task-list"' : ''}>${rendered
        .map((r) => {
          let h = r.h;
          if (r.task !== null) {
            const cb = `<input type="checkbox" disabled${r.task ? ' checked' : ''}>`;
            h = h.charAt(0) === '\u0003' ? `\u0003${cb}${h.slice(1)}` : cb + h;
          }
          h = loose ? h.replace(/\u0003/g, '<p>').replace(/\u0004/g, '</p>') : h.replace(/[\u0003\u0004]/g, '');
          return `<li${r.task !== null ? ` class="task-item${r.task ? ' done' : ''}"` : ''}>${h}</li>`;
        })
        .join('')}</${tag}>`;
      return {html, next: i};
    }
    blocks(lines, defer, info) {
      const out = [];
      let i = 0;
      const n = lines.length;
      let gap = false;
      let pend = false;
      let m;
      const emit = (h) => {
        if (pend && out.length) gap = true;
        pend = false;
        out.push(h);
      };
      while (i < n) {
        const line = lines[i];
        if (BlockParser.isBlank(line)) {
          pend = true;
          i++;
          continue;
        }
        // code clôturé
        if ((m = /^( {0,3})(`{3,}|~{3,})(.*)$/.exec(line)) && !(m[2].charAt(0) === '`' && m[3].includes('`'))) {
          const ind = m[1].length;
          const fence = m[2];
          const finfo = m[3].trim();
          const buf = [];
          const closeRe = new RegExp(`^ {0,3}${fence.charAt(0)}{${fence.length},}\\s*$`);
          i++;
          while (i < n && !closeRe.test(lines[i])) {
            buf.push(ind ? lines[i].replace(new RegExp(`^ {0,${ind}}`), '') : lines[i]);
            i++;
          }
          i++;
          emit(SyntaxHighlighter.codeBlock(buf.join('\n'), finfo));
          continue;
        }
        // code indenté
        if (/^ {4}/.test(line)) {
          const cb = [];
          while (i < n && (/^ {4}/.test(lines[i]) || BlockParser.isBlank(lines[i]))) {
            cb.push(lines[i].replace(/^ {4}/, ''));
            i++;
          }
          while (cb.length && BlockParser.isBlank(cb[cb.length - 1])) cb.pop();
          emit(SyntaxHighlighter.codeBlock(cb.join('\n'), ''));
          continue;
        }
        if ((m = RE_ATX.exec(line))) {
          emit(headings.render(m[1].length, m[2] || ''));
          i++;
          continue;
        }
        if (RE_HR.test(line)) {
          emit('<hr>');
          i++;
          continue;
        }
        // commentaire HTML
        if (/^ {0,3}<!--/.test(line)) {
          while (i < n && !lines[i].includes('-->')) i++;
          i++;
          continue;
        }
        // <details> : le contenu est du Markdown
        if (/^ {0,3}<details(?:\s[^>]*)?>/i.test(line)) {
          let depth = 0;
          let j = i;
          const dbuf = [];
          for (; j < n; j++) {
            depth += (lines[j].match(/<details[\s>]/gi) || []).length - (lines[j].match(/<\/details\s*>/gi) || []).length;
            dbuf.push(lines[j]);
            if (depth <= 0) break;
          }
          i = j + 1;
          let raw = dbuf.join('\n');
          const dm = /^\s*<details((?:\s[^>]*)?)>/i.exec(raw);
          raw = raw.slice(dm[0].length).replace(/<\/details\s*>\s*$/i, '');
          const sm = /^\s*<summary[^>]*>([\s\S]*?)<\/summary>/i.exec(raw);
          let sum = 'Détails';
          if (sm) {
            sum = inlineRenderer.html(sm[1].replace(/\s+/g, ' ').trim());
            raw = raw.slice(sm[0].length);
          }
          emit(`<details${/\bopen\b/i.test(dm[1]) ? ' open' : ''}><summary>${sum}</summary>${this.blocks(raw.split('\n'))}</details>`);
          continue;
        }
        // autres blocs HTML
        if (RE_HTML_BLOCK.test(line)) {
          const tag = /^ {0,3}<([a-z0-9]+)/i.exec(line)[1].toLowerCase();
          const stopBlank = /^(?:p|h[1-6]|a|img|hr|br|picture|figure|center)$/.test(tag);
          const openRe = new RegExp(`<${tag}[\\s>/]`, 'gi');
          const clRe = new RegExp(`</${tag}\\s*>`, 'gi');
          let hd = 0;
          const hb = [];
          while (i < n) {
            const hl = lines[i];
            hd += (hl.match(openRe) || []).length - (hl.match(clRe) || []).length;
            hb.push(hl);
            i++;
            if ((stopBlank || hd <= 0) && (i >= n || BlockParser.isBlank(lines[i]))) break;
          }
          emit(HtmlSanitizer.clean(hb.join('\n')));
          continue;
        }
        if (RE_QUOTE.test(line)) {
          const qb = [];
          while (
            i < n &&
            (RE_QUOTE.test(lines[i]) ||
              (!BlockParser.isBlank(lines[i]) && qb.length && !BlockParser.isBlank(qb[qb.length - 1]) && !BlockParser.startsBlock(lines[i])))
          ) {
            qb.push(lines[i].replace(RE_QUOTE, ''));
            i++;
          }
          emit(this.quote(qb));
          continue;
        }
        if (RE_LIST.test(line) && !RE_HR.test(line)) {
          const pl2 = this.parseList(lines, i);
          emit(pl2.html);
          i = pl2.next;
          continue;
        }
        if (BlockParser.isTableAt(lines, i)) {
          const tb = this.table(lines, i);
          emit(tb.html);
          i = tb.next;
          continue;
        }

        // paragraphe (ou titre souligné)
        const pl = [];

        let setext = 0;
        while (i < n && !BlockParser.isBlank(lines[i])) {
          if (pl.length) {
            if (/^ {0,3}=+[ \t]*$/.test(lines[i])) {
              setext = 1;
              i++;
              break;
            }
            if (/^ {0,3}-+[ \t]*$/.test(lines[i])) {
              setext = 2;
              i++;
              break;
            }
            if (BlockParser.startsBlock(lines[i]) || BlockParser.isTableAt(lines, i)) break;
          }
          pl.push(lines[i].replace(/^ +/, ''));
          i++;
        }
        const text = pl.join('\n').replace(/\s+$/, '');
        if (setext) emit(headings.render(setext, text.replace(/\n/g, ' ')));
        else emit(`\u0003${inlineRenderer.html(text)}\u0004`);
      }
      if (info) info.gap = gap;
      const html = out.join('\n');
      return defer ? html : html.replace(/\u0003/g, '<p>').replace(/\u0004/g, '</p>');
    }
  }

  const blockParser = new BlockParser();

  
