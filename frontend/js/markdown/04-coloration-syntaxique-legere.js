/* ---------- Coloration syntaxique légère ---------- */
var KW = {};
function defKw(name, words){ var o = {}; words.split(' ').forEach(function(w){ o[w] = 1; }); KW[name] = o; }
defKw('js', 'async await break case catch class const continue debugger default delete do else export extends finally for from function if import in instanceof let new of return static super switch this throw try typeof var void while with yield true false null undefined interface type enum implements public private protected readonly abstract namespace declare as');
defKw('py', 'and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield True False None self');
defKw('sh', 'if then else elif fi for while do done case esac function in select until return export local echo cd exit set unset source alias sudo');
defKw('c', 'int char float double void long short unsigned signed struct union enum typedef static const extern return if else for while do switch case break continue goto sizeof class public private protected new delete this namespace using template typename virtual override final try catch throw throws import package interface implements extends abstract synchronized volatile bool true false null nil fn let mut impl trait pub use mod match loop where async await func go defer chan map range var type select fallthrough default echo function foreach as isset array string object');
defKw('sql', 'select from where insert into values update set delete create table alter drop join left right inner outer on group by order having limit offset and or not null is in as distinct union all primary key foreign references index unique default auto_increment varchar int text date timestamp boolean case when then else end like between exists view database use show describe');
defKw('json', 'true false null');
defKw('cfg', 'true false null yes no on off');
defKw('css', 'important');
var DQ = '"(?:\\\\.|[^"\\\\\\n])*"', SQ = "'(?:\\\\.|[^'\\\\\\n])*'";
var SPECS = {
  js: {c: '\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*', s: DQ + '|' + SQ + '|`(?:\\\\[\\s\\S]|[^`\\\\])*`', k: KW.js},
  c: {c: '\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*|#[^\\n]*', s: DQ + '|' + SQ, k: KW.c},
  py: {c: '#[^\\n]*', s: '"{3}[\\s\\S]*?"{3}|\'{3}[\\s\\S]*?\'{3}|[rRbBfFuU]{0,2}' + DQ + '|[rRbBfFuU]{0,2}' + SQ, k: KW.py},
  sh: {c: '#[^\\n]*', s: '"(?:\\\\[\\s\\S]|[^"\\\\])*"|\'[^\']*\'', k: KW.sh},
  sql: {c: '--[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/', s: "'(?:''|\\\\.|[^'\\\\])*'|" + DQ + '|`[^`]*`', k: KW.sql, ci: true},
  json: {c: '\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*', s: DQ, k: KW.json, json: true},
  cfg: {c: '#[^\\n]*|;[^\\n]*', s: DQ + '|' + SQ, k: KW.cfg, ci: true, id: '[A-Za-z_.][\\w.-]*', prop: true},
  css: {c: '\\/\\*[\\s\\S]*?\\*\\/', s: DQ + '|' + SQ, k: KW.css, id: '@?-{0,2}[A-Za-z_][\\w-]*',
        n: '#[0-9a-fA-F]{3,8}\\b|\\b\\d[\\d.]*(?:px|r?em|vh|vw|ms|deg|fr|s|%)?', prop: true, at: true}
};
var LANG = {
  js: 'js', javascript: 'js', mjs: 'js', cjs: 'js', jsx: 'js', ts: 'js', typescript: 'js', tsx: 'js',
  py: 'py', python: 'py', python3: 'py',
  sh: 'sh', bash: 'sh', zsh: 'sh', shell: 'sh', console: 'sh',
  c: 'c', h: 'c', cpp: 'c', 'c++': 'c', cc: 'c', hpp: 'c', java: 'c', cs: 'c', csharp: 'c', go: 'c', rust: 'c', rs: 'c',
  php: 'c', kotlin: 'c', swift: 'c', dart: 'c', scala: 'c',
  sql: 'sql', mysql: 'sql', postgres: 'sql', postgresql: 'sql', sqlite: 'sql',
  json: 'json', jsonc: 'json',
  yaml: 'cfg', yml: 'cfg', toml: 'cfg', ini: 'cfg', conf: 'cfg', env: 'cfg', dotenv: 'cfg', properties: 'cfg',
  css: 'css', scss: 'css', less: 'css',
  html: 'html', xml: 'html', svg: 'html', vue: 'html', xhtml: 'html',
  diff: 'diff', patch: 'diff'
};
function lex(code, spec){
  var num = spec.n || '\\b0[xX][0-9a-fA-F_]+\\b|\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b';
  var id = spec.id || '[A-Za-z_$@][\\w$]*';
  var re = new RegExp('(' + spec.c + ')|(' + spec.s + ')|(' + num + ')|(' + id + ')', 'g');
  var out = '', last = 0, m, rest, w;
  while ((m = re.exec(code))) {
    if (m[0] === '') { re.lastIndex++; continue; }
    out += esc(code.slice(last, m.index));
    last = re.lastIndex;
    rest = code.slice(last, last + 24);
    if (m[1] !== undefined) out += '<i class="c">' + esc(m[0]) + '</i>';
    else if (m[2] !== undefined) out += '<i class="' + (spec.json && /^\s*:/.test(rest) ? 'p' : 's') + '">' + esc(m[0]) + '</i>';
    else if (m[3] !== undefined) out += '<i class="n">' + esc(m[0]) + '</i>';
    else {
      w = m[4];
      var key = spec.ci ? w.toLowerCase() : w;
      if (spec.at && w.charAt(0) === '@') out += '<i class="k">' + esc(w) + '</i>';
      else if (spec.prop && /^[ \t]*[:=]/.test(rest)) out += '<i class="p">' + esc(w) + '</i>';
      else if (spec.k[key] === 1) out += '<i class="k">' + esc(w) + '</i>';
      else if (/^[ \t]*\(/.test(rest)) out += '<i class="f">' + esc(w) + '</i>';
      else if (/^[A-Z][a-z]/.test(w)) out += '<i class="t">' + esc(w) + '</i>';
      else out += esc(w);
    }
  }
  return out + esc(code.slice(last));
}
function hlHtml(code){
  var re = /(<!--[\s\S]*?-->|<![A-Za-z][^>]*>)|(<\/?)([A-Za-z][\w:-]*)((?:\s+[^\s=>\/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)(\s*\/?>)/g;
  var out = '', last = 0, m;
  while ((m = re.exec(code))) {
    out += esc(code.slice(last, m.index));
    last = re.lastIndex;
    if (m[1] !== undefined) { out += '<i class="c">' + esc(m[0]) + '</i>'; continue; }
    out += esc(m[2]) + '<i class="k">' + esc(m[3]) + '</i>';
    out += m[4].replace(/(\s+)([^\s=]+)(?:(\s*=\s*)("[^"]*"|'[^']*'|[^\s]+))?/g, function(x, sp, name, eq, val){
      return esc(sp) + '<i class="p">' + esc(name) + '</i>' + (eq ? esc(eq) + '<i class="s">' + esc(val) + '</i>' : '');
    });
    out += esc(m[5]);
  }
  return out + esc(code.slice(last));
}
function hlDiff(code){
  return code.split('\n').map(function(l){
    var c = /^(?:\+\+\+|---)/.test(l) ? 'h' : l.charAt(0) === '+' ? 'da' : l.charAt(0) === '-' ? 'dd' : /^@@/.test(l) ? 'h' : '';
    return c ? '<i class="' + c + '">' + esc(l) + '</i>' : esc(l);
  }).join('\n');
}
function highlight(code, lang){
  var l = LANG[lang];
  if (!l || code.length > 120000) return esc(code);
  try {
    if (l === 'html') return hlHtml(code);
    if (l === 'diff') return hlDiff(code);
    return lex(code, SPECS[l]);
  } catch(e) { return esc(code); }
}
function codeBlock(code, info){
  var lang = (info.split(/\s+/)[0] || '').replace(/^\{\.?|\}$/g, '').replace(/^\./, '').toLowerCase();
  return '<figure class="code"><figcaption><span class="lang">' + esc(lang || 'texte') +
    '</span><button type="button" class="copy">Copier</button></figcaption><pre><code>' +
    highlight(code, lang) + '</code></pre></figure>';
}

