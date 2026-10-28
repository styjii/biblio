  /* ----- lecture ----- */
  function start(k, wantPlay){
    clearTimeout(errT);
    idx = k;
    var t = T[k];
    $('l-count').textContent = 'Piste ' + (k + 1) + ' sur ' + n;
    $('l-dl').href = '/raw?dl=1&f=' + t.q;
    try { history.replaceState(null, '', '/listen?f=' + t.q); } catch(e) {}
    applyTitle(null); setCover(null, k);
    getInfo(k).then(function(j){
      if (k !== idx) return;
      applyTitle(j); setCover(j, k); showDur(k, j && j.duration);
    });
    a.src = '/raw?f=' + t.q;
    a.defaultPlaybackRate = rate; a.playbackRate = rate;
    say('');
    markCurrent(); reveal();
    loading = !!wantPlay;
    if (wantPlay) play();
    renderSeek(); renderPlay();
  }
  function playIndex(k){
    idx = k; rebuild();
    start(k, true);
  }
  function wrap(){
    // fin de liste : on repart du début ; en aléatoire, nouvelle série dont la piste qui vient de finir passe en dernier
    rebuild();
    if (shuffle) order.push(order.shift());
    pos = 0;
    start(order[0], true);
  }
  function next(auto){
    if (pos + 1 < n) { pos++; start(order[pos], true); return; }
    if (repeat === 'all' || (!auto && n > 1)) { wrap(); return; }
    if (!auto) { a.currentTime = 0; play(); return; }       // une seule piste : « suivant » la relance
    a.pause(); a.currentTime = 0; renderPlay(); say('Fin de la liste.');
  }
  function prev(){
    if (a.currentTime > 3) { a.currentTime = 0; return; }
    if (pos > 0) { pos--; start(order[pos], true); return; }
    if (n > 1) { pos = n - 1; start(order[pos], true); return; }
    a.currentTime = 0;
  }
  function toggle(){ if (a.paused) play(); else a.pause(); }
  function seekBy(d){
    if (!isFinite(a.duration)) return;
    a.currentTime = Math.max(0, Math.min(a.duration, a.currentTime + d));
  }
  function setShuffle(v){
    shuffle = v; store('shuffle', v ? '1' : '0'); rebuild(); renderModes();
    say(v ? 'Lecture aléatoire activée.' : "Lecture dans l'ordre.");
  }
  function cycleRepeat(){
    repeat = repeat === 'off' ? 'all' : (repeat === 'all' ? 'one' : 'off');
    store('repeat', repeat); renderModes();
    say(repeat === 'off' ? 'Répétition désactivée.' : (repeat === 'all' ? 'Répétition de toutes les pistes.' : 'Répétition de la piste.'));
  }
  function setVol(v){
    v = Math.max(0, Math.min(1, v));
    a.volume = v; if (v > 0) a.muted = false;
    store('vol', v); store('muted', '0');
  }
  function toggleMute(){ a.muted = !a.muted; store('muted', a.muted ? '1' : '0'); }
  function setRate(r){
    rate = r; a.defaultPlaybackRate = r; a.playbackRate = r; store('rate', r); renderRate();
    say('Vitesse : ' + String(r).replace('.', ',') + '×');
  }
  function stepRate(d){
    var i = rates.indexOf(rate) + d;
    setRate(rates[Math.max(0, Math.min(rates.length - 1, i))]);
  }

