  /* ----- reprise de la lecture, lecture automatique ----- */
  try { auto.checked = localStorage.getItem('vl:autonext') !== '0'; } catch(e) {}
  auto.addEventListener('change', function(){
    try { localStorage.setItem('vl:autonext', auto.checked ? '1' : '0'); } catch(e) {}
  });

  var saved = null;
  try { saved = JSON.parse(localStorage.getItem(posKey)); } catch(e) {}
  v.addEventListener('loadedmetadata', function(){
    if (saved && saved.t > 3 && saved.t < v.duration - 8) v.currentTime = saved.t;
  });

  var last = 0;
  function save(){
    if (!v.duration || v.ended) return;
    try { localStorage.setItem(posKey, JSON.stringify({t: v.currentTime, d: v.duration})); }
    catch(e) {}
  }
  v.addEventListener('timeupdate', function(){
    var now = Date.now();
    if (now - last > 2500) { last = now; save(); }
  });
  v.addEventListener('pause', save);
  window.addEventListener('pagehide', save);

  v.addEventListener('ended', function(){
    try { localStorage.removeItem(posKey); } catch(e) {}
    if (repeat === 'one') { v.currentTime = 0; play(); return; }     // (repli : la boucle native s'en charge déjà)
    if (auto.checked) next(true);
  });

  var cur = document.querySelector('.row.cur');
  if (cur && cur.scrollIntoView && innerWidth >= 1000) {
    cur.scrollIntoView({block: 'nearest'});
  }

