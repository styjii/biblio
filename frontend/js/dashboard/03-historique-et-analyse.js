  /* ---------- historique et analyse ---------- */
  var hsel = $('h-dev'), hrange = $('h-range'), hmetric = $('h-metric');
  var hdata = null, hseq = 0, devKey = '';
  function catOf(id){
    for (var i = 0; i < I.cats.length; i++) if (I.cats[i].id === id) return I.cats[i];
    return {id: id, label: id, color: 'var(--muted)'};
  }
  function syncDevices(list){
    var key = list.map(function(v){ return v.ip; }).join(',');
    if (key === devKey) return;
    devKey = key;
    var cur = hsel.value;
    hsel.textContent = '';
    var o = el('option', null, 'Tous les appareils');
    o.value = 'all';
    hsel.appendChild(o);
    list.forEach(function(v){
      var op = el('option', null, v.ip + (v.ua ? ' · ' + v.ua : '') + (v.me ? ' (cet appareil)' : ''));
      op.value = v.ip;
      hsel.appendChild(op);
    });
    hsel.value = cur;
    if (!hsel.value) hsel.value = 'all';
  }
  function openHistory(ip){
    hsel.value = ip;
    if (!hsel.value) hsel.value = 'all';
    loadHistory();
    $('hist').scrollIntoView({behavior: 'smooth'});
  }
  function loadHistory(){
    var my = ++hseq;
    fetch('/dashboard/history?ip=' + encodeURIComponent(hsel.value || 'all') + '&range=' + hrange.value,
          {credentials: 'same-origin', cache: 'no-store'})
      .then(function(r){
        if (r.status === 401) { location.reload(); return null; }
        return r.json();
      })
      .then(function(d){ if (d && d.ok && my === hseq) { hdata = d; drawHistory(); } })
      .catch(function(){});
  }
  function timeLabel(t, long){
    var d = new Date(t * 1000);
    if (long) return d.toLocaleString('fr-FR', {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
    if (hdata && hdata.range === '24h') return d.toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'});
    return d.toLocaleDateString('fr-FR', {day: 'numeric', month: 'short'});
  }
  function curve(cats, d, metric){
    var n = d.n, W = 640, Hh = 220, L = 50, R = 8, T = 10, B = 24, pw = W - L - R, ph = Hh - T - B, i;
    var tot = [];
    for (i = 0; i < n; i++) tot.push(0);
    cats.forEach(function(c){ d.series[c.id][metric].forEach(function(v, k){ tot[k] += v; }); });
    var max = niceFor(Math.max.apply(null, tot), metric);
    var x = function(k){ return L + (n > 1 ? k * pw / (n - 1) : pw / 2); };
    var y = function(v){ return T + ph - v / max * ph; };
    var out = '<svg viewBox="0 0 ' + W + ' ' + Hh + '" class="chart" role="img" aria-label="Courbe d activité">';
    for (var g = 0; g <= 4; g++) {
      var gy = y(max * g / 4);
      out += '<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + f1(gy) + '" y2="' + f1(gy) + '"/>'
           + '<text class="axis" x="' + (L - 6) + '" y="' + f1(gy + 3.5) + '" text-anchor="end">' + fmtMetric(max * g / 4, metric) + '</text>';
    }
    var base = [];
    for (i = 0; i < n; i++) base.push(0);
    cats.forEach(function(c){
      var vals = d.series[c.id][metric], up = [], p, k;
      for (k = 0; k < n; k++) up.push(base[k] + vals[k]);
      p = 'M' + f1(x(0)) + ' ' + f1(y(base[0]));
      for (k = 0; k < n; k++) p += ' L' + f1(x(k)) + ' ' + f1(y(up[k]));
      for (k = n - 1; k >= 0; k--) p += ' L' + f1(x(k)) + ' ' + f1(y(base[k]));
      out += '<path class="area" d="' + p + 'Z" style="fill:' + c.color + '"/>';
      base = up;
    });
    [0, 0.25, 0.5, 0.75, 1].forEach(function(f, k){
      var idx = Math.round(f * (n - 1));
      out += '<text class="axis" x="' + f1(x(idx)) + '" y="' + (Hh - 6) + '" text-anchor="'
           + (k === 0 ? 'start' : (k === 4 ? 'end' : 'middle')) + '">' + timeLabel(d.start + idx * d.step, false) + '</text>';
    });
    out += '<line class="cursor" x1="0" x2="0" y1="' + T + '" y2="' + (T + ph) + '"/>'
         + '<rect class="hit" x="' + L + '" y="' + T + '" width="' + pw + '" height="' + ph + '"/></svg>';
    var box = $('h-curve');
    box.innerHTML = out;
    var svg = box.firstChild, cur = svg.querySelector('.cursor'), hit = svg.querySelector('.hit');
    function at(ev){
      var r = svg.getBoundingClientRect();
      var px = (ev.clientX - r.left) / r.width * W;
      var k = Math.max(0, Math.min(n - 1, Math.round((px - L) / pw * (n - 1))));
      cur.setAttribute('x1', f1(x(k)));
      cur.setAttribute('x2', f1(x(k)));
      cur.style.visibility = 'visible';
      var parts = [];
      cats.forEach(function(c){
        var v = d.series[c.id][metric][k];
        if (v) parts.push(c.label + ' ' + fmtMetric(v, metric));
      });
      $('h-read').textContent = timeLabel(d.start + k * d.step, true) + ' : ' + (parts.length ? parts.join(' · ') : 'aucune activité');
    }
    hit.addEventListener('pointermove', at);
    hit.addEventListener('pointerdown', at);
    $('h-read').textContent = 'Touche ou survole la courbe pour le détail.';
    var lg = $('h-legend');
    lg.textContent = '';
    cats.forEach(function(c){
      var s = el('span', null, c.label + ' ');
      var sw = el('span', 'sw');
      sw.style.background = c.color;
      s.insertBefore(sw, s.firstChild);
      s.appendChild(el('b', null, fmtMetric(d.totals[c.id][metric], metric)));
      lg.appendChild(s);
    });
  }
  function donut(cats, d, metric){
    var tot = 0;
    cats.forEach(function(c){ tot += d.totals[c.id][metric]; });
    var out = '<svg viewBox="0 0 42 42" class="donut" role="img" aria-label="Répartition par catégorie">'
            + '<circle cx="21" cy="21" r="15.9155" class="ring"/>';
    var off = 25;
    var share = $('h-share');
    share.textContent = '';
    cats.forEach(function(c){
      var v = d.totals[c.id][metric];
      if (!v || !tot) return;
      var p = v / tot * 100;
      out += '<circle cx="21" cy="21" r="15.9155" class="seg" style="stroke:' + c.color + '" stroke-dasharray="'
           + p.toFixed(2) + ' ' + (100 - p).toFixed(2) + '" stroke-dashoffset="' + off.toFixed(2) + '"/>';
      off -= p;
      var line = el('div');
      var left = el('span', null, c.label);
      var sw = el('span', 'sw');
      sw.style.background = c.color;
      left.insertBefore(sw, left.firstChild);
      line.appendChild(left);
      line.appendChild(el('b', null, Math.round(p) + ' %'));
      share.appendChild(line);
    });
    out += '<text x="21" y="22.8" text-anchor="middle" class="dtot">' + fmtMetric(tot, metric) + '</text></svg>';
    $('h-donut').innerHTML = out;
  }
  function topFiles(d){
    var box = $('h-top');
    box.textContent = '';
    if (!d.top.length) { box.appendChild(el('div', 'sub', 'Aucun fichier consulté.')); return; }
    var max = d.top[0].n;
    d.top.forEach(function(t){
      var c = catOf(t.cat);
      var r = el('div', 'top-row');
      r.appendChild(el('div', 'name', t.file));
      var bits = [c.label, t.n + ' fois'];
      if (t.seconds >= 5) bits.push(fmtDur(t.seconds));
      if (t.bytes) bits.push(fmtBytes(t.bytes));
      r.appendChild(el('div', 'sub', bits.join(' · ')));
      var bar = el('div', 'bar');
      var s = el('span');
      s.style.width = Math.max(4, t.n / max * 100) + '%';
      s.style.background = c.color;
      bar.appendChild(s);
      r.appendChild(bar);
      box.appendChild(r);
    });
  }
  function recent(d){
    var box = $('h-list');
    box.textContent = '';
    d.recent.forEach(function(e){
      var c = catOf(e.cat);
      var r = el('div', 'h-item');
      r.appendChild(el('span', 'when', timeLabel(e.t, true)));
      var what = el('span', 'what');
      var sw = el('span', 'sw');
      sw.style.background = c.color;
      what.appendChild(sw);
      what.appendChild(document.createTextNode(c.label + ' · ' + (e.file || '/')));
      r.appendChild(what);
      var bits = [];
      if (e.end - e.t >= 5) bits.push(fmtDur(e.end - e.t));
      if (e.bytes) bits.push(fmtBytes(e.bytes));
      if (d.ip === 'all') bits.push(e.ip);
      if (bits.length) r.appendChild(el('span', 'meta', bits.join(' · ')));
      box.appendChild(r);
    });
  }
  function drawHistory(){
    var d = hdata, metric = hmetric.value;
    var cats = I.cats.filter(function(c){ return d.series[c.id]; });
    $('h-empty').hidden = cats.length > 0;
    $('h-body').hidden = cats.length === 0;
    if (!cats.length) return;
    curve(cats, d, metric);
    donut(cats, d, metric);
    topFiles(d);
    recent(d);
  }

