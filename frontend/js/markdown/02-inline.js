/* ---------- Inline ---------- */
var refs = Object.create(null), fnDefs = Object.create(null), fnOrder = [], stash = [];
function keep(h){ stash.push(h); return '\u0001' + (stash.length - 1) + '\u0002'; }
function unstash(s){
  var guard = 0;
  while (/\u0001\d+\u0002/.test(s) && guard++ < 24) {
    s = s.replace(/\u0001(\d+)\u0002/g, function(m, n){ return stash[+n]; });
  }
  return s;
}
function inline(s){
  s = s.replace(/(?: {2,}|\\)\n/g, function(){ return keep('<br>') + '\n'; });
  s = s.replace(/(`+)([\s\S]*?[^`])\1(?!`)/g, function(m, a, c){
    c = c.replace(/\n/g, ' ');
    if (/^ [\s\S]* $/.test(c) && /\S/.test(c)) c = c.slice(1, -1);
    return keep('<code>' + esc(c) + '</code>');
  });
  s = s.replace(/\\([\\`*_{}\[\]()#+\-.!|~<>=$"'&])/g, function(m, c){ return keep(esc(c)); });
  s = s.replace(/!\[([^\]]*)\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+"([^"]*)")?\s*\)/g, function(m, alt, u, t){
    return keep(imgTag(alt, u, t));
  });
  s = s.replace(/!\[([^\]]*)\]\[([^\]]*)\]/g, function(m, alt, id){
    var r = refs[(id || alt).toLowerCase()];
    return r ? keep(imgTag(alt, r.u, r.t)) : m;
  });
  s = s.replace(/\[\^([^\]\s]+)\]/g, function(m, id){
    if (!(id in fnDefs)) return m;
    var n = fnOrder.indexOf(id);
    if (n < 0) { fnOrder.push(id); n = fnOrder.length - 1; }
    return keep('<sup class="fnref"><a href="#fn-' + esc(id) + '" id="fnref-' + esc(id) + '">' + (n + 1) + '</a></sup>');
  });
  s = s.replace(/\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*(<[^>]*>|[^)\s]*)(?:\s+"([^"]*)")?\s*\)/g, function(m, text, u, t){
    return keep(linkTag(inline(text), u, t));
  });
  s = s.replace(/\[((?:[^\[\]]|\[[^\]]*\])*)\]\[([^\]]*)\]/g, function(m, text, id){
    var r = refs[(id || text).toLowerCase()];
    return r ? keep(linkTag(inline(text), r.u, r.t)) : m;
  });
  s = s.replace(/\[([^\[\]]+)\](?!\()/g, function(m, id){
    var r = refs[id.toLowerCase()];
    return r ? keep(linkTag(esc(id), r.u, r.t)) : m;
  });
  s = s.replace(/<((?:https?:\/\/|mailto:)[^\s<>]+)>/gi, function(m, u){ return keep(linkTag(esc(u), u)); });
  s = s.replace(/<([^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)>/g, function(m, u){ return keep(linkTag(esc(u), 'mailto:' + u)); });
  s = s.replace(/(^|[\s(>])(https?:\/\/[^\s<]*[^\s<.,;:!?'")\]])/g, function(m, pre, u){
    return pre + keep(linkTag(esc(u), u));
  });
  s = s.replace(/<!--[\s\S]*?-->/g, '');
  s = s.replace(/<br\s*\/?>/gi, function(){ return keep('<br>'); });
  s = s.replace(/<(\/?)(kbd|sub|sup|mark|b|i|u|em|strong|del|ins|small|s|abbr|cite|q)>/gi, function(m, sl, t){
    return keep('<' + sl + t.toLowerCase() + '>');
  });
  s = esc(s);
  s = s.replace(/\*\*\*(?=\S)([\s\S]*?\S)\*\*\*/g, '<strong><em>$1</em></strong>')
       .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>')
       .replace(/(^|[^\w])__(?=\S)([\s\S]*?\S)__(?!\w)/g, '$1<strong>$2</strong>')
       .replace(/\*(?=[^\s*])([\s\S]*?[^\s*])\*/g, '<em>$1</em>')
       .replace(/(^|[^\w])_(?=[^\s_])([\s\S]*?[^\s_])_(?!\w)/g, '$1<em>$2</em>')
       .replace(/~~(?=\S)([\s\S]*?\S)~~/g, '<del>$1</del>')
       .replace(/==(?=\S)([\s\S]*?\S)==/g, '<mark>$1</mark>');
  return s;
}
function ih(s){ return unstash(inline(s)); }

