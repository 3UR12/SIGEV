(() => {
  function updateTotal() {
    const body = document.querySelector('#sale-lines tbody');
    const totalElement = document.querySelector('#sale-total');
    if (!body || !totalElement) return;
    let total = 0;
    body.querySelectorAll('tr').forEach((row) => {
      const option = row.querySelector('select').selectedOptions[0];
      const quantity = Number(row.querySelector('input[name="cantidad"]').value || 0);
      const price = Number(option?.dataset.price || 0);
      total += price * quantity;
      row.querySelector('.line-stock').textContent = option?.dataset.stock ?? '—';
      row.querySelector('.line-price').textContent = option ? `B/. ${(price / 100).toFixed(2)}` : '—';
    });
    totalElement.textContent = `B/. ${(total / 100).toFixed(2)}`;
  }

  function addLine() {
    const template = document.querySelector('#line-template');
    const body = document.querySelector('#sale-lines tbody');
    if (!template || !body) return;
    const fragment = template.content.cloneNode(true);
    body.appendChild(fragment);
    updateTotal();
  }

  function initializeSale() {
    const body = document.querySelector('#sale-lines tbody');
    if (body && !body.querySelector('tr')) addLine();
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('#add-line')) addLine();
    const removeButton = event.target.closest('.remove-line');
    if (removeButton) {
      removeButton.closest('tr')?.remove();
      updateTotal();
    }
  });
  document.addEventListener('input', (event) => {
    if (event.target.closest('#sale-lines')) updateTotal();
  });
  document.addEventListener('change', (event) => {
    if (event.target.closest('#sale-lines')) updateTotal();
  });
  document.addEventListener('sigev:navigation', initializeSale);
  initializeSale();
})();
