
  /** Mémoire de l'appareil et capacité des disques configurés. */
  class SystemPanel {
    static meterClass(percent) { return percent >= 90 ? 'crit' : percent >= 70 ? 'warn' : ''; }

    memory(memory) {
      $('mem').hidden = !memory;
      $('mem-na').hidden = !!memory;
      if (!memory) return;
      $('m-used').textContent = memory.used_h;
      $('m-free').textContent = memory.free_h;
      $('m-total').textContent = memory.total_h;
      const bar = $('meter-bar');
      bar.style.width = `${memory.percent}%`;
      bar.className = SystemPanel.meterClass(memory.percent);
      $('m-pct-val').textContent = `${Format.percent(memory.percent)} %`;
      $('m-pct').textContent = 'Libre = mémoire disponible (cache récupérable inclus)';
    }

    disks(disks) {
      const box = $('disks');
      box.textContent = '';
      $('disks-sec').hidden = !disks.length;
      for (const disk of disks) {
        const card = el('div', 'stat');
        const head = el('div', 'dev-top');
        head.append(el('span', 'label', disk.label), el('span', 'tag', disk.path));
        if (disk.system) {
          const warning = el('span', 'tag bad', 'Même volume que le système');
          warning.title = 'Ce chemin ne semble pas être un disque monté séparément';
          head.appendChild(warning);
        }
        card.appendChild(head);
        if (disk.error) {
          card.appendChild(el('div', 'sub', disk.error));
        } else {
          const meter = el('div', 'meter');
          const fill = el('span', SystemPanel.meterClass(disk.percent));
          fill.style.width = `${disk.percent}%`;
          meter.appendChild(fill);
          card.append(
            el('div', 'value', `${disk.free_h} libres`),
            meter,
            el('div', 'sub', `${disk.used_h} utilisés sur ${disk.total_h} (${Format.percent(disk.percent)} %)`),
          );
        }
        box.appendChild(card);
      }
    }
  }
