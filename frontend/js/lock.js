/* Cadenas du haut de page : déverrouillage (mot de passe demandé uniquement ici) et verrouillage. */
(() => {
  const ICO = window.LKICO ?? {};
  const HEADERS = {'X-Requested-With': 'biblio'};

  const post = async (url, body) => {
    const r = await fetch(url, {method: 'POST', credentials: 'same-origin', headers: HEADERS, body});
    return r.json();
  };

  class LockToggle {
    #button = document.getElementById('lock-toggle');
    #state = {enabled: false, unlocked: false};
    #first = null;                                   // premier état connu : sert à détecter un changement fait depuis un autre onglet

    constructor() {
      this.#button?.addEventListener('click', () => this.toggle());
      document.addEventListener('click', (e) => {
        const trigger = e.target.closest?.('[data-unlock]');
        if (trigger) { e.preventDefault(); this.openDialog(); }
      });
      document.addEventListener('visibilitychange', () => { if (!document.hidden) this.refresh(); });
      window.addEventListener('focus', () => this.refresh());
      this.refresh();
    }

    paint() {
      const button = this.#button;
      if (!button) return;
      const {enabled, unlocked} = this.#state;
      const title = unlocked ? 'Accès déverrouillé : cliquer pour verrouiller' : 'Accès verrouillé : cliquer pour déverrouiller';
      button.hidden = !enabled;
      button.innerHTML = unlocked ? ICO.unlock : ICO.lock;
      button.classList.toggle('unlocked', unlocked);
      button.title = title;
      button.setAttribute('aria-label', title);
    }

    async toggle() {
      if (!this.#state.unlocked) return this.openDialog();
      await post('/lock');
      location.reload();
    }

    openDialog() {
      if (document.querySelector('.lkveil')) return;
      const veil = document.createElement('div');
      veil.className = 'lkveil';
      veil.innerHTML = `<form class="lkbox" autocomplete="off"><h2>Déverrouiller l’accès</h2>
        <p>Le mot de passe n’est demandé qu’ici. Ensuite, la modification, le renommage, la suppression, l’envoi de fichiers et le tableau de bord ne le redemandent plus, jusqu’au prochain verrouillage.</p>
        <input type="password" placeholder="Mot de passe" autocomplete="current-password" required>
        <p class="lkerr" role="alert"></p><div class="row"><button type="button" class="pill" data-x>Annuler</button>
        <button type="submit" class="pill primary">Déverrouiller</button></div></form>`;
      document.body.appendChild(veil);
      document.documentElement.classList.add('noscroll-lk');

      const form = veil.firstElementChild;
      const password = form.querySelector('input');
      const error = form.querySelector('.lkerr');
      const submit = form.querySelector('[type=submit]');
      const onKey = (e) => { if (e.key === 'Escape') close(); };
      const close = () => {
        veil.remove();
        document.documentElement.classList.remove('noscroll-lk');
        document.removeEventListener('keydown', onKey);
      };
      document.addEventListener('keydown', onKey);
      veil.addEventListener('click', (e) => { if (e.target === veil) close(); });
      form.querySelector('[data-x]').addEventListener('click', close);
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        submit.disabled = true;
        error.textContent = '';
        try {
          const answer = await post('/unlock', password.value);
          if (answer.ok) return location.reload();
          error.textContent = answer.error || 'Erreur';
          password.value = '';
          password.focus();
        } catch {
          error.textContent = 'Connexion impossible.';
        }
        submit.disabled = false;
      });
      setTimeout(() => password.focus(), 30);
    }

    async refresh() {
      try {
        const state = await (await fetch('/lock-state', {credentials: 'same-origin'})).json();
        this.#state = state;
        this.paint();
        if (window.FLCFG) window.FLCFG.unlocked = !!state.files;
        const watched = window.LKRELOAD;
        if (this.#first === null) this.#first = state;
        else if (watched && !!state[watched] !== !!this.#first[watched]) location.reload();
      } catch { /* serveur injoignable : on garde l'état affiché */ }
    }
  }

  new LockToggle();
})();
