  /* ----- titre, pochette, écran de verrouillage ----- */
  function coverUrl(k){ return '/cover?f=' + T[k].q; }
  function session(title, info){
    if (!('mediaSession' in navigator) || !window.MediaMetadata) return;
    var art = [];
    if (info && info.cover) { try { art = [{src: new URL(coverUrl(idx), location.href).href, sizes: '640x640'}]; } catch(e) {} }
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: title, artist: (info && info.artist) || cfg.folder, album: (info && info.album) || cfg.folder, artwork: art
      });
    } catch(e) {}
  }
  function applyTitle(info){
    var title = (info && info.title) || T[idx].n;
    $('l-title').textContent = title;
    var sub = [info && info.artist, info && info.album].filter(Boolean).join(' · ');
    var el = $('l-artist'); el.textContent = sub; el.hidden = !sub;
    document.title = title + ' — Lecteur audio';
    session(title, info);
  }
  function setCover(info, k){
    cov.classList.remove('has-img'); img.hidden = true; img.removeAttribute('src');
    if (info && info.cover) img.src = coverUrl(k);
  }
  img.addEventListener('load', function(){ cov.classList.add('has-img'); img.hidden = false; });
  img.addEventListener('error', function(){ cov.classList.remove('has-img'); img.hidden = true; });

