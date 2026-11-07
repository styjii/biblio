
/** La liste des appareils connectés, avec blocage / déblocage. */
class DeviceList {
  #box = $('devices');
  #onHistory;                                            // (ip) -> affiche l'historique de cet appareil
  #onChange;                                             // () -> recharge les données après un blocage

  constructor({onHistory, onChange}) {
    this.#onHistory = onHistory;
    this.#onChange = onChange;
  }

  render(devices) {
    this.#box.textContent = '';
    for (const device of devices) this.#box.appendChild(this.#row(device));
    if (!devices.length) this.#box.appendChild(el('div', 'empty', 'Aucun appareil pour le moment.'));
  }

  async #toggleBlock(ip, block) {
    if (block && !confirm(`Bloquer ${ip} ? Cet appareil n'aura plus accès à la bibliothèque.`)) return;
    try {
      const r = await fetch(`/dashboard/${block ? 'block' : 'unblock'}?ip=${encodeURIComponent(ip)}`, {
        method: 'POST', headers: HEADERS, credentials: 'same-origin',
      });
      if (r.status === 401) return location.reload();
      const answer = await r.json();
      if (!answer.ok) alert(answer.error || 'Erreur');
      else if (answer.warning) alert(answer.warning);
      this.#onChange();
    } catch {
      alert('Connexion impossible.');
    }
  }

  #row(device) {
    const {ip, blocked, me, local, auth, ago, ua, mac, hits} = device;
    const row = el('div', `dev${blocked ? ' blocked' : ''}`);
    const icon = el('div', `ico ${blocked ? 'danger' : 'code'}`);
    icon.innerHTML = blocked ? config.ban : config.monitor;

    const text = el('div', 'text');
    const top = el('div', 'dev-top');
    top.appendChild(el('span', 'ip', ip));
    if (me) top.appendChild(el('span', 'tag me', 'Cet appareil'));
    else if (local) top.appendChild(el('span', 'tag me', 'Serveur'));
    if (blocked) {
      top.appendChild(el('span', 'tag bad', 'Bloqué'));
    } else if (ago !== null && !auth) {
      const warning = el('span', 'tag bad', 'Sans jeton');
      warning.title = "N'a jamais présenté le jeton d'accès";
      top.appendChild(warning);
    }
    const details = [ua, mac && `MAC ${mac}`, Format.ago(ago), hits && `${hits} ${hits > 1 ? 'requêtes' : 'requête'}`].filter(Boolean);
    text.append(top, el('div', 'sub', details.join(' · ')));

    const actions = el('div', 'dev-actions');
    const history = el('button', 'pill', 'Historique');
    history.type = 'button';
    history.addEventListener('click', () => this.#onHistory(ip));
    actions.appendChild(history);
    if (!me && !local) {
      const block = el('button', `pill${blocked ? '' : ' danger'}`, blocked ? 'Débloquer' : 'Bloquer');
      block.type = 'button';
      block.addEventListener('click', () => this.#toggleBlock(ip, !blocked));
      actions.appendChild(block);
    }
    row.append(icon, text, actions);
    return row;
  }
}
