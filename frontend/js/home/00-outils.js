/** Page d'accueil : petits outils partagés par les fichiers de ce dossier. */
const $ = (id) => document.getElementById(id);

/** Crée un élément avec une classe et un texte (le texte est inséré comme texte, jamais comme HTML). */
const el = (tag, className = '', text = '') => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};

const formatSize = (bytes) => {
  const units = ['o', 'Ko', 'Mo', 'Go', 'To'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${unit === 0 || value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`.replace('.', ',');
};
