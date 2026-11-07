/** Copie du code (bouton « Copier ») et agrandissement des images. */
class CodeCopy {
  constructor() {
    art.addEventListener('click', async (e) => {
      const target = e.target;
      const button = target.closest?.('button.copy');
      if (button) {
        const ok = await CodeCopy.copy(button.closest('figure').querySelector('code').textContent);
        button.textContent = ok ? 'Copié' : 'Échec';
        setTimeout(() => {
          button.textContent = 'Copier';
        }, 1600);
        return;
      }
      if (target.tagName === 'IMG' && !target.closest?.('a')) CodeCopy.lightbox(target);
    });
  }

  /** Copie dans le presse-papiers (API moderne si possible, sinon repli par un champ temporaire). -> true si réussi */
  static async copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        /* repli ci-dessous */
      }
    }
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      /* copie refusée */
    }
    area.remove();
    return ok;
  }

  /** Image en grand ; un clic ou Échap la ferme. */
  static lightbox(image) {
    const box = document.createElement('div');
    box.className = 'mdbox';
    const big = document.createElement('img');
    big.src = image.src;
    big.alt = image.alt;
    box.appendChild(big);
    const onKey = (e) => {
      if (e.key === 'Escape') close();
    };
    const close = () => {
      box.remove();
      document.removeEventListener('keydown', onKey);
    };
    box.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    document.body.appendChild(box);
  }
}

new CodeCopy();
