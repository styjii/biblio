  /* ----- affichage ----- */
  function renderPlay(){
    var playing = !a.paused, b = $('b-play');
    setIcon(b, loading ? 'loader' : (playing ? 'pause' : 'play'));
    b.classList.toggle('loading', loading);
    b.setAttribute('aria-busy', loading ? 'true' : 'false');
    b.setAttribute('aria-label', playing ? 'Pause' : 'Lecture');
    cov.classList.toggle('playing', playing && !loading);
    renderPlayRow();
  }
  function renderModes(){
    $('b-shuffle').classList.toggle('on', shuffle);
    $('b-shuffle').setAttribute('aria-pressed', shuffle ? 'true' : 'false');
    var rb = $('b-repeat');
    setIcon(rb, repeat === 'one' ? 'repeat1' : 'repeat');
    rb.classList.toggle('on', repeat !== 'off');
    rb.setAttribute('aria-pressed', repeat !== 'off' ? 'true' : 'false');
    rb.setAttribute('aria-label', 'Répétition : ' + (repeat === 'off' ? 'désactivée' : (repeat === 'all' ? 'toutes les pistes' : 'cette piste')));
    rb.title = 'Répétition (R) : ' + (repeat === 'off' ? 'aucune' : (repeat === 'all' ? 'tout' : 'une piste'));
  }
  function renderVol(){
    var muted = a.muted || a.volume === 0;
    setIcon($('b-mute'), muted ? 'mute' : 'volume');
    $('b-mute').setAttribute('aria-pressed', muted ? 'true' : 'false');
    var v = Math.round((a.muted ? 0 : a.volume) * 100);
    vslider.value = v;
    vslider.style.setProperty('--p', v + '%');
    vslider.setAttribute('aria-valuetext', v + ' %');
  }
  function renderRate(){ $('b-rate').textContent = String(rate).replace('.', ',') + '×'; }
  function renderSeek(){
    var d = a.duration, ok = isFinite(d) && d > 0;
    var p = ok ? a.currentTime / d * 100 : 0;
    if (!seeking) seek.value = Math.round(p * 10);
    var shown = seeking ? seek.value / 10 : p, buf = 0;
    if (ok) {
      for (var i = 0; i < a.buffered.length; i++) {
        if (a.buffered.start(i) <= a.currentTime + 0.25 && a.buffered.end(i) >= a.currentTime) buf = Math.max(buf, a.buffered.end(i));
      }
      buf = buf / d * 100;
    }
    seek.style.setProperty('--p', shown + '%');
    seek.style.setProperty('--b', Math.max(shown, buf) + '%');
    $('l-cur').textContent = fmt(seeking && ok ? seek.value / 1000 * d : a.currentTime);
    $('l-dur').textContent = fmt(ok ? d : 0);
    seek.setAttribute('aria-valuetext', fmt(a.currentTime) + ' sur ' + fmt(ok ? d : 0));
  }
  function ui(){ renderPlay(); renderModes(); renderVol(); renderRate(); renderSeek(); }

