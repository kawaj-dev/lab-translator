/* Source-only zoom. Translation values remain server-owned. */
(() => {
  const content = document.getElementById('source-content');
  const viewport = document.getElementById('source-viewport');
  if (!content || !viewport) return;
  let scale = 1;
  function apply(next) {
    scale = Math.max(0.5, Math.min(3, next));
    content.style.width = `${scale * 100}%`;
    document.getElementById('zoom-label').textContent = `${Math.round(scale * 100)}%`;
    const pdf = content.querySelector('object');
    if (pdf) pdf.style.height = `${viewport.clientHeight * scale}px`;
    const paper = content.querySelector('.source-report');
    if (paper) paper.style.fontSize = `${scale * 100}%`;
  }
  document.getElementById('zoom-in').addEventListener('click', () => apply(scale * 1.25));
  document.getElementById('zoom-out').addEventListener('click', () => apply(scale / 1.25));
  document.getElementById('zoom-fit').addEventListener('click', () => {
    apply(1);
    viewport.scrollTo(0, 0);
  });
})();
