/** Le sommaire : liste des titres (jusqu'au niveau 4), panneau fixe sur grand écran, tiroir sur petit écran. */
class TableOfContents {
  heads = headings.list.filter(({level}) => level <= 4);
  nav = tocNav;
  #button = $('md-toc-btn');
  #veil = $('md-veil');
  #wide = window.matchMedia('(min-width:1000px)');
  #links = null;
  #elements = null;

  constructor() {
    if (this.heads.length < 2) {
      this.nav.hidden = true;
      this.#button.hidden = true;
    } else {
      const minLevel = Math.min(...this.heads.map(({level}) => level));
      tocList.innerHTML = this.heads
        .map(({id, text, level}) => `<a href="#${esc(id)}" data-id="${esc(id)}" style="--ind:${level - minLevel}">${esc(text)}</a>`)
        .join('');
    }
    if (store.get('md-toc') === 'off') document.body.classList.add('toc-off');
    this.#sync();
    this.#button.addEventListener('click', () => this.toggle());
    this.#veil.addEventListener('click', () => this.close());
    this.#wide.addEventListener('change', () => this.close());
  }

  get links() {
    return (this.#links ??= [...tocList.querySelectorAll('a')]);
  }
  get headingElements() {
    return (this.#elements ??= this.heads.map(({id}) => document.getElementById(id)));
  }
  get isWide() {
    return this.#wide.matches;
  }
  get isOpen() {
    return this.nav.classList.contains('open');
  }
  get hasButton() {
    return !this.#button.hidden;
  }

  #sync() {
    const on = this.#wide.matches ? !document.body.classList.contains('toc-off') : this.isOpen;
    this.#button.classList.toggle('on', on);
  }

  close() {
    this.nav.classList.remove('open');
    this.#veil.hidden = true;
    this.#sync();
  }

  toggle() {
    if (this.#wide.matches) {
      const off = document.body.classList.toggle('toc-off');
      store.set('md-toc', off ? 'off' : 'on');
    } else {
      const open = this.nav.classList.toggle('open');
      this.#veil.hidden = !open;
    }
    this.#sync();
  }
}

const toc = new TableOfContents();
