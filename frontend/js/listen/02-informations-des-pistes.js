  /* ----- informations des pistes (durée, tags) : chargées à la demande ----- */
  function getInfo(i){
    if (!infos[i]) {
      infos[i] = fetch('/meta?f=' + T[i].q)
        .then(function(r){ return r.ok ? r.json() : {}; })
        .catch(function(){ return {}; });
    }
    return infos[i];
  }
  function showDur(i, d){
    var el = rows[i] && rows[i].querySelector('.td');
    if (el && d) el.textContent = fmt(d);
  }

