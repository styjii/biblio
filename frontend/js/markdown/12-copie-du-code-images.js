/* ---------- Copie du code, images ---------- */
function copyText(t, cb){
  function legacy(){
    var ta = document.createElement('textarea'), ok = false;
    ta.value = t; ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.appendChild(ta); ta.select();
    try { ok = document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    cb(ok);
  }
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(function(){ cb(true); }, legacy);
  else legacy();
}
function lightbox(img){
  var box = document.createElement('div');
  box.className = 'mdbox';
  var big = document.createElement('img');
  big.src = img.src; big.alt = img.alt;
  box.appendChild(big);
  function close(){ box.remove(); document.removeEventListener('keydown', onKey); }
  function onKey(e){ if (e.key === 'Escape') close(); }
  box.addEventListener('click', close);
  document.addEventListener('keydown', onKey);
  document.body.appendChild(box);
}
art.addEventListener('click', function(e){
  var t = e.target, b = t.closest ? t.closest('button.copy') : null;
  if (b) {
    copyText(b.closest('figure').querySelector('code').textContent, function(ok){
      b.textContent = ok ? 'Copié' : 'Échec';
      setTimeout(function(){ b.textContent = 'Copier'; }, 1600);
    });
    return;
  }
  if (t.tagName === 'IMG' && !(t.closest && t.closest('a'))) lightbox(t);
});

