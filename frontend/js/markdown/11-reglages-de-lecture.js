  /** Réglages de lecture : taille du texte (14 à 26 px), police (serif / sans), impression. */
  class ReadingSettings {
    static MIN = 14;
    static MAX = 26;

    #size;
    #sans = store.get('md-ff') === 'sans';
    #fontButton = $('md-ff');

    constructor() {
      const saved = parseInt(store.get('md-fs') || '18', 10);
      this.#size = saved >= ReadingSettings.MIN && saved <= ReadingSettings.MAX ? saved : 18;
      this.#applySize();
      this.#applyFont();
      $('md-fs-down').addEventListener('click', () => {
        if (this.#size > ReadingSettings.MIN) {
          this.#size--;
          this.#applySize();
        }
      });
      $('md-fs-up').addEventListener('click', () => {
        if (this.#size < ReadingSettings.MAX) {
          this.#size++;
          this.#applySize();
        }
      });
      this.#fontButton.addEventListener('click', () => {
        this.#sans = !this.#sans;
        store.set('md-ff', this.#sans ? 'sans' : 'serif');
        this.#applyFont();
        progress.update();
      });
      $('md-print').addEventListener('click', () => window.print());
    }

    #applySize() {
      art.style.setProperty('--mdfs', `${this.#size}px`);
      store.set('md-fs', String(this.#size));
      progress.update();
    }

    #applyFont() {
      art.classList.toggle('sans', this.#sans);
      this.#fontButton.textContent = this.#sans ? 'Sans' : 'Serif';
      this.#fontButton.classList.toggle('on', this.#sans);
    }
  }

  new ReadingSettings();

  
