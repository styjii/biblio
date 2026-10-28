/* ---------- Document ---------- */
function prepare(text){
  var lines = [], fence = null, curFn = null, m, fm = '';
  var f = /^---[ \t]*\n([\s\S]*?)\n(?:---|\.\.\.)[ \t]*(?:\n|$)/.exec(text);
  if (f) {
    text = text.slice(f[0].length);
    var rows = '';
    f[1].split('\n').forEach(function(l){
      var kv = /^([\w.-]+):[ \t]*(.*)$/.exec(l);
      if (kv && kv[2]) rows += '<dt>' + esc(kv[1]) + '</dt><dd>' + esc(kv[2].replace(/^["']|["']$/g, '')) + '</dd>';
    });
    if (rows) fm = '<details class="fm"><summary>Métadonnées</summary><dl>' + rows + '</dl></details>';
  }
  text.split('\n').forEach(function(l){
    if (fence) {
      lines.push(l);
      if (new RegExp('^\\s*' + fence.charAt(0) + '{' + fence.length + ',}\\s*$').test(l)) fence = null;
      return;
    }
    if ((m = /^\s*(`{3,}|~{3,})(.*)$/.exec(l)) && !(m[1].charAt(0) === '`' && m[2].indexOf('`') >= 0)) {
      fence = m[1]; curFn = null; lines.push(l); return;
    }
    l = l.replace(/^\t+/, function(t){ return new Array(t.length + 1).join('    '); });
    if ((m = /^ {0,3}\[\^([^\]\s]+)\]:[ \t]?(.*)$/.exec(l))) { curFn = m[1]; fnDefs[curFn] = m[2]; return; }
    if (curFn && /^ {2,}\S/.test(l)) { fnDefs[curFn] += ' ' + l.trim(); return; }
    curFn = null;
    if ((m = /^ {0,3}\[([^\]^][^\]]*)\]:[ \t]*(<[^>]+>|\S+)(?:[ \t]+(?:"([^"]*)"|'([^']*)'|\(([^)]*)\)))?[ \t]*$/.exec(l))) {
      refs[m[1].toLowerCase()] = {u: m[2].replace(/^<|>$/g, ''), t: m[3] || m[4] || m[5] || ''};
      return;
    }
    lines.push(l);
  });
  return {lines: lines, fm: fm};
}
function footnotes(){
  if (!fnOrder.length) return '';
  return '<section class="footnotes"><ol>' + fnOrder.map(function(id){
    return '<li id="fn-' + esc(id) + '">' + ih(fnDefs[id]) + ' <a class="fnback" href="#fnref-' + esc(id) + '" aria-label="Retour au texte">retour</a></li>';
  }).join('') + '</ol></section>';
}

var art = $('md-art'), sc = $('md-scroll'), bar = $('md-bar'), tocNav = $('md-toc'), tocList = $('md-toc-list');
var prep = prepare(src), body = blocks(prep.lines);
art.innerHTML = (body.trim() || prep.fm) ? prep.fm + body + footnotes() : '<p class="empty">Ce fichier est vide.</p>';

