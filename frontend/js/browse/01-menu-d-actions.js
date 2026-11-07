
/** La feuille (menu et boîtes de dialogue) : un seul panneau visible à la fois ; la page derrière ne défile plus. */
class Sheet {
  static PANELS = ['sheet-main', 'newdlg', 'mkdlg', 'deldlg', 'rendlg', 'edtdlg', 'updlg'];

  #wrap = $('sheet');
  #body = $('sh-body');

  constructor() {
    new MutationObserver(() => this.#lockScroll()).observe(this.#wrap, {attributes: true, attributeFilter: ['hidden']});
    this.#lockScroll();
    this.#wrap.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', () => this.close()));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !this.#wrap.hidden) this.close(); });
  }

  get body() { return this.#body; }
  get isOpen() { return !this.#wrap.hidden; }

  /** Montre le panneau `id` (et lui seul) et ouvre la feuille. */
  show(id) {
    Sheet.PANELS.forEach((panel) => { $(panel).hidden = panel !== id; });
    this.#wrap.hidden = false;
  }

  close() {
    this.#wrap.hidden = true;
    Sheet.PANELS.filter((panel) => panel !== 'sheet-main').forEach((panel) => { $(panel).hidden = true; });
    this.#body.innerHTML = '';
  }

  // Feuille ouverte : la molette / le doigt ne font défiler que le menu.
  #lockScroll() {
    const root = document.documentElement;
    const on = !this.#wrap.hidden;
    if (on === root.classList.contains('noscroll')) return;
    root.style.paddingRight = on && window.innerWidth > root.clientWidth ? `${window.innerWidth - root.clientWidth}px` : '';
    root.classList.toggle('noscroll', on);
  }
}

/** Le menu d'actions d'un fichier ou d'un dossier. */
class ItemMenu {
  static OPTIONS = {
    watch:    {ic: 'play',     t: 'Regarder',           d: 'Lire la vidéo',                        u: (f) => `/watch?f=${f}`},
    pdf:      {ic: 'file',     t: 'Lire le PDF',        d: 'Ouvrir dans le lecteur PDF',           u: (f) => `/pdf?f=${f}`},
    view:     {ic: 'eye',      t: 'Lire',               d: 'Affichage avec coloration syntaxique', u: (f) => `/view?f=${f}`},
    edit:     {ic: 'edit',     t: 'Éditer',             d: 'Éditeur de type Vim',                  u: (f) => `/edit?f=${f}`, protected: true},
    preview:  {ic: 'globe',    t: 'Aperçu de la page',  d: 'Afficher la page web rendue',          u: (f) => `/preview?f=${f}`},
    mdview:   {ic: 'book',     t: 'Aperçu',             d: 'Rendu Markdown, mis en page pour la lecture', u: (f) => `/preview?f=${f}`},
    mdsrc:    {ic: 'code',     t: 'Source',             d: 'Texte brut avec coloration syntaxique', u: (f) => `/view?f=${f}`},
    listen:   {ic: 'music',    t: 'Écouter',            d: 'Lecteur audio (aléatoire, répétition…)', u: (f) => `/listen?f=${f}`},
    open:     {ic: 'external', t: 'Ouvrir',             d: 'Afficher dans le navigateur',          u: (f) => `/raw?f=${f}`},
    download: {ic: 'download', t: 'Télécharger',        d: 'Enregistrer une copie',                u: (f) => `/raw?dl=1&f=${f}`},
    openf:    {ic: 'folder',   t: 'Ouvrir',             d: 'Afficher le contenu du dossier',       u: (f) => `/?folder=${f}`},
    zip:      {ic: 'download', t: 'Télécharger en ZIP', d: 'Archive du dossier et de son contenu', u: (f) => `/zip?f=${f}`},
    rename:   {ic: 'rename',   t: 'Renommer',           d: 'Changer le nom du fichier',            u: null, protected: true, attr: 'data-ren'},
    del:      {ic: 'trash',    t: 'Supprimer',          d: 'Supprimer définitivement',             u: null, protected: true, danger: true, attr: 'data-del'},
  };

  /** Actions proposées selon le type de l'élément. */
  static BY_KIND = {
    video: ['watch', 'open', 'download'], pdf: ['pdf', 'open', 'download'], text: ['view', 'edit', 'download'],
    web: ['preview', 'view', 'edit', 'download'], image: ['open', 'download'], audio: ['listen', 'open', 'download'],
    binary: ['download'], folder: ['openf', 'zip'], md: ['mdview', 'mdsrc', 'edit', 'download'],
  };

  #sheet;
  #on;                                                      // {delete(item), rename(item), edit(item)}

  constructor(sheet, on) {
    this.#sheet = sheet;
    this.#on = on;
  }

  open(item) {
    const {kind, f, title, size, ico, icls, md} = item.dataset;
    const keys = [...(md === '1' ? ItemMenu.BY_KIND.md : (ItemMenu.BY_KIND[kind] ?? ['view', 'edit', 'download']))]
      .filter((key) => !(cfg.readonly && key === 'edit'));
    if (cfg.canDelete) keys.push('rename', 'del');
    $('sh-title').textContent = title;
    $('sh-sub').textContent = size;
    $('sh-ico').innerHTML = ICO[ico] ?? '';
    $('sh-ico').className = `ico ${icls ?? ''}`;
    this.#sheet.body.innerHTML = keys.map((key) => this.#render(key, f)).join('');

    const body = this.#sheet.body;
    body.querySelector('[data-del]')?.addEventListener('click', (e) => { e.preventDefault(); this.#on.delete(item); });
    body.querySelector('[data-ren]')?.addEventListener('click', (e) => { e.preventDefault(); this.#on.rename(item); });
    body.querySelector('[data-edt]')?.addEventListener('click', (e) => {
      if (cfg.protect && !cfg.unlocked) { e.preventDefault(); this.#on.edit(item); }
    });
    this.#sheet.show('sheet-main');
  }

  #render(key, f) {
    const option = ItemMenu.OPTIONS[key];
    const description = option.protected && cfg.protect && !cfg.unlocked ? 'Accès verrouillé' : option.d;
    const attribute = key === 'edit' ? ' data-edt="1"' : option.attr ? ` ${option.attr}="1"` : '';
    return `<a class="opt${option.danger ? ' danger' : ''}"${attribute} href="${option.u ? option.u(f) : '#'}"><span class="ico back">${ICO[option.ic]}</span><span class="text"><span class="name">${escapeHtml(option.t)}</span><div class="sub">${escapeHtml(description)}</div></span><span class="go">${ICO.chevron}</span></a>`;
  }
}
