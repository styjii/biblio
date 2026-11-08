/* Vignettes vidéo : durée affichée sur l'image et barre de reprise (position de CET appareil, fournie par /meta). */
(() => {
  const fmt = (seconds) => {
    const s = Math.floor(seconds);
    const h = Math.floor(s / 3600);
    const m = Math.floor(s % 3600 / 60);
    const mm = h ? String(m).padStart(2, '0') : String(m);
    return `${h ? `${h}:` : ''}${mm}:${String(s % 60).padStart(2, '0')}`;
  };

  const showBar = (card, position, duration) => {
    const bar = card.querySelector('.bar');
    if (!bar || !duration || !position) return;
    bar.hidden = false;
    bar.firstElementChild.style.width = `${Math.min(100, position / duration * 100)}%`;
  };

  async function decorate(card) {
    try {
      const {duration, pos = 0} = await (await fetch(`/meta?f=${card.dataset.f}`)).json();
      if (!duration) return;
      card.dataset.dur = String(duration);                  // lue aussi par le tri « Durée » de la liste
      document.dispatchEvent(new Event('biblio:duration'));
      const label = card.querySelector('.dur');
      if (label) { label.textContent = fmt(duration); label.hidden = false; }
      showBar(card, pos, duration);
    } catch { /* vignette laissée telle quelle */ }
  }

  const cards = document.querySelectorAll('[data-key]');
  if (!('IntersectionObserver' in window)) { cards.forEach(decorate); return; }
  const observer = new IntersectionObserver((entries) => {
    for (const {isIntersecting, target} of entries) {
      if (!isIntersecting) continue;
      observer.unobserve(target);
      decorate(target);
    }
  }, {rootMargin: '200px'});
  cards.forEach((card) => observer.observe(card));
})();
