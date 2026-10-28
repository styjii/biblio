(function(){
  var cfg = window.LCFG, I = window.LICO || {};
  var T = cfg.tracks, n = T.length;
  var $ = function(id){ return document.getElementById(id); };
  var a = $('l-audio'), seek = $('l-seek'), vslider = $('l-vol'), cov = $('l-cover'), img = $('l-img');
  var idx = cfg.start, order = [], pos = 0, first = true, errRun = 0, errT = 0, msgT = 0;
  var shuffle = false, repeat = 'off', rates = [0.75, 1, 1.25, 1.5, 1.75, 2], rate = 1;
  var loading = false, seeking = false, lastSave = 0, rows = [], infos = {}, curRow = null;
  function load(k, d){ try { var v = localStorage.getItem('al:' + k); return v === null ? d : v; } catch(e) { return d; } }
  function store(k, v){ try { localStorage.setItem('al:' + k, v); } catch(e) {} }

  shuffle = load('shuffle', '0') === '1';
  repeat = ['off', 'all', 'one'].indexOf(load('repeat', 'off')) >= 0 ? load('repeat', 'off') : 'off';
  rate = parseFloat(load('rate', '1')); if (rates.indexOf(rate) < 0) rate = 1;
  var vol = parseFloat(load('vol', '1')); if (!(vol >= 0 && vol <= 1)) vol = 1;
  a.volume = vol; a.muted = load('muted', '0') === '1';

  function fmt(s){
    if (!isFinite(s) || s < 0) s = 0;
    s = Math.floor(s);
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), r = s % 60;
    return (h ? h + ':' + ('0' + m).slice(-2) : m) + ':' + ('0' + r).slice(-2);
  }
  // keep = true : le message reste (erreurs) ; sinon il s'efface seul
  function say(t, keep){
    clearTimeout(msgT);
    $('l-msg').textContent = t || '';
    if (t && !keep) msgT = setTimeout(function(){ $('l-msg').textContent = ''; }, 4000);
  }
  function setIcon(btn, name){ btn.innerHTML = I[name] || ''; }
  function play(){
    var pr = a.play();
    if (pr && pr.catch) pr.catch(function(e){
      if (e && e.name === 'AbortError') return;       // lecture interrompue par un changement de piste
      loading = false; renderPlay();
      if (e && e.name === 'NotAllowedError') say('Appuie sur lecture pour démarrer.', true);
    });
  }

