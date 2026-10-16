/* Both picker and drop use the same PDF validation and multipart form. */
(() => {
  const form = document.getElementById('upload-form');
  if (!form) return;
  const input = document.getElementById('upload-file');
  const zone = document.getElementById('drop-zone');
  const button = document.getElementById('choose-file');
  const status = document.getElementById('upload-status');
  let submitting = false;
  button.hidden = false;
  input.classList.add('visually-hidden');
  // Keep the real file input focusable for keyboard and native validation.
  button.addEventListener('click', () => input.click());
  function accept(files, dropped) {
    if (submitting) return;
    if (files.length !== 1 || !/\.pdf$/i.test(files[0].name)) {
      status.textContent = 'PDFファイルを1つ選択してください。';
      input.value = '';
      return;
    }
    if (files[0].size > 20 * 1024 * 1024) {
      status.textContent = '20 MB以内のPDFを選択してください。';
      input.value = '';
      return;
    }
    if (dropped) input.files = files;
    status.textContent = `${files[0].name} をアップロードしています…`;
    form.requestSubmit();
  }
  input.addEventListener('change', () => { if (input.files.length) accept(input.files, false); });
  zone.addEventListener('dragover', event => {
    event.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', event => {
    if (!zone.contains(event.relatedTarget)) zone.classList.remove('drag-over');
  });
  zone.addEventListener('drop', event => {
    event.preventDefault();
    zone.classList.remove('drag-over');
    accept(event.dataTransfer.files, true);
  });
  // Dropping outside the zone must not navigate away from the application.
  document.addEventListener('dragover', event => event.preventDefault());
  document.addEventListener('drop', event => event.preventDefault());
  form.addEventListener('submit', () => {
    submitting = true;
    button.disabled = true;
    zone.setAttribute('aria-busy', 'true');
  });
})();
