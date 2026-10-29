  /* ----- volume et vitesse ----- */
  function setVol(x){
    x = Math.max(0, Math.min(1, x));
    v.volume = x; if (x > 0) v.muted = false;
  }
  function toggleMute(){ v.muted = !v.muted; }
  function renderVol(){
    var muted = v.muted || v.volume === 0;
    setIcon($('w-mute'), muted ? 'mute' : 'volume');
    $('w-mute').setAttribute('aria-pressed', muted ? 'true' : 'false');
    var p = Math.round((v.muted ? 0 : v.volume) * 100);
    vslider.value = p;
    vslider.style.setProperty('--p', p + '%');
    vslider.setAttribute('aria-valuetext', p + ' %');
  }
  // le volume du lecteur natif (clavier, souris, plein écran) est lui aussi mémorisé
  v.addEventListener('volumechange', function(){
    renderVol();
    store('vol', v.volume); store('muted', v.muted ? '1' : '0');
  });
  function renderRate(){ $('w-rate').textContent = String(rate).replace('.', ',') + '×'; }
  function setRate(r){
    rate = r; v.defaultPlaybackRate = r; v.playbackRate = r; store('rate', r); renderRate();
    say('Vitesse : ' + String(r).replace('.', ',') + '×');
  }
  function stepRate(d){
    var i = rates.indexOf(rate) + d;
    setRate(rates[Math.max(0, Math.min(rates.length - 1, i))]);
  }
  v.addEventListener('ratechange', function(){
    // vitesse changée depuis le menu du lecteur natif : on la retient aussi
    if (rates.indexOf(v.playbackRate) >= 0 && v.playbackRate !== rate) { rate = v.playbackRate; store('rate', rate); renderRate(); }
  });

