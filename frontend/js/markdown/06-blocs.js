/* ---------- Blocs ---------- */
var RE_ATX = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/;
var RE_HR = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
var RE_LIST = /^( *)([-*+]|\d{1,9}[.)])( +|$)(.*)$/;
var RE_QUOTE = /^ {0,3}> ?/;
var RE_TBL_SEP = /^ *\|? *:?-+:? *(?:\| *:?-+:? *)*\|? *$/;
var RE_HTML_BLOCK = /^ {0,3}<(?:p|div|center|table|h[1-6]|ul|ol|hr|img|picture|figure|section|a|br|blockquote|dl|pre)(?:[\s>\/]|$)/i;
var RE_HTML_INT = /^ {0,3}<(?:details|table|div|p|center|h[1-6]|ul|ol|hr|picture|figure|section|blockquote|dl|pre)(?:[\s>\/]|$)|^ {0,3}<!--/i;
var ALERTS = {
  note: {i: 'info', l: 'Note'}, tip: {i: 'bulb', l: 'Astuce'}, important: {i: 'msg_alert', l: 'Important'},
  warning: {i: 'alert', l: 'Avertissement'}, caution: {i: 'octagon', l: 'Attention'}
};
function isBlank(l){ return /^\s*$/.test(l); }
function leadSp(l){ return /^ */.exec(l)[0].length; }
function startsBlock(l){
  return /^ {0,3}(?:`{3,}|~{3,})/.test(l) || RE_ATX.test(l) || RE_HR.test(l) || /^ {0,3}>/.test(l) ||
    /^ {0,3}(?:[-*+]|1[.)])(?: +\S)/.test(l) || RE_HTML_INT.test(l);
}
function splitRow(l){
  l = l.trim();
  if (l.charAt(0) === '|') l = l.slice(1);
  if (/(^|[^\\])\|$/.test(l)) l = l.slice(0, -1);
  var cells = [], cur = '', i, c;
  for (i = 0; i < l.length; i++) {
    c = l.charAt(i);
    if (c === '\\' && l.charAt(i + 1) === '|') { cur += '|'; i++; continue; }
    if (c === '|') { cells.push(cur.trim()); cur = ''; } else cur += c;
  }
  cells.push(cur.trim());
  return cells;
}
function isTableAt(lines, i){
  if (i + 1 >= lines.length || lines[i].indexOf('|') < 0) return false;
  var sep = lines[i + 1];
  if (!RE_TBL_SEP.test(sep) || (sep.indexOf('|') < 0 && sep.indexOf(':') < 0)) return false;
  return splitRow(lines[i]).length === splitRow(sep).length;
}
function table(lines, i){
  var n = lines.length, head = splitRow(lines[i]);
  var al = splitRow(lines[i + 1]).map(function(c){
    var l = c.charAt(0) === ':', r = c.slice(-1) === ':';
    return l && r ? 'center' : r ? 'right' : l ? 'left' : '';
  });
  function cell(tag, c, k){
    return '<' + tag + (al[k] ? ' style="text-align:' + al[k] + '"' : '') + '>' + ih(c) + '</' + tag + '>';
  }
  var h = '<div class="tblwrap"><table><thead><tr>' + head.map(function(c, k){ return cell('th', c, k); }).join('') + '</tr></thead><tbody>';
  i += 2;
  while (i < n && !isBlank(lines[i]) && !startsBlock(lines[i])) {
    var row = splitRow(lines[i]);
    while (row.length < head.length) row.push('');
    row.length = head.length;
    h += '<tr>' + row.map(function(c, k){ return cell('td', c, k); }).join('') + '</tr>';
    i++;
  }
  return {html: h + '</tbody></table></div>', next: i};
}
function quote(qb){
  var m = /^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*(.*)$/i.exec(qb[0] || '');
  if (m) {
    var t = m[1].toLowerCase(), rest = qb.slice(1), A = ALERTS[t];
    if (m[2]) rest.unshift(m[2]);
    return '<div class="alert alert-' + t + '"><p class="alert-t">' + (ICO[A.i] || '') + '<span>' + A.l + '</span></p>' + blocks(rest) + '</div>';
  }
  return '<blockquote>' + blocks(qb) + '</blockquote>';
}
function sameKind(m, ordered, ch){
  return !!m && /^\d/.test(m[2]) === ordered && (ordered ? m[2].slice(-1) : m[2]) === ch;
}
function parseList(lines, i){
  var n = lines.length, first = RE_LIST.exec(lines[i]);
  var ordered = /^\d/.test(first[2]), ch = ordered ? first[2].slice(-1) : first[2];
  var start = ordered ? parseInt(first[2], 10) : 1, items = [], loose = false;
  while (i < n) {
    var m = RE_LIST.exec(lines[i]);
    if (!sameKind(m, ordered, ch)) break;
    var pad = m[3].length, w = m[1].length + m[2].length + ((pad === 0 || pad > 4) ? 1 : pad);
    var item = [m[4]];
    i++;
    while (i < n) {
      var l = lines[i];
      if (isBlank(l)) {
        var j = i + 1;
        while (j < n && isBlank(lines[j])) j++;
        if (j < n && leadSp(lines[j]) >= w) { for (; i < j; i++) item.push(''); continue; }
        break;
      }
      if (leadSp(l) >= w) { item.push(l.slice(w)); i++; continue; }
      if (!isBlank(item[item.length - 1]) && !startsBlock(l) && !RE_LIST.test(l)) { item.push(l.replace(/^ +/, '')); i++; continue; }
      break;
    }
    items.push(item);
    if (i < n && isBlank(lines[i])) {
      var k = i;
      while (k < n && isBlank(lines[k])) k++;
      var m2 = k < n ? RE_LIST.exec(lines[k]) : null;
      if (sameKind(m2, ordered, ch) && leadSp(lines[k]) < 4) { loose = true; i = k; continue; }
      break;
    }
  }
  var rendered = items.map(function(item){
    var task = null, tm = /^\[([ xX])\](?:[ \t]+|$)/.exec(item[0]);
    if (tm) { task = tm[1] !== ' '; item = [item[0].slice(tm[0].length)].concat(item.slice(1)); }
    var info = {}, h = blocks(item, true, info);
    if (info.gap) loose = true;
    return {h: h, task: task};
  });
  var tag = ordered ? 'ol' : 'ul';
  var hasTask = rendered.some(function(r){ return r.task !== null; });
  var html = '<' + tag + (ordered && start !== 1 ? ' start="' + start + '"' : '') + (hasTask ? ' class="contains-task-list"' : '') + '>' +
    rendered.map(function(r){
      var h = r.h;
      if (r.task !== null) {
        var cb = '<input type="checkbox" disabled' + (r.task ? ' checked' : '') + '>';
        h = h.charAt(0) === '\u0003' ? '\u0003' + cb + h.slice(1) : cb + h;
      }
      h = loose ? h.replace(/\u0003/g, '<p>').replace(/\u0004/g, '</p>') : h.replace(/[\u0003\u0004]/g, '');
      return '<li' + (r.task !== null ? ' class="task-item' + (r.task ? ' done' : '') + '"' : '') + '>' + h + '</li>';
    }).join('') + '</' + tag + '>';
  return {html: html, next: i};
}
function blocks(lines, defer, info){
  var out = [], i = 0, n = lines.length, gap = false, pend = false, m;
  function emit(h){ if (pend && out.length) gap = true; pend = false; out.push(h); }
  while (i < n) {
    var line = lines[i];
    if (isBlank(line)) { pend = true; i++; continue; }
    // code clôturé
    if ((m = /^( {0,3})(`{3,}|~{3,})(.*)$/.exec(line)) && !(m[2].charAt(0) === '`' && m[3].indexOf('`') >= 0)) {
      var ind = m[1].length, fence = m[2], finfo = m[3].trim(), buf = [];
      var closeRe = new RegExp('^ {0,3}' + fence.charAt(0) + '{' + fence.length + ',}\\s*$');
      i++;
      while (i < n && !closeRe.test(lines[i])) {
        buf.push(ind ? lines[i].replace(new RegExp('^ {0,' + ind + '}'), '') : lines[i]);
        i++;
      }
      i++;
      emit(codeBlock(buf.join('\n'), finfo));
      continue;
    }
    // code indenté
    if (/^ {4}/.test(line)) {
      var cb = [];
      while (i < n && (/^ {4}/.test(lines[i]) || isBlank(lines[i]))) { cb.push(lines[i].replace(/^ {4}/, '')); i++; }
      while (cb.length && isBlank(cb[cb.length - 1])) cb.pop();
      emit(codeBlock(cb.join('\n'), ''));
      continue;
    }
    if ((m = RE_ATX.exec(line))) { emit(heading(m[1].length, m[2] || '')); i++; continue; }
    if (RE_HR.test(line)) { emit('<hr>'); i++; continue; }
    // commentaire HTML
    if (/^ {0,3}<!--/.test(line)) {
      while (i < n && lines[i].indexOf('-->') < 0) i++;
      i++;
      continue;
    }
    // <details> : le contenu est du Markdown
    if (/^ {0,3}<details(?:\s[^>]*)?>/i.test(line)) {
      var depth = 0, j = i, dbuf = [];
      for (; j < n; j++) {
        depth += (lines[j].match(/<details[\s>]/gi) || []).length - (lines[j].match(/<\/details\s*>/gi) || []).length;
        dbuf.push(lines[j]);
        if (depth <= 0) break;
      }
      i = j + 1;
      var raw = dbuf.join('\n'), dm = /^\s*<details((?:\s[^>]*)?)>/i.exec(raw);
      raw = raw.slice(dm[0].length).replace(/<\/details\s*>\s*$/i, '');
      var sm = /^\s*<summary[^>]*>([\s\S]*?)<\/summary>/i.exec(raw), sum = 'Détails';
      if (sm) { sum = ih(sm[1].replace(/\s+/g, ' ').trim()); raw = raw.slice(sm[0].length); }
      emit('<details' + (/\bopen\b/i.test(dm[1]) ? ' open' : '') + '><summary>' + sum + '</summary>' + blocks(raw.split('\n')) + '</details>');
      continue;
    }
    // autres blocs HTML
    if (RE_HTML_BLOCK.test(line)) {
      var tag = /^ {0,3}<([a-z0-9]+)/i.exec(line)[1].toLowerCase();
      var stopBlank = /^(?:p|h[1-6]|a|img|hr|br|picture|figure|center)$/.test(tag);
      var openRe = new RegExp('<' + tag + '[\\s>/]', 'gi'), clRe = new RegExp('</' + tag + '\\s*>', 'gi');
      var hd = 0, hb = [];
      while (i < n) {
        var hl = lines[i];
        hd += (hl.match(openRe) || []).length - (hl.match(clRe) || []).length;
        hb.push(hl);
        i++;
        if ((stopBlank || hd <= 0) && (i >= n || isBlank(lines[i]))) break;
      }
      emit(cleanHtml(hb.join('\n')));
      continue;
    }
    if (RE_QUOTE.test(line)) {
      var qb = [];
      while (i < n && (RE_QUOTE.test(lines[i]) ||
             (!isBlank(lines[i]) && qb.length && !isBlank(qb[qb.length - 1]) && !startsBlock(lines[i])))) {
        qb.push(lines[i].replace(RE_QUOTE, ''));
        i++;
      }
      emit(quote(qb));
      continue;
    }
    if (RE_LIST.test(line) && !RE_HR.test(line)) {
      var pl2 = parseList(lines, i);
      emit(pl2.html);
      i = pl2.next;
      continue;
    }
    if (isTableAt(lines, i)) { var tb = table(lines, i); emit(tb.html); i = tb.next; continue; }
    // paragraphe (ou titre souligné)
    var pl = [], setext = 0;
    while (i < n && !isBlank(lines[i])) {
      if (pl.length) {
        if (/^ {0,3}=+[ \t]*$/.test(lines[i])) { setext = 1; i++; break; }
        if (/^ {0,3}-+[ \t]*$/.test(lines[i])) { setext = 2; i++; break; }
        if (startsBlock(lines[i]) || isTableAt(lines, i)) break;
      }
      pl.push(lines[i].replace(/^ +/, ''));
      i++;
    }
    var text = pl.join('\n').replace(/\s+$/, '');
    if (setext) emit(heading(setext, text.replace(/\n/g, ' ')));
    else emit('\u0003' + ih(text) + '\u0004');
  }
  if (info) info.gap = gap;
  var html = out.join('\n');
  return defer ? html : html.replace(/\u0003/g, '<p>').replace(/\u0004/g, '</p>');
}

