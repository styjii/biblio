  /* ----- ordre de lecture : l'ordre aléatoire est conservé d'une vidéo à l'autre (onglet courant) ----- */
  var orderKey = 'vl:order:' + cfg.folder;
  var sig = (function(s){ var h = 0; for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return h + ':' + n; })(
    items.map(function(t){ return t.f; }).join('|'));
  function saveOrder(nextIdx){
    try { sessionStorage.setItem(orderKey, JSON.stringify({sig: sig, order: order, cur: idx, next: nextIdx})); } catch(e) {}
  }
  function rebuild(){
    var i, rest = [];
    if (shuffle) {
      for (i = 0; i < n; i++) if (i !== idx) rest.push(i);
      for (i = rest.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1)), t = rest[i];
        rest[i] = rest[j]; rest[j] = t;
      }
      order = [idx].concat(rest); pos = 0;
    } else {
      order = []; for (i = 0; i < n; i++) order.push(i);
      pos = idx;
    }
  }
  // à l'ouverture de la page : on poursuit l'ordre en cours si on y arrive par « suivante » / « précédente » (ou rechargement)
  function restoreOrder(){
    var rec = null;
    if (shuffle) {
      try { rec = JSON.parse(sessionStorage.getItem(orderKey)); } catch(e) {}
      if (rec && rec.sig === sig && rec.order && rec.order.length === n && (rec.cur === idx || rec.next === idx)) {
        order = rec.order; pos = order.indexOf(idx);
        if (pos >= 0) { saveOrder(-1); return; }
      }
    }
    rebuild(); saveOrder(-1);
  }
  function go(k){ saveOrder(k); location.href = items[k].u; }
  function wrap(){
    // fin de liste : on repart du début ; en aléatoire, nouvelle série dont la vidéo qui vient de finir passe en dernier
    rebuild();
    if (shuffle) order.push(order.shift());
    pos = 0;
    go(order[0]);
  }
  function next(autoNext){
    if (pos + 1 < n) { go(order[pos + 1]); return; }
    if (repeat === 'all' || (!autoNext && n > 1)) { wrap(); return; }
    if (!autoNext) { v.currentTime = 0; play(); return; }      // une seule vidéo : « suivante » la relance
    say('Fin de la liste.');
  }
  function prev(){
    if (v.currentTime > 3) { v.currentTime = 0; return; }
    if (pos > 0) { go(order[pos - 1]); return; }
    if (n > 1) { go(order[n - 1]); return; }
    v.currentTime = 0;
  }
  function setShuffle(on){
    shuffle = on; store('shuffle', on ? '1' : '0'); rebuild(); saveOrder(-1); renderModes();
    say(on ? 'Lecture aléatoire activée.' : "Lecture dans l'ordre.");
  }
  function cycleRepeat(){
    repeat = repeat === 'off' ? 'all' : (repeat === 'all' ? 'one' : 'off');
    store('repeat', repeat); renderModes();
    say(repeat === 'off' ? 'Répétition désactivée.' : (repeat === 'all' ? 'Répétition de toutes les vidéos.' : 'Répétition de la vidéo.'));
  }
  function renderModes(){
    $('w-shuffle').classList.toggle('on', shuffle);
    $('w-shuffle').setAttribute('aria-pressed', shuffle ? 'true' : 'false');
    var rb = $('w-repeat');
    setIcon(rb, repeat === 'one' ? 'repeat1' : 'repeat');
    rb.classList.toggle('on', repeat !== 'off');
    rb.setAttribute('aria-pressed', repeat !== 'off' ? 'true' : 'false');
    rb.setAttribute('aria-label', 'Répétition : ' + (repeat === 'off' ? 'désactivée' : (repeat === 'all' ? 'toutes les vidéos' : 'cette vidéo')));
    rb.title = 'Répétition (R) : ' + (repeat === 'off' ? 'aucune' : (repeat === 'all' ? 'tout' : 'une vidéo'));
    v.loop = repeat === 'one';
  }

