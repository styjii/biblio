(function(){
  var cfg = window.WCFG;
  var v = document.getElementById('player');
  var auto = document.getElementById('autonext');
  var posKey = 'vl:pos:' + cfg.key;

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
    if (auto.checked && cfg.next) location.href = cfg.next;
  });

  var cur = document.querySelector('.row.cur');
  if (cur && cur.scrollIntoView && innerWidth >= 1000) {
    cur.scrollIntoView({block: 'nearest'});
  }

  document.addEventListener('keydown', function(e){
    var tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || e.ctrlKey || e.metaKey || e.altKey) return;
    var onPlayer = e.target === v;
    var k = e.key.toLowerCase();
    var handled = true;
    if (k === 'k' || (k === ' ' && !onPlayer)) { v.paused ? v.play() : v.pause(); }
    else if (k === 'j') { v.currentTime = Math.max(0, v.currentTime - 10); }
    else if (k === 'l') { v.currentTime = Math.min(v.duration || 1e9, v.currentTime + 10); }
    else if (k === 'arrowleft' && !onPlayer) { v.currentTime = Math.max(0, v.currentTime - 5); }
    else if (k === 'arrowright' && !onPlayer) { v.currentTime = Math.min(v.duration || 1e9, v.currentTime + 5); }
    else if (k === 'm') { v.muted = !v.muted; }
    else if (k === 'f') {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (v.requestFullscreen) v.requestFullscreen();
    }
    else { handled = false; }
    if (handled) e.preventDefault();
  });
})();
