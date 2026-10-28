/* ---------- URL : chemins relatifs, liens sûrs ---------- */
function extOf(p){ var m = /\.([A-Za-z0-9]+)$/.exec(p); return m ? m[1].toLowerCase() : ''; }
function has(list, e){ return !!e && list.indexOf(e) >= 0; }
function joinPath(base, rel){
  var parts = (base ? base.split('/') : []).concat(rel.split('/')), out = [];
  parts.forEach(function(s){
    if (s === '' || s === '.') return;
    if (s === '..') out.pop(); else out.push(s);
  });
  return out.join('/');
}
function safeUrl(u, isImg){
  u = String(u || '').trim();
  if (!u) return null;
  if (/^(?:https?:)?\/\//i.test(u)) return {href: u, ext: true};
  if (u.charAt(0) === '#') return isImg ? null : {href: u};
  if (/^(?:mailto|tel):/i.test(u)) return isImg ? null : {href: u};
  if (/^data:image\/(?:png|jpe?g|gif|webp|avif|svg\+xml)[;,]/i.test(u)) return isImg ? {href: u} : null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(u)) return null;
  var m = /^([^?#]*)([?#][\s\S]*)?$/.exec(u), path = m[1], tail = m[2] || '';
  try { path = decodeURIComponent(path); } catch(e) {}
  var full = path.charAt(0) === '/' ? joinPath('', path) : joinPath(cfg.dir, path);
  var hi = tail.indexOf('#'), hash = hi >= 0 ? tail.slice(hi) : '';
  if (!full) return hash ? {href: hash} : null;
  var q = encodeURIComponent(full), e = extOf(full), href;
  if (isImg) href = e === 'svg' ? cfg.site + full.split('/').map(encodeURIComponent).join('/') : '/raw?f=' + q;
  else if (has(EXT.md, e) || has(EXT.web, e)) href = '/preview?f=' + q + hash;
  else if (e === 'pdf') href = '/pdf?f=' + q + hash;
  else if (has(EXT.video, e)) href = '/watch?f=' + q;
  else if (has(EXT.audio, e)) href = '/listen?f=' + q;
  else if (has(EXT.image, e)) href = '/raw?f=' + q;
  else if (has(EXT.binary, e)) href = '/raw?dl=1&f=' + q;
  else href = '/view?f=' + q + hash;
  return {href: href};
}
function linkTag(inner, u, t){
  u = String(u || '').replace(/^<|>$/g, '');
  var r = safeUrl(u, false);
  if (!r) return inner;
  return '<a href="' + esc(r.href) + '"' + (t ? ' title="' + esc(t) + '"' : '') +
    (r.ext ? ' target="_blank" rel="noopener noreferrer"' : '') + '>' + inner + '</a>';
}
function imgTag(alt, u, t){
  u = String(u || '').replace(/^<|>$/g, '');
  var r = safeUrl(u, true);
  if (!r) return esc(alt);
  return '<img src="' + esc(r.href) + '" alt="' + esc(alt) + '"' + (t ? ' title="' + esc(t) + '"' : '') + ' loading="lazy">';
}

