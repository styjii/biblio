  /* ----- boutons ----- */
  vslider.addEventListener('input', function(e){ setVol(e.target.value / 100); });
  vslider.addEventListener('change', function(e){ e.target.blur(); });
  $('w-prev').addEventListener('click', prev);
  $('w-next').addEventListener('click', function(){ next(false); });
  $('w-back').addEventListener('click', function(){ seekBy(-10); });
  $('w-fwd').addEventListener('click', function(){ seekBy(10); });
  $('w-shuffle').addEventListener('click', function(){ setShuffle(!shuffle); });
  $('w-repeat').addEventListener('click', cycleRepeat);
  $('w-mute').addEventListener('click', toggleMute);
  $('w-rate').addEventListener('click', function(){ setRate(rates[(rates.indexOf(rate) + 1) % rates.length]); });

  /* ----- clavier ----- */
  document.addEventListener('keydown', function(e){
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target.tagName || '').toLowerCase(), type = (e.target.type || '').toLowerCase();
    if (tag === 'textarea' || (tag === 'input' && type !== 'range')) return;
    var k = e.key, lk = k.toLowerCase();
    if (tag === 'button' && (k === ' ' || k === 'Enter')) return;
    var onPlayer = e.target === v;
    // le curseur de volume garde ses flèches natives
    if (e.target.id === 'w-vol' && (k === 'ArrowLeft' || k === 'ArrowRight' || k === 'ArrowUp' || k === 'ArrowDown')) return;
    var handled = true;
    if (lk === 'k' || (k === ' ' && !onPlayer)) { v.paused ? play() : v.pause(); }
    else if (lk === 'j') seekBy(-10);
    else if (lk === 'l') seekBy(10);
    else if (lk === 'n') next(false);
    else if (lk === 'p') prev();
    else if (lk === 's') setShuffle(!shuffle);
    else if (lk === 'r') cycleRepeat();
    else if (lk === 'm') toggleMute();
    else if (k === 'ArrowLeft' && !onPlayer) seekBy(-5);
    else if (k === 'ArrowRight' && !onPlayer) seekBy(5);
    else if (k === 'ArrowUp' && !onPlayer) setVol((v.muted ? 0 : v.volume) + 0.05);
    else if (k === 'ArrowDown' && !onPlayer) setVol((v.muted ? 0 : v.volume) - 0.05);
    else if (k === '<' || k === ',') stepRate(-1);
    else if (k === '>' || k === '.') stepRate(1);
    else if (lk === 'f') {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (v.requestFullscreen) v.requestFullscreen();
    }
    else { handled = false; }
    if (handled) e.preventDefault();
  });

  // touches multimédia du téléphone / du clavier et écran de verrouillage
  if ('mediaSession' in navigator) {
    var H = {previoustrack: prev, nexttrack: function(){ next(false); },
             seekbackward: function(d){ seekBy(-((d && d.seekOffset) || 10)); },
             seekforward: function(d){ seekBy((d && d.seekOffset) || 10); }};
    Object.keys(H).forEach(function(name){ try { navigator.mediaSession.setActionHandler(name, H[name]); } catch(e) {} });
  }

  restoreOrder();
  renderModes(); renderVol(); renderRate();
})();
