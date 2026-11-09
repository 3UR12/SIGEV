(() => {
  document.querySelectorAll('.message-close').forEach((button) => {
    button.addEventListener('click', () => button.closest('.message')?.remove());
  });

  document.querySelectorAll('[data-auto-dismiss]').forEach((message) => {
    const delay = Number(message.dataset.autoDismiss) || 6000;
    window.setTimeout(() => message.remove(), delay);
  });
})();
