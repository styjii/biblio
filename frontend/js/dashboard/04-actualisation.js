  /* ---------- actualisation ---------- */
  function render(d){
    $('host').textContent = d.host;
    memory(d.memory);
    disks(d.disks || []);
    $('n-active').textContent = d.active;
    $('dev-sub').textContent = d.active + (d.active > 1 ? ' appareils connectés' : ' appareil connecté')
      + ' (activité depuis moins de ' + Math.round(d.window / 60) + ' min) · ' + d.blocked
      + (d.blocked > 1 ? ' bloqués' : ' bloqué');
    var list = $('devices');
    list.textContent = '';
    d.devices.forEach(function(v){ list.appendChild(row(v)); });
    if (!d.devices.length) list.appendChild(el('div', 'empty', 'Aucun appareil pour le moment.'));
    syncDevices(d.devices);
  }
  var busy = false;
  function load(){
    if (busy) return;
    busy = true;
    fetch('/dashboard/data', {credentials: 'same-origin', cache: 'no-store'})
      .then(function(r){
        if (r.status === 401) { location.reload(); return null; }
        return r.json();
      })
      .then(function(d){
        if (d && d.ok) {
          render(d);
          $('upd').textContent = 'mis à jour à ' + new Date().toLocaleTimeString('fr-FR');
        }
      })
      .catch(function(){ $('upd').textContent = 'connexion perdue, nouvel essai…'; })
      .then(function(){ busy = false; });
  }
  $('lock').addEventListener('click', function(){
    fetch('/lock', {method: 'POST', headers: H, credentials: 'same-origin'})
      .then(function(){ location.reload(); });
  });
  hsel.addEventListener('change', loadHistory);
  hrange.addEventListener('change', loadHistory);
  hmetric.addEventListener('change', function(){ if (hdata) drawHistory(); });
  document.addEventListener('visibilitychange', function(){ if (!document.hidden) { load(); loadHistory(); } });
  setInterval(function(){ if (!document.hidden) load(); }, 3000);
  setInterval(function(){ if (!document.hidden) loadHistory(); }, 15000);
  load();
  loadHistory();
})();
