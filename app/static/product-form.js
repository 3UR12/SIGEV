(() => {
  document.addEventListener('keydown', (event) => {
    const form = event.target.closest('form[data-prevent-enter-submit]');
    if (!form) return;
    const input = event.target;
    const isDataInput = input.tagName === 'INPUT' && !['checkbox', 'radio', 'submit', 'reset', 'button', 'hidden'].includes(input.type);
    if (event.key !== 'Enter' || !isDataInput) return;
    event.preventDefault();
    const controls = [...form.elements].filter((element) => !element.disabled && element.type !== 'hidden');
    const next = controls[controls.indexOf(event.target) + 1];
    next?.focus();
  });
})();
