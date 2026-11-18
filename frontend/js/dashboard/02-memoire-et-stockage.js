
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

  /** Stockage : un bloc par chemin du .env (espace libre en premier) ; le dossier courant est une part de son volume. */
  storage(storage) {
    const disks = storage?.disks ?? [];
    const box = $('disks');
    box.textContent = '';
    $('disks-sec').hidden = !disks.length;
    $('disks-count').textContent = disks.length;
    $('disks-total').textContent = disks.length
      ? `${storage.free_total_h} libres au total sur ${storage.volumes} ${storage.volumes > 1 ? 'volumes' : 'volume'} (un volume partagé n'est compté qu'une fois)`
      : '';
    for (const disk of disks) box.appendChild(this.#diskCard(disk));
  }

  #diskCard(disk) {
    const card = el('div', 'stat');
    const head = el('div', 'dev-top');
    head.append(el('span', 'label', disk.label), el('span', 'tag', disk.path));
    if (disk.current) head.appendChild(el('span', 'tag me', 'Dossier courant'));
    if (disk.same_volume_as) {
      const shared = el('span', 'tag', `Même volume que ${disk.same_volume_as}`);
      shared.title = 'Ces chemins partagent le même espace : il n\'est compté qu\'une fois dans le total';
      head.appendChild(shared);
    }
    if (disk.system) {
      const warning = el('span', 'tag bad', 'Même volume que le système');
      warning.title = 'Ce chemin ne semble pas être un disque monté séparément';
      head.appendChild(warning);
    }
    card.appendChild(head);
    if (disk.error) {
      card.appendChild(el('div', 'sub', disk.error));
      return card;
    }
    const meter = el('div', 'meter');
    const fill = el('span', SystemPanel.meterClass(disk.percent));
    fill.style.width = `${disk.percent}%`;
    meter.appendChild(fill);
    if (disk.folder?.percent) {    // part du dossier courant, comprise dans l'espace utilisé (jamais ajoutée à la barre)
      const part = el('span', 'part');
      part.style.width = `${Math.min(disk.folder.percent, disk.percent)}%`;
      meter.appendChild(part);
    }
    card.append(
      el('div', 'value', `${disk.free_h} libres`),
      meter,
      el('div', 'sub', `${disk.used_h} utilisés sur ${disk.total_h} (${Format.percent(disk.percent)} %)`),
    );
    if (disk.folder) card.appendChild(this.#folderLine(disk.folder));
    return card;
  }

  #folderLine(folder) {
    const line = el('div', 'sub folder-line');
    line.append(el('span', 'sw'));
    if (folder.bytes_h === undefined) {
      line.append(document.createTextNode(`Dossier courant « ${folder.name} » : calcul en cours…`));
    } else {
      const share = folder.percent !== undefined ? ` · ${Format.percent(folder.percent)} % du volume` : '';
      const progress = folder.computing ? ' (mise à jour…)' : '';
      line.append(document.createTextNode(`Dossier courant « ${folder.name} » : ${folder.bytes_h} · ${folder.files} fichiers${share}${progress}`));
    }
    line.title = folder.path;
    return line;
  }
}
