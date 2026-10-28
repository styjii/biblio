/* ---------- HTML brut : assaini via DOMParser (inerte) ---------- */
var HT = {}, HA = {}, DROP = {};
'a abbr b blockquote br caption center cite code col colgroup dd del details div dl dt em figcaption figure h1 h2 h3 h4 h5 h6 hr i img ins kbd li mark ol p picture pre q s small span strong sub summary sup table tbody td tfoot th thead tr u ul'
  .split(' ').forEach(function(t){ HT[t] = 1; });
'href src alt title width height align colspan rowspan open start valign'.split(' ').forEach(function(a){ HA[a] = 1; });
'script style iframe object embed noscript template textarea svg math link meta form input button select audio video source'.split(' ')
  .forEach(function(t){ DROP[t] = 1; });
var VOID = {br: 1, hr: 1, img: 1, col: 1};
function cleanHtml(str){
  var doc = new DOMParser().parseFromString('<body>' + str + '</body>', 'text/html');
  function walk(node){
    var out = '';
    node.childNodes.forEach(function(c){
      if (c.nodeType === 3) { out += esc(c.nodeValue); return; }
      if (c.nodeType !== 1) return;
      var t = c.tagName.toLowerCase();
      if (DROP[t]) return;
      var inner = VOID[t] ? '' : walk(c);
      if (!HT[t]) { out += inner; return; }
      var attrs = '', ext = false;
      Array.prototype.forEach.call(c.attributes, function(a){
        var n = a.name.toLowerCase(), v = a.value;
        if (!HA[n]) return;
        if (n === 'href' || n === 'src') {
          var r = safeUrl(v, t === 'img');
          if (!r) return;
          if (r.ext && n === 'href') ext = true;
          v = r.href;
        } else if (n === 'align') {
          if (!/^(?:left|right|center|justify)$/i.test(v)) return;
        } else if (n === 'width' || n === 'height' || n === 'colspan' || n === 'rowspan' || n === 'start') {
          if (!/^\d+%?$/.test(v)) return;
        } else if (n === 'open') {
          v = '';
        }
        attrs += ' ' + n + '="' + esc(v) + '"';
      });
      if (t === 'a' && ext) attrs += ' target="_blank" rel="noopener noreferrer"';
      if (t === 'img') attrs += ' loading="lazy"';
      out += VOID[t] ? '<' + t + attrs + '>' : '<' + t + attrs + '>' + inner + '</' + t + '>';
    });
    return out;
  }
  return walk(doc.body);
}

