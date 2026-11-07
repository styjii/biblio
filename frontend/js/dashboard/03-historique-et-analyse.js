
/** Historique d'activité : courbe empilée, répartition, fichiers les plus consultés et liste récente, par appareil. */
class HistoryPanel {
  #device = $('h-dev');
  #range = $('h-range');
  #metric = $('h-metric');
  #data = null;
  #sequence = 0;                                         // ignore les réponses arrivées dans le désordre
  #deviceKey = '';

  constructor() {
    this.#device.addEventListener('change', () => this.load());
    this.#range.addEventListener('change', () => this.load());
    this.#metric.addEventListener('change', () => { if (this.#data) this.#draw(); });
  }

  /** Catégorie d'activité (libellé, couleur) ; inconnue : affichée avec son identifiant. */
  static category(id) {
    return config.cats.find((c) => c.id === id) ?? {id, label: id, color: 'var(--muted)'};
  }

  /** Met à jour la liste déroulante des appareils quand elle change. */
  syncDevices(devices) {
    const key = devices.map((d) => d.ip).join(',');
    if (key === this.#deviceKey) return;
    this.#deviceKey = key;
    const current = this.#device.value;
    this.#device.textContent = '';
    const all = el('option', null, 'Tous les appareils');
    all.value = 'all';
    this.#device.appendChild(all);
    for (const {ip, ua, me} of devices) {
      const option = el('option', null, `${ip}${ua ? ` · ${ua}` : ''}${me ? ' (cet appareil)' : ''}`);
      option.value = ip;
      this.#device.appendChild(option);
    }
    this.#device.value = current;
    if (!this.#device.value) this.#device.value = 'all';
  }

  open(ip) {
    this.#device.value = ip;
    if (!this.#device.value) this.#device.value = 'all';
    this.load();
    $('hist').scrollIntoView({behavior: 'smooth'});
  }

  async load() {
    const mine = ++this.#sequence;
    try {
      const data = await getJson(`/dashboard/history?ip=${encodeURIComponent(this.#device.value || 'all')}&range=${this.#range.value}`);
      if (data?.ok && mine === this.#sequence) { this.#data = data; this.#draw(); }
    } catch { /* on réessaie au prochain rafraîchissement */ }
  }

  #timeLabel(timestamp, long) {
    const date = new Date(timestamp * 1000);
    if (long) return date.toLocaleString('fr-FR', {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
    if (this.#data?.range === '24h') return date.toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'});
    return date.toLocaleDateString('fr-FR', {day: 'numeric', month: 'short'});
  }

  #draw() {
    const data = this.#data;
    const metric = this.#metric.value;
    const cats = config.cats.filter((c) => data.series[c.id]);
    $('h-empty').hidden = cats.length > 0;
    $('h-body').hidden = cats.length === 0;
    if (!cats.length) return;
    this.#drawCurve(cats, data, metric);
    this.#drawDonut(cats, data, metric);
    this.#drawTopFiles(data);
    this.#drawRecent(data);
  }

  #swatch(color) {
    const swatch = el('span', 'sw');
    swatch.style.background = color;
    return swatch;
  }

  #drawCurve(cats, data, metric) {
    const {n} = data;
    const [W, HEIGHT, L, R, T, B] = [640, 220, 50, 8, 10, 24];            // dimensions du graphique et marges
    const pw = W - L - R;
    const ph = HEIGHT - T - B;
    const f = Format.fixed;
    const stacked = Array(n).fill(0);
    for (const c of cats) data.series[c.id][metric].forEach((v, k) => { stacked[k] += v; });
    const max = Format.niceMax(Math.max(...stacked), metric);
    const x = (k) => L + (n > 1 ? k * pw / (n - 1) : pw / 2);
    const y = (v) => T + ph - v / max * ph;

    let svg = `<svg viewBox="0 0 ${W} ${HEIGHT}" class="chart" role="img" aria-label="Courbe d activité">`;
    for (let g = 0; g <= 4; g++) {                                          // graduations horizontales
      const gy = y(max * g / 4);
      svg += `<line class="grid" x1="${L}" x2="${W - R}" y1="${f(gy)}" y2="${f(gy)}"/><text class="axis" x="${L - 6}" y="${f(gy + 3.5)}" text-anchor="end">${Format.metric(max * g / 4, metric)}</text>`;
    }
    let base = Array(n).fill(0);
    for (const c of cats) {                                                 // une aire par catégorie, empilées
      const top = data.series[c.id][metric].map((v, k) => base[k] + v);
      let path = `M${f(x(0))} ${f(y(base[0]))}`;
      for (let k = 0; k < n; k++) path += ` L${f(x(k))} ${f(y(top[k]))}`;
      for (let k = n - 1; k >= 0; k--) path += ` L${f(x(k))} ${f(y(base[k]))}`;
      svg += `<path class="area" d="${path}Z" style="fill:${c.color}"/>`;
      base = top;
    }
    [0, 0.25, 0.5, 0.75, 1].forEach((fraction, k) => {                      // repères de temps
      const index = Math.round(fraction * (n - 1));
      const anchor = k === 0 ? 'start' : k === 4 ? 'end' : 'middle';
      svg += `<text class="axis" x="${f(x(index))}" y="${HEIGHT - 6}" text-anchor="${anchor}">${this.#timeLabel(data.start + index * data.step, false)}</text>`;
    });
    svg += `<line class="cursor" x1="0" x2="0" y1="${T}" y2="${T + ph}"/><rect class="hit" x="${L}" y="${T}" width="${pw}" height="${ph}"/></svg>`;

    $('h-curve').innerHTML = svg;
    const chart = $('h-curve').firstChild;
    const cursor = chart.querySelector('.cursor');
    const show = (event) => {                                               // détail de la tranche survolée ou touchée
      const box = chart.getBoundingClientRect();
      const px = (event.clientX - box.left) / box.width * W;
      const k = Math.max(0, Math.min(n - 1, Math.round((px - L) / pw * (n - 1))));
      cursor.setAttribute('x1', f(x(k)));
      cursor.setAttribute('x2', f(x(k)));
      cursor.style.visibility = 'visible';
      const parts = cats
        .map((c) => [c, data.series[c.id][metric][k]])
        .filter(([, value]) => value)
        .map(([c, value]) => `${c.label} ${Format.metric(value, metric)}`);
      $('h-read').textContent = `${this.#timeLabel(data.start + k * data.step, true)} : ${parts.length ? parts.join(' · ') : 'aucune activité'}`;
    };
    const hit = chart.querySelector('.hit');
    hit.addEventListener('pointermove', show);
    hit.addEventListener('pointerdown', show);
    $('h-read').textContent = 'Touche ou survole la courbe pour le détail.';

    const legend = $('h-legend');
    legend.textContent = '';
    for (const c of cats) {
      const item = el('span', null, `${c.label} `);
      item.prepend(this.#swatch(c.color));
      item.appendChild(el('b', null, Format.metric(data.totals[c.id][metric], metric)));
      legend.appendChild(item);
    }
  }

  #drawDonut(cats, data, metric) {
    const total = cats.reduce((sum, c) => sum + data.totals[c.id][metric], 0);
    let svg = '<svg viewBox="0 0 42 42" class="donut" role="img" aria-label="Répartition par catégorie"><circle cx="21" cy="21" r="15.9155" class="ring"/>';
    let offset = 25;
    const share = $('h-share');
    share.textContent = '';
    for (const c of cats) {
      const value = data.totals[c.id][metric];
      if (!value || !total) continue;
      const percent = value / total * 100;
      svg += `<circle cx="21" cy="21" r="15.9155" class="seg" style="stroke:${c.color}" stroke-dasharray="${percent.toFixed(2)} ${(100 - percent).toFixed(2)}" stroke-dashoffset="${offset.toFixed(2)}"/>`;
      offset -= percent;
      const label = el('span', null, c.label);
      label.prepend(this.#swatch(c.color));
      const line = el('div');
      line.append(label, el('b', null, `${Math.round(percent)} %`));
      share.appendChild(line);
    }
    svg += `<text x="21" y="22.8" text-anchor="middle" class="dtot">${Format.metric(total, metric)}</text></svg>`;
    $('h-donut').innerHTML = svg;
  }

  #drawTopFiles({top}) {
    const box = $('h-top');
    box.textContent = '';
    if (!top.length) { box.appendChild(el('div', 'sub', 'Aucun fichier consulté.')); return; }
    const max = top[0].n;
    for (const {cat, file, n, seconds, bytes} of top) {
      const category = HistoryPanel.category(cat);
      const row = el('div', 'top-row');
      const details = [category.label, `${n} fois`, seconds >= 5 && Format.duration(seconds), bytes && Format.bytes(bytes)].filter(Boolean);
      const bar = el('div', 'bar');
      const fill = el('span');
      fill.style.width = `${Math.max(4, n / max * 100)}%`;
      fill.style.background = category.color;
      bar.appendChild(fill);
      row.append(el('div', 'name', file), el('div', 'sub', details.join(' · ')), bar);
      box.appendChild(row);
    }
  }

  #drawRecent({recent, ip}) {
    const box = $('h-list');
    box.textContent = '';
    for (const entry of recent) {
      const category = HistoryPanel.category(entry.cat);
      const row = el('div', 'h-item');
      const what = el('span', 'what');
      what.append(this.#swatch(category.color), document.createTextNode(`${category.label} · ${entry.file || '/'}`));
      row.append(el('span', 'when', this.#timeLabel(entry.t, true)), what);
      const details = [entry.end - entry.t >= 5 && Format.duration(entry.end - entry.t), entry.bytes && Format.bytes(entry.bytes), ip === 'all' && entry.ip].filter(Boolean);
      if (details.length) row.appendChild(el('span', 'meta', details.join(' · ')));
      box.appendChild(row);
    }
  }
}
