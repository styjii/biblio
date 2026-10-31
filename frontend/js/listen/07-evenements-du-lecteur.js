  /* ----- événements du lecteur ----- */
  /* ----- reprise : dernière position de CET appareil pour la piste ouverte au chargement, mémorisée par le serveur ----- */
  var legacyKey = 'al:pos:' + cfg.key + ':' + T[idx].f;      // ancien stockage dans le navigateur (repris une dernière fois)
  var resumeIdx = idx, resume = null, fetched = false, curRel = T[idx].f;
  function tryResume(){
    if (!first || !fetched || !isFinite(a.duration) || a.duration <= 0) return;
    first = false;                                         // à partir d'ici seulement, on peut enregistrer sans écraser la position mémorisée
    if (idx === resumeIdx && resume && resume.t > 3 && resume.t < a.duration - 5 && a.currentTime < 3) {
      a.currentTime = resume.t;
      say('Reprise à ' + Progress.fmt(resume.t) + '.');
    }
  }
  Progress.get(T[idx].f).then(function(r){
    if (r && r.t > 0) resume = r;
    else {
      try { var old = JSON.parse(localStorage.getItem(legacyKey)); if (old && old.t > 3) resume = {t: old.t, d: 0}; } catch(e) {}
    }
    try { localStorage.removeItem(legacyKey); } catch(e) {}
    fetched = true;
    tryResume();
  });
  function savePos(final){
    if (first || !curRel || !isFinite(a.duration) || a.duration <= 0 || a.ended) return;
    if (a.currentTime > a.duration - 5) Progress.done(curRel);   // presque fini : on repartira du début
    else Progress.save(curRel, a.currentTime, a.duration, final);
  }
  function posState(){
    if ('mediaSession' in navigator && navigator.mediaSession.setPositionState && isFinite(a.duration)) {
      try { navigator.mediaSession.setPositionState({duration: a.duration, playbackRate: a.playbackRate, position: Math.min(a.currentTime, a.duration)}); } catch(e) {}
    }
  }
  a.addEventListener('loadedmetadata', function(){
    errRun = 0;
    showDur(idx, a.duration);
    tryResume();
    renderSeek(); posState();
  });
  a.addEventListener('durationchange', renderSeek);
  a.addEventListener('progress', renderSeek);
  a.addEventListener('timeupdate', function(){
    renderSeek();
    var now = Date.now();
    if (now - lastSave > 5000) { lastSave = now; savePos(false); }
  });
  a.addEventListener('waiting', function(){ if (!a.paused) { loading = true; renderPlay(); } });
  a.addEventListener('canplay', function(){ loading = false; renderPlay(); });
  a.addEventListener('playing', function(){ loading = false; renderPlay(); });
  a.addEventListener('play', function(){ renderPlay(); if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing'; });
  a.addEventListener('pause', function(){
    loading = false; renderPlay();
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
    savePos(false);
  });
  a.addEventListener('ended', function(){
    if (curRel) Progress.done(curRel);
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

