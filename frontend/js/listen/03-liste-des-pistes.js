
  /** La liste des pistes : lignes cliquables, piste courante, durées chargées à mesure qu'on les voit, filtre. */
  class TrackList {
    #box = $('l-list');
    #rows = [];
    #current = null;
    #info;

    constructor(info, onSelect) {
      this.#info = info;
      this.#build(onSelect);
      $('l-filter').addEventListener('input', () => this.applyFilter());
    }

    #build(onSelect) {
      const observer = 'IntersectionObserver' in window
        ? new IntersectionObserver((entries) => {
          for (const {isIntersecting, target} of entries) {
            if (!isIntersecting) continue;
            observer.unobserve(target);
            this.#showDurationOf(Number(target.dataset.i));
          }
        }, {root: this.#box, rootMargin: '120px'})
        : null;
      const part = (tag, className, text = '') => Object.assign(document.createElement(tag), {className, textContent: text});

      this.#box.textContent = '';
      tracks.forEach((track, i) => {
        const row = part('button', 'ltrack');
        row.type = 'button';
        row.dataset.i = i;
        const num = part('span', 'num');
        const equalizer = part('span', 'eqi');
        equalizer.innerHTML = icons.eq ?? '';
        num.append(part('span', 'n', i + 1), equalizer);
        row.append(num, part('span', 'tn', track.n), part('span', 'td'), part('span', 'te', track.e));
        row.addEventListener('click', () => onSelect(i));
        this.#box.appendChild(row);
        this.#rows.push(row);
        observer?.observe(row);
      });
    }

    async #showDurationOf(index) {
      const meta = await this.#info.get(index);
      this.showDuration(index, meta?.duration);
    }

    showDuration(index, seconds) {
      const cell = this.#rows[index]?.querySelector('.td');
      if (cell && seconds) cell.textContent = formatTime(seconds);
    }

    /** Marque la piste en cours ; `playing` : elle est en lecture. */
    markCurrent(index, playing) {
      if (this.#current) {
        this.#current.classList.remove('cur', 'playing');
        this.#current.removeAttribute('aria-current');
      }
      this.#current = this.#rows[index] ?? null;
      this.#current?.classList.add('cur');
      this.#current?.setAttribute('aria-current', 'true');
      this.setPlaying(playing);
    }

    setPlaying(playing) { this.#current?.classList.toggle('playing', playing); }
    markBad(index) { this.#rows[index]?.classList.add('bad'); }

    /** Fait défiler la liste elle-même (jamais la page) pour montrer la piste courante. */
    reveal(index) {
      const row = this.#rows[index];
      if (!row) return;
      requestAnimationFrame(() => {
        this.#box.scrollTop = Math.max(0, row.offsetTop - (this.#box.clientHeight - row.offsetHeight) / 2);
      });
    }

    applyFilter() {
      const query = $('l-filter').value.trim().toLowerCase();
      this.#rows.forEach((row, i) => { row.hidden = !!query && !tracks[i].n.toLowerCase().includes(query); });
    }
  }
