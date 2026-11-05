/* Page d'erreur : « Page précédente » n'a de sens que s'il y a un historique. */
(() => {
  const back = document.getElementById('err-back');
  if (!back) return;
  if (history.length < 2) back.hidden = true;
  else back.addEventListener('click', () => history.back());
})();
