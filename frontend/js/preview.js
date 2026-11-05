(() => {
  const frame = document.getElementById('pv');
  document.getElementById('reload').addEventListener('click', () => { frame.src = frame.src; });
})();
