(function(){
  var cfg = window.WCFG, I = window.WICO || {};
  var items = cfg.items, n = items.length, idx = cfg.index;
  var $ = function(id){ return document.getElementById(id); };
  var v = $('player'), auto = $('autonext'), vslider = $('w-vol');
  var posKey = 'vl:pos:' + cfg.key;
  var shuffle = false, repeat = 'off', rates = [0.75, 1, 1.25, 1.5, 1.75, 2], rate = 1;
  var order = [], pos = 0, msgT = 0;
  function load(k, d){ try { var x = localStorage.getItem('vl:' + k); return x === null ? d : x; } catch(e) { return d; } }
  function store(k, x){ try { localStorage.setItem('vl:' + k, x); } catch(e) {} }

  // préférences conservées d'une vidéo à l'autre
  shuffle = load('shuffle', '0') === '1';
  repeat = ['off', 'all', 'one'].indexOf(load('repeat', 'off')) >= 0 ? load('repeat', 'off') : 'off';
  rate = parseFloat(load('rate', '1')); if (rates.indexOf(rate) < 0) rate = 1;
  var vol = parseFloat(load('vol', '1')); if (!(vol >= 0 && vol <= 1)) vol = 1;
  v.volume = vol; v.muted = load('muted', '0') === '1';
  v.defaultPlaybackRate = rate; v.playbackRate = rate;

  // message court sous les commandes (s'efface seul)
  function say(t){
    clearTimeout(msgT);
    $('w-msg').textContent = t || '';
    if (t) msgT = setTimeout(function(){ $('w-msg').textContent = ''; }, 4000);
  }
  function setIcon(btn, name){ btn.innerHTML = I[name] || ''; }
  function play(){
    var pr = v.play();
    if (pr && pr.catch) pr.catch(function(){});     // lecture interrompue ou refusée : sans conséquence
  }
  function seekBy(d){ v.currentTime = Math.max(0, Math.min(v.duration || 1e9, v.currentTime + d)); }

