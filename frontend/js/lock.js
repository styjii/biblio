(function(){
  var ICO = window.LKICO || {}, H = {'X-Requested-With': 'biblio'};
  var btn = document.getElementById('lock-toggle');
  var st = {enabled: false, unlocked: false};
  function paint(){
    if (!btn) return;
    btn.hidden = !st.enabled;
    btn.innerHTML = st.unlocked ? ICO.unlock : ICO.lock;
    btn.classList.toggle('unlocked', st.unlocked);
    var t = st.unlocked ? 'Accès déverrouillé : cliquer pour verrouiller' : 'Accès verrouillé : cliquer pour déverrouiller';
    btn.title = t; btn.setAttribute('aria-label', t);
  }
  function post(url, body){
    return fetch(url, {method: 'POST', credentials: 'same-origin', headers: H, body: body}).then(function(r){ return r.json(); });
  }
  function dialog(){
    if (document.querySelector('.lkveil')) return;
    var veil = document.createElement('div');
    veil.className = 'lkveil';
    veil.innerHTML = '<form class="lkbox" autocomplete="off"><h2>Déverrouiller l’accès</h2>' +
      '<p>Le mot de passe n’est demandé qu’ici. Ensuite, la modification, le renommage, la suppression, l’envoi de fichiers et le tableau de bord ne le redemandent plus, jusqu’au prochain verrouillage.</p>' +
      '<input type="password" placeholder="Mot de passe" autocomplete="current-password" required>' +
      '<p class="lkerr" role="alert"></p><div class="row"><button type="button" class="pill" data-x>Annuler</button>' +
      '<button type="submit" class="pill primary">Déverrouiller</button></div></form>';
    document.body.appendChild(veil);
    document.documentElement.classList.add('noscroll-lk');
    var f = veil.firstChild, pw = f.querySelector('input'), err = f.querySelector('.lkerr'), go = f.querySelector('[type=submit]');
    function close(){ veil.remove(); document.documentElement.classList.remove('noscroll-lk'); document.removeEventListener('keydown', onKey); }
    function onKey(e){ if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onKey);
    veil.addEventListener('click', function(e){ if (e.target === veil) close(); });
    f.querySelector('[data-x]').addEventListener('click', close);
    f.addEventListener('submit', function(e){
      e.preventDefault(); go.disabled = true; err.textContent = '';
      post('/unlock', pw.value).then(function(j){
        if (j.ok) { location.reload(); return; }
        go.disabled = false; err.textContent = j.error || 'Erreur'; pw.value = ''; pw.focus();
      }).catch(function(){ go.disabled = false; err.textContent = 'Connexion impossible.'; });
    });
    setTimeout(function(){ pw.focus(); }, 30);
  }
  if (btn) btn.addEventListener('click', function(){
    if (!st.unlocked) { dialog(); return; }
    post('/lock').then(function(){ location.reload(); });
  });
  document.addEventListener('click', function(e){
    var t = e.target.closest ? e.target.closest('[data-unlock]') : null;
    if (t) { e.preventDefault(); dialog(); }
  });
  var first = null;
  function refresh(){
    fetch('/lock-state', {credentials: 'same-origin'}).then(function(r){ return r.json(); }).then(function(x){
      st = x; paint();
      if (window.FLCFG) window.FLCFG.unlocked = !!x.files;
      if (first === null) first = x;
      else if (window.LKRELOAD && !!x[window.LKRELOAD] !== !!first[window.LKRELOAD]) location.reload();
    }).catch(function(){});
  }
  refresh();
  document.addEventListener('visibilitychange', function(){ if (!document.hidden) refresh(); });
  window.addEventListener('focus', refresh);
})();
