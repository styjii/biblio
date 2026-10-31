  /* ----- reprise de la lecture, lecture automatique ----- */
  try { auto.checked = localStorage.getItem('vl:autonext') !== '0'; } catch(e) {}
  auto.addEventListener('change', function(){
    try { localStorage.setItem('vl:autonext', auto.checked ? '1' : '0'); } catch(e) {}
  });

  /* ----- reprise de la lecture : dernière position de CET appareil, mémorisée par le serveur (voir progress.js) ----- */
  var rel = items[idx].f, resume = null, fetched = false, resumed = false;
  function tryResume(){
    if (resumed || !fetched || !v.duration || isNaN(v.duration)) return;
    resumed = true;                                   // à partir d'ici seulement, on peut enregistrer sans écraser la position mémorisée
    if (resume && resume.t > 3 && resume.t < v.duration - 8 && v.currentTime < 3) {
      v.currentTime = resume.t;
      say('Reprise à ' + Progress.fmt(resume.t) + '.');
    }
  }
  Progress.get(rel).then(function (r) {
    if (r && r.t > 0) resume = r;
    else {                                            // ancienne position gardée par ce navigateur : reprise une dernière fois, puis oubliée
      try {
        var old = JSON.parse(localStorage.getItem(posKey));
        if (old && old.t > 3) resume = {t: old.t, d: old.d || 0};
      } catch (e) {}
    }
    try { localStorage.removeItem(posKey); } catch (e) {}
    fetched = true;
    tryResume();
  });
  v.addEventListener('loadedmetadata', tryResume);

  var last = 0;
  function save(final){
    if (!resumed || !v.duration || v.ended) return;
    if (v.currentTime > v.duration - 8) Progress.done(rel);      // presque fini : on repartira du début
    else Progress.save(rel, v.currentTime, v.duration, final);
  }
  v.addEventListener('timeupdate', function(){
    var now = Date.now();
    if (now - last > 5000) { last = now; save(false); }
  });
  v.addEventListener('pause', function(){ save(false); });
  v.addEventListener('seeked', function(){ if (v.paused) save(false); });
  document.addEventListener('visibilitychange', function(){ if (document.visibilityState === 'hidden') save(true); });
  window.addEventListener('pagehide', function(){ save(true); });

  v.addEventListener('ended', function(){
    Progress.done(rel);
    if (repeat === 'one') { v.currentTime = 0; play(); return; }     // (repli : la boucle native s'en charge déjà)
    if (!auto.checked) return;
    if (window.Transfers && window.Transfers.busy()) { say('Lecture automatique suspendue : un envoi est en cours dans cet onglet.'); return; }
    next(true);
  });

  var cur = document.querySelector('.row.cur');
  if (cur && cur.scrollIntoView && innerWidth >= 1000) {
    cur.scrollIntoView({block: 'nearest'});
  }

