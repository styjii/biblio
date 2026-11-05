
  /** Le tableau de bord : chargement périodique des données et rafraîchissement des panneaux. */
  class Dashboard {
    #loading = false;
    #history = new HistoryPanel();
    #system = new SystemPanel();
    #devices = new DeviceList({
      onHistory: (ip) => this.#history.open(ip),
      onChange: () => this.load({force: true}),
    });

    constructor() {
      $('lock').addEventListener('click', async () => {
        await fetch('/lock', {method: 'POST', headers: HEADERS, credentials: 'same-origin'});
        location.reload();
      });
      document.addEventListener('visibilitychange', () => { if (!document.hidden) { this.load(); this.#history.load(); } });
      setInterval(() => { if (!document.hidden) this.load(); }, 3000);
      setInterval(() => { if (!document.hidden) this.#history.load(); }, 15000);
      this.load();
      this.#history.load();
    }

    #render(data) {
      $('host').textContent = data.host;
      this.#system.memory(data.memory);
      this.#system.disks(data.disks ?? []);
      $('n-active').textContent = data.active;
      $('dev-sub').textContent = `${data.active} ${data.active > 1 ? 'appareils connectés' : 'appareil connecté'} (activité depuis moins de ${Math.round(data.window / 60)} min) · ${data.blocked}${data.blocked > 1 ? ' bloqués' : ' bloqué'}`;
      this.#devices.render(data.devices);
      this.#history.syncDevices(data.devices);
    }

    async load({force = false} = {}) {
      if (this.#loading && !force) return;
      this.#loading = true;
      try {
        const data = await getJson('/dashboard/data');
        if (data?.ok) {
          this.#render(data);
          $('upd').textContent = `mis à jour à ${new Date().toLocaleTimeString('fr-FR')}`;
        }
      } catch {
        $('upd').textContent = 'connexion perdue, nouvel essai…';
      }
      this.#loading = false;
    }
  }

  new Dashboard();
})();
