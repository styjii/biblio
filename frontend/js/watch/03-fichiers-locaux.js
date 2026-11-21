/** Lecteur de l'accueil : la liste des fichiers vidéo et audio de l'appareil (choisis ou déposés) et son affichage.
    C'est le même lecteur que la page de lecture (PlayerUI, VideoPlayer) : seule la source change. Le navigateur lit le
    fichier directement depuis le disque (URL locale créée à la demande), sans le copier ni l'envoyer au serveur.
    Les éléments de `items` valent ici {f: nom, u: URL locale (une seule à la fois), file, kind: 'video' | 'audio'}.
    Deux modes, Vidéo et Audio : `items` ne contient que les fichiers du mode affiché. Le lecteur étant unique, la file de l'autre
    mode est mise de côté (avec sa position et son état lecture/pause) et rétablie au retour (voir swap). */
class LocalFiles {
  static MODES = ['video', 'audio'];
  static VIDEO_EXT = new Set(['mp4', 'm4v', 'webm', 'mkv', 'mov', 'avi', 'ogv', 'ts', '3gp']);
  static AUDIO_EXT = new Set(['mp3', 'm4a', 'aac', 'flac', 'wav', 'ogg', 'oga', 'opus', 'mka', 'weba']);
  /** Image affichée à la place de la vidéo pour un son. */
  static AUDIO_POSTER = `data:image/svg+xml,${encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 9"><rect width="16" height="9" fill="#14171f"/>'
    + '<g transform="translate(5.9 1.9) scale(.2)" fill="none" stroke="#8b95ff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
    + '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></g></svg>')}`;

  #host;
  #url = null;
  #mode = 'video';
  #parked = {video: null, audio: null};                   // file du mode qui n'est pas affiché : {items, index, time, playing}

  constructor(host) {
    this.#host = host;
    this.render();
  }

  get mode() { return this.#mode; }

  static other(mode) { return mode === 'video' ? 'audio' : 'video'; }

  /** Nombre de fichiers de chaque mode (celui qui est affiché et celui qui est mis de côté). */
  get counts() {
    const other = LocalFiles.other(this.#mode);
    return {[this.#mode]: items.length, [other]: this.#parked[other]?.items.length ?? 0};
  }

  static kindOf(file) {
    if (file.type.startsWith('video/')) return 'video';
    if (file.type.startsWith('audio/')) return 'audio';
    const ext = file.name.split('.').pop().toLowerCase();
    if (LocalFiles.VIDEO_EXT.has(ext)) return 'video';
    if (LocalFiles.AUDIO_EXT.has(ext)) return 'audio';
    return null;
  }

  static stem(name) { return name.replace(/\.[^.]+$/, '') || name; }

  static size(bytes) {
    const units = ['o', 'Ko', 'Mo', 'Go', 'To'];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
    return `${unit === 0 || value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`.replace('.', ',');
  }

  /** Ajoute à la liste les fichiers du mode affiché. -> {mode, accepted, rejected, other}
      (`other` : fichiers de l'autre mode, laissés de côté ; `rejected` : ni vidéo ni audio). */
  add(files) {
    let accepted = 0;
    let rejected = 0;
    let other = 0;
    for (const file of files) {
      const kind = LocalFiles.kindOf(file);
      if (kind === this.#mode) { items.push({f: file.name, u: '', file, kind}); accepted += 1; } else if (kind) other += 1; else rejected += 1;
    }
    this.render();
    return {mode: this.#mode, accepted, rejected, other};
  }

  /** Change de mode : la file du mode quitté est mise de côté avec `state` ({time, playing}), celle de `mode` reprend.
      -> ce qui avait été mis de côté pour `mode` (ou null : rien à lire). L'affichage est rafraîchi par l'appelant. */
  swap(mode, state) {
    this.#parked[this.#mode] = items.length ? {items: items.splice(0), index, ...state} : null;
    this.#parked[this.#mode]?.items.forEach((item) => { item.u = ''; });     // l'URL locale est libérée ci-dessous
    this.#release();
    this.#mode = mode;
    const next = this.#parked[mode];
    this.#parked[mode] = null;
    index = next?.index ?? 0;
    if (next) items.push(...next.items);
    return next;
  }

  /** Prépare la lecture de `items[target]` : libère l'URL précédente, en crée une nouvelle. -> l'URL à donner au lecteur. */
  open(target) {
    this.#release();
    const item = items[target];
    this.#url = URL.createObjectURL(item.file);
    item.u = this.#url;
    if (item.kind === 'audio') video.poster = LocalFiles.AUDIO_POSTER; else video.removeAttribute('poster');
    this.render();
    return this.#url;
  }

  /** Retire un fichier de la liste (l'affichage est rafraîchi par l'appelant, une fois `index` à jour). */
  remove(target) { items.splice(target, 1); }

  clear() {
    this.#release();
    items.length = 0;
    video.removeAttribute('poster');
    this.render();
  }

  #release() {
    if (this.#url) { URL.revokeObjectURL(this.#url); this.#url = null; }
  }

  /** Affichage : lecteur et liste visibles seulement s'il y a des fichiers ; titre, informations, ligne en cours. */
  render() {
    $('watch').hidden = items.length === 0;
    const current = items[index];
    const title = current ? LocalFiles.stem(current.f) : '';
    document.querySelector('.vtitle').textContent = title;
    document.querySelector('.vp-top').textContent = title;
    $('mp-meta').textContent = current
      ? `${current.kind === 'video' ? 'Vidéo' : 'Audio'} · ${LocalFiles.size(current.file.size)} · ${(current.f.split('.').pop() || '').toUpperCase()}`
      : '';
    $('list-pos').textContent = `${current ? index + 1 : 0} / ${items.length}`;
    const list = $('mp-list');
    list.replaceChildren(...items.map((item, i) => this.#row(item, i)));
    document.dispatchEvent(new CustomEvent('biblio:local', {detail: {count: items.length, mode: this.#mode, counts: this.counts}}));
  }

  #row(item, i) {
    const make = (tag, className, text = '') => {
      const node = document.createElement(tag);
      node.className = className;
      if (text) node.textContent = text;
      return node;
    };
    const row = make('div', `row${i === index ? ' cur' : ''}`);
    row.dataset.f = item.f;
    const open = make('button', 'mp-main');
    open.type = 'button';
    const thumb = make('div', 'rthumb');
    const placeholder = make('div', 'ph');
    placeholder.innerHTML = icons[item.kind === 'video' ? 'film' : 'music'] ?? '';
    thumb.append(placeholder);
    const info = make('div', 'rinfo');
    info.append(make('div', 'rname', LocalFiles.stem(item.f)),
      make('div', 'rsub', `${item.kind === 'video' ? 'Vidéo' : 'Audio'} · ${LocalFiles.size(item.file.size)}`));
    open.append(thumb, info);
    open.addEventListener('click', () => this.#host.playLocal(i));
    const remove = make('button', 'abtn sm');
    remove.type = 'button';
    remove.title = 'Retirer de la liste';
    remove.setAttribute('aria-label', `Retirer ${item.f} de la liste`);
    remove.innerHTML = icons.close ?? '×';
    remove.addEventListener('click', () => this.#host.removeLocal(i));
    row.append(open, remove);
    return row;
  }
}
