  /* ----- événements du lecteur ----- */
  function posKey(){ return 'al:pos:' + cfg.key + ':' + T[idx].f; }
  function posState(){
    if ('mediaSession' in navigator && navigator.mediaSession.setPositionState && isFinite(a.duration)) {
      try { navigator.mediaSession.setPositionState({duration: a.duration, playbackRate: a.playbackRate, position: Math.min(a.currentTime, a.duration)}); } catch(e) {}
    }
  }
  a.addEventListener('loadedmetadata', function(){
    errRun = 0;
    showDur(idx, a.duration);
    if (first) {
      first = false;
      try {
        var s = JSON.parse(localStorage.getItem(posKey()));
        if (s && s.t > 3 && s.t < a.duration - 5) a.currentTime = s.t;
      } catch(e) {}
    }
    renderSeek(); posState();
  });
  a.addEventListener('durationchange', renderSeek);
  a.addEventListener('progress', renderSeek);
  a.addEventListener('timeupdate', function(){
    renderSeek();
    var now = Date.now();
    if (now - lastSave > 2500 && a.duration && !a.ended) {
      lastSave = now;
      try { localStorage.setItem(posKey(), JSON.stringify({t: a.currentTime})); } catch(e) {}
    }
  });
  a.addEventListener('waiting', function(){ if (!a.paused) { loading = true; renderPlay(); } });
  a.addEventListener('canplay', function(){ loading = false; renderPlay(); });
  a.addEventListener('playing', function(){ loading = false; renderPlay(); });
  a.addEventListener('play', function(){ renderPlay(); if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing'; });
  a.addEventListener('pause', function(){
    loading = false; renderPlay();
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
    try { if (a.duration && !a.ended) localStorage.setItem(posKey(), JSON.stringify({t: a.currentTime})); } catch(e) {}
  });
  a.addEventListener('ended', function(){
    try { localStorage.removeItem(posKey()); } catch(e) {}
    if (repeat === 'one') { a.currentTime = 0; play(); return; }
    next(true);
  });
  a.addEventListener('error', function(){
    loading = false;
    var c = a.error ? a.error.code : 0;
    var why = c === 2 ? 'Erreur réseau' : (c === 3 ? 'Fichier audio endommagé' : (c === 4 ? 'Format non pris en charge' : 'Lecture impossible'));
    if (rows[idx]) rows[idx].classList.add('bad');
    errRun++;
    var canSkip = n > 1 && errRun < n && (pos + 1 < n || repeat === 'all');
    say(why + ' : ' + T[idx].n + (canSkip ? ' — passage à la piste suivante…' : ''), true);
    renderPlay();
    if (canSkip) { clearTimeout(errT); errT = setTimeout(function(){ next(true); }, 1400); }
  });
  a.addEventListener('volumechange', renderVol);
  a.addEventListener('ratechange', posState);
  a.addEventListener('seeked', function(){ renderSeek(); posState(); });

