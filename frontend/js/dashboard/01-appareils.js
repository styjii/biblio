  /* ---------- appareils ---------- */
  function act(ip, block){
    if (block && !confirm('Bloquer ' + ip + ' ? Cet appareil n\'aura plus accès à la bibliothèque.')) return;
    fetch('/dashboard/' + (block ? 'block' : 'unblock') + '?ip=' + encodeURIComponent(ip), {
      method: 'POST', headers: H, credentials: 'same-origin'
    })
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, j: j}; }); })
      .then(function(x){
        if (x.status === 401) { location.reload(); return; }
        if (!x.j.ok) alert(x.j.error || 'Erreur');
        else if (x.j.warning) alert(x.j.warning);
        busy = false; load();
      })
      .catch(function(){ alert('Connexion impossible.'); });
  }
  function row(v){
    var r = el('div', 'dev' + (v.blocked ? ' blocked' : ''));
    var ic = el('div', 'ico ' + (v.blocked ? 'danger' : 'code'));
    ic.innerHTML = v.blocked ? I.ban : I.monitor;
    var t = el('div', 'text');
    var top = el('div', 'dev-top');
    top.appendChild(el('span', 'ip', v.ip));
    if (v.me) top.appendChild(el('span', 'tag me', 'Cet appareil'));
    else if (v.local) top.appendChild(el('span', 'tag me', 'Serveur'));
    if (v.blocked) top.appendChild(el('span', 'tag bad', 'Bloqué'));
    else if (v.ago !== null && !v.auth) {
      var w = el('span', 'tag bad', 'Sans jeton');
      w.title = "N'a jamais présenté le jeton d'accès";
      top.appendChild(w);
    }
    var bits = [];
    if (v.ua) bits.push(v.ua);
    if (v.mac) bits.push('MAC ' + v.mac);
    bits.push(ago(v.ago));
    if (v.hits) bits.push(v.hits + (v.hits > 1 ? ' requêtes' : ' requête'));
    t.appendChild(top);
    t.appendChild(el('div', 'sub', bits.join(' · ')));
    r.appendChild(ic);
    r.appendChild(t);
    var acts = el('div', 'dev-actions');
    var hb = el('button', 'pill', 'Historique');
    hb.type = 'button';
    hb.addEventListener('click', function(){ openHistory(v.ip); });
    acts.appendChild(hb);
    if (!v.me && !v.local) {
      var b = el('button', 'pill' + (v.blocked ? '' : ' danger'), v.blocked ? 'Débloquer' : 'Bloquer');
      b.type = 'button';
      b.addEventListener('click', function(){ act(v.ip, !v.blocked); });
      acts.appendChild(b);
    }
    r.appendChild(acts);
    return r;
  }

