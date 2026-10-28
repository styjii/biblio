/* ---------- Titres ---------- */
var slugs = Object.create(null), heads = [];
function slugify(t){
  t = t.toLowerCase().trim();
  try { t = t.replace(/[^\p{L}\p{N}\p{M}_\- ]/gu, ''); } catch(e) { t = t.replace(/[^\w\- ]/g, ''); }
  return t.replace(/ /g, '-');
}
function plain(html){ return new DOMParser().parseFromString('<body>' + html + '</body>', 'text/html').body.textContent; }
function heading(level, text){
  var html = ih(text.trim()), pt = plain(html).trim();
  var base = slugify(pt) || 'section', id = base, k = 1;
  while (slugs[id]) id = base + '-' + (k++);
  slugs[id] = 1;
  heads.push({level: level, id: id, text: pt});
  return '<h' + level + ' id="' + esc(id) + '">' + html +
    '<a class="anc" href="#' + esc(id) + '" aria-label="Lien vers cette section">#</a></h' + level + '>';
}

