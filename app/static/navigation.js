(() => {
  const toggle = document.querySelector('.nav-toggle');
  const navigation = document.querySelector('#main-navigation');
  if (!toggle || !navigation) return;

  const mobile = window.matchMedia('(max-width: 680px)');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const modulePaths = new Set(['/', '/productos', '/entradas', '/ventas', '/inventario', '/reportes']);
  let pendingNavigation;

  function setOpen(open, returnFocus = false) {
    navigation.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    if (returnFocus) toggle.focus();
  }

  toggle.addEventListener('click', () => {
    setOpen(toggle.getAttribute('aria-expanded') !== 'true');
  });

  navigation.addEventListener('click', (event) => {
    if (mobile.matches && event.target.closest('a')) setOpen(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
      setOpen(false, true);
    }
  });

  mobile.addEventListener('change', () => setOpen(false));

  function updateCurrentModule(pathname) {
    navigation.querySelectorAll('a').forEach((link) => {
      const active = new URL(link.href).pathname === pathname;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }

  function initializeView(url) {
    document.dispatchEvent(new CustomEvent('sigev:navigation', { detail: { url } }));
    const heading = document.querySelector('.main-content h1');
    if (heading) {
      heading.setAttribute('tabindex', '-1');
      heading.focus({ preventScroll: true });
    }
  }

  async function loadModule(url, pushHistory = true) {
    if (pendingNavigation) pendingNavigation.abort();
    const controller = new AbortController();
    pendingNavigation = controller;
    const currentMain = document.querySelector('.main-content');
    currentMain?.setAttribute('aria-busy', 'true');

    try {
      const response = await fetch(url, {
        headers: { 'X-SIGEV-Navigation': 'module' },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const nextDocument = new DOMParser().parseFromString(await response.text(), 'text/html');
      const nextMain = nextDocument.querySelector('.main-content');
      if (!nextMain) throw new Error('La respuesta no contiene el módulo solicitado.');
      const targetUrl = new URL(response.url);

      const applyView = () => {
        currentMain.replaceWith(nextMain);
        document.title = nextDocument.title;
        updateCurrentModule(targetUrl.pathname);
        window.scrollTo(0, 0);
        initializeView(targetUrl.href);
      };

      if (document.startViewTransition && !reducedMotion.matches) {
        await document.startViewTransition(applyView).finished;
      } else {
        applyView();
      }

      if (pushHistory) history.pushState({ sigevModule: true }, '', targetUrl);
    } catch (error) {
      if (error.name === 'AbortError') return;
      window.location.assign(url);
    } finally {
      document.querySelector('.main-content')?.removeAttribute('aria-busy');
      if (pendingNavigation === controller) pendingNavigation = undefined;
    }
  }

  document.addEventListener('click', (event) => {
    const link = event.target.closest('.brand, .sidebar-nav a');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || !modulePaths.has(url.pathname) || url.href === location.href) return;
    event.preventDefault();
    setOpen(false);
    loadModule(url.href);
  });

  window.addEventListener('popstate', () => {
    if (modulePaths.has(location.pathname)) loadModule(location.href, false);
  });
})();
