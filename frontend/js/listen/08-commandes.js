  /* ----- commandes ----- */
  seek.addEventListener('input', function(){ seeking = true; renderSeek(); });
  seek.addEventListener('change', function(){
    if (isFinite(a.duration)) a.currentTime = seek.value / 1000 * a.duration;
    seeking = false; renderSeek(); seek.blur();
  });
  seek.addEventListener('pointercancel', function(){ seeking = false; renderSeek(); });
  vslider.addEventListener('input', function(e){ setVol(e.target.value / 100); });
  vslider.addEventListener('change', function(e){ e.target.blur(); });
  $('b-play').addEventListener('click', toggle);
  $('b-next').addEventListener('click', function(){ next(false); });
  $('b-prev').addEventListener('click', prev);
  $('b-back').addEventListener('click', function(){ seekBy(-10); });
  $('b-fwd').addEventListener('click', function(){ seekBy(10); });
  $('b-shuffle').addEventListener('click', function(){ setShuffle(!shuffle); });
  $('b-repeat').addEventListener('click', cycleRepeat);
  $('b-mute').addEventListener('click', toggleMute);
  $('b-rate').addEventListener('click', function(){ setRate(rates[(rates.indexOf(rate) + 1) % rates.length]); });
  function applyFilter(){
    var q = $('l-filter').value.trim().toLowerCase();
    rows.forEach(function(r, i){ r.hidden = !!q && T[i].n.toLowerCase().indexOf(q) < 0; });
  }
  $('l-filter').addEventListener('input', applyFilter);

  document.addEventListener('keydown', function(e){
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target.tagName || '').toLowerCase(), type = (e.target.type || '').toLowerCase();
    var k = e.key, lk = k.toLowerCase();
    if (tag === 'textarea' || (tag === 'input' && type !== 'range' && type !== 'checkbox')) {
      if (k === 'Escape') { if (e.target.id === 'l-filter') { e.target.value = ''; applyFilter(); } e.target.blur(); }
      return;
    }
    if (tag === 'button' && (k === ' ' || k === 'Enter')) return;
    // le curseur de volume garde ses flèches natives ; sur le curseur de position, elles avancent de 5 s
    if (e.target.id === 'l-vol' && (k === 'ArrowLeft' || k === 'ArrowRight' || k === 'ArrowUp' || k === 'ArrowDown')) return;
    var handled = true;
    if (k === ' ' || lk === 'k') toggle();
    else if (lk === 'n') next(false);
    else if (lk === 'p') prev();
    else if (lk === 's') setShuffle(!shuffle);
    else if (lk === 'r') cycleRepeat();
    else if (lk === 'm') toggleMute();
    else if (k === 'ArrowLeft') seekBy(-5);
    else if (k === 'ArrowRight') seekBy(5);
    else if (lk === 'j') seekBy(-10);
    else if (lk === 'l') seekBy(10);
    else if (k === 'ArrowUp') setVol((a.muted ? 0 : a.volume) + 0.05);
    else if (k === 'ArrowDown') setVol((a.muted ? 0 : a.volume) - 0.05);
    else if (k === '<' || k === ',') stepRate(-1);
    else if (k === '>' || k === '.') stepRate(1);
    else if (/^[0-9]$/.test(k)) { if (isFinite(a.duration)) a.currentTime = a.duration * Number(k) / 10; }
    else if (k === '/') { $('l-filter').focus(); }
    else handled = false;
    if (handled) e.preventDefault();
  });

  if ('mediaSession' in navigator) {
    var H = {
      play: play, pause: function(){ a.pause(); },
      previoustrack: prev, nexttrack: function(){ next(false); },
      seekbackward: function(d){ seekBy(-((d && d.seekOffset) || 10)); },
      seekforward: function(d){ seekBy((d && d.seekOffset) || 10); },
      seekto: function(d){ if (d && isFinite(d.seekTime)) a.currentTime = d.seekTime; }
    };
    Object.keys(H).forEach(function(name){ try { navigator.mediaSession.setActionHandler(name, H[name]); } catch(e) {} });
  }
  window.addEventListener('pagehide', function(){
    try { if (a.duration && !a.ended && a.currentTime > 0) localStorage.setItem(posKey(), JSON.stringify({t: a.currentTime})); } catch(e) {}
  });

  buildList();
  rebuild();
  ui();
  start(idx, true);
})();
