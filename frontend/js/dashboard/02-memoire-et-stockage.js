  /* ---------- mémoire et stockage ---------- */
  function meterClass(p){ return p >= 90 ? 'crit' : (p >= 70 ? 'warn' : ''); }
  function memory(m){
    $('mem').hidden = !m;
    $('mem-na').hidden = !!m;
    if (!m) return;
    $('m-used').textContent = m.used_h;
    $('m-free').textContent = m.free_h;
    $('m-total').textContent = m.total_h;
    var bar = $('meter-bar');
    bar.style.width = m.percent + '%';
    bar.className = meterClass(m.percent);
    $('m-pct').textContent = pct(m.percent) + ' % utilisée · libre = mémoire disponible (cache récupérable inclus)';
  }
  function disks(list){
    var box = $('disks');
    box.textContent = '';
    $('disks-sec').hidden = !list.length;
    list.forEach(function(k){
      var c = el('div', 'stat');
      var head = el('div', 'dev-top');
      head.appendChild(el('span', 'label', k.label));
      head.appendChild(el('span', 'tag', k.path));
      if (k.system) {
        var w = el('span', 'tag bad', 'Même volume que le système');
        w.title = 'Ce chemin ne semble pas être un disque monté séparément';
        head.appendChild(w);
      }
      c.appendChild(head);
      if (k.error) {
        c.appendChild(el('div', 'sub', k.error));
      } else {
        c.appendChild(el('div', 'value', k.free_h + ' libres'));
        var m = el('div', 'meter');
        var s = el('span', meterClass(k.percent));
        s.style.width = k.percent + '%';
        m.appendChild(s);
        c.appendChild(m);
        c.appendChild(el('div', 'sub', k.used_h + ' utilisés sur ' + k.total_h + ' (' + pct(k.percent) + ' %)'));
      }
      box.appendChild(c);
    });
  }

