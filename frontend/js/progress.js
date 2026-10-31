/* Dernière position de lecture : mémorisée par le SERVEUR pour chaque appareil (adresse IP), pas par le navigateur.
   La reprise fonctionne donc aussi après avoir vidé le navigateur ou changé de navigateur sur le même appareil. */
window.Progress = (function () {
  var last = {};                                    // fichier -> dernière position envoyée (évite les envois inutiles)
  function url(rel, extra) { return '/progress?f=' + encodeURIComponent(rel) + (extra || ''); }
  function post(rel, extra, keepalive) {
    try {
      fetch(url(rel, extra), {method: 'POST', headers: {'X-Requested-With': 'biblio'}, credentials: 'same-origin',
                              keepalive: !!keepalive}).catch(function () {});
    } catch (e) {}
  }
  return {
    // -> Promise<{t, d} | null> : position mémorisée pour cet appareil, null si le serveur ne répond pas
    get: function (rel) {
      return fetch(url(rel), {credentials: 'same-origin'})
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) { return j && j.ok ? {t: j.t || 0, d: j.d || 0} : null; })
        .catch(function () { return null; });
    },
    // `keepalive` : l'envoi aboutit même si la page se ferme. Une position proche du début efface la mémoire (côté serveur).
    save: function (rel, t, d, keepalive) {
      if (!isFinite(t) || t < 0) return;
      if (last[rel] !== undefined && Math.abs(last[rel] - t) < 1) return;
      last[rel] = t;
      post(rel, '&t=' + t.toFixed(1) + '&d=' + (isFinite(d) ? d : 0).toFixed(1), keepalive);
    },
    done: function (rel) { last[rel] = 0; post(rel, '&done=1', true); },      // lu jusqu'au bout : on oublie la position
    fmt: function (s) {
      s = Math.max(0, Math.floor(s));
      var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), r = s % 60;
      return (h ? h + ':' + (m < 10 ? '0' : '') + m : m) + ':' + (r < 10 ? '0' : '') + r;
    }
  };
})();
