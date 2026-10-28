(function(){
  var H = {'X-Requested-With': 'biblio'};
  var I = window.DCFG || {};
  var $ = function(id){ return document.getElementById(id); };
  function el(tag, cls, text){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function pct(p){ return String(p).replace('.', ','); }
  function ago(s){
    if (s === null) return 'pas vu depuis le démarrage';
    if (s < 5) return "à l'instant";
    if (s < 60) return 'il y a ' + s + ' s';
    if (s < 3600) return 'il y a ' + Math.floor(s / 60) + ' min';
    if (s < 86400) return 'il y a ' + Math.floor(s / 3600) + ' h';
    return 'il y a ' + Math.floor(s / 86400) + ' j';
  }
  function fmtBytes(n){
    var u = [['Go', 1073741824], ['Mo', 1048576], ['Ko', 1024]];
    for (var i = 0; i < u.length; i++) {
      if (n >= u[i][1]) {
        var v = n / u[i][1];
        return (v < 10 ? v.toFixed(1) : String(Math.round(v))).replace('.', ',') + ' ' + u[i][0];
      }
    }
    return Math.round(n) + ' o';
  }
  function fmtDur(s){
    s = Math.round(s);
    if (s < 60) return s + ' s';
    var m = Math.floor(s / 60);
    if (m < 60) return m + ' min';
    var h = Math.floor(m / 60);
    m = m % 60;
    return h + ' h' + (m ? ' ' + ('0' + m).slice(-2) : '');
  }
  function fmtMetric(v, metric){
    return metric === 'bytes' ? fmtBytes(v) : (metric === 'seconds' ? fmtDur(v) : String(Math.round(v)));
  }
  function niceFor(v, metric){
    if (!(v > 0)) return metric === 'actions' ? 4 : 1;
    if (metric === 'actions') return Math.max(4, Math.ceil(v / 4) * 4);
    var div = 1;
    if (metric === 'bytes') div = v >= 1073741824 ? 1073741824 : (v >= 1048576 ? 1048576 : (v >= 1024 ? 1024 : 1));
    else div = v >= 3600 ? 3600 : (v >= 60 ? 60 : 1);
    var x = v / div, p = Math.pow(10, Math.floor(Math.log(x) / Math.LN10)), m = x / p;
    return (m <= 1 ? 1 : (m <= 2 ? 2 : (m <= 5 ? 5 : 10))) * p * div;
  }
  function f1(x){ return x.toFixed(1); }

