// ================================
// Smooth Page Transition (anti-jitter)
// ================================
(function () {
  const DURATION = 150; // doit matcher le CSS
  let navLock = false;  // évite les doubles clics / doubles sorties

  document.documentElement.classList.add('js');

  // Lecture d’entrée
  window.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector('.container');
    if (!root) return;
    root.classList.remove('exit-forward', 'exit-back', 'enter');
    // double RAF pour éviter tout flash/reflow
    requestAnimationFrame(() => {
      requestAnimationFrame(() => root.classList.add('enter'));
    });
  });

  // Transition forward sur clic de lien interne
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (!a) return;

    // Cas à ignorer
    if (a.target && a.target !== '_self') return;
    if (a.hasAttribute('download')) return;

    const url = new URL(a.href, window.location.href);
    if (url.origin !== window.location.origin) return;

    // Pas de transition si on reste sur exactement la même page (même path + query + hash vide)
    const samePath = url.pathname === window.location.pathname;
    const sameQuery = url.search === window.location.search;
    if (samePath && sameQuery && (!url.hash || url.hash === '')) return;

    if (a.dataset.noTransition === 'true') return;

    // Lock pour éviter double déclenchement
    if (navLock) return;
    navLock = true;

    e.preventDefault();

    const root = document.querySelector('.container');
    if (!root) {
      window.location.href = a.href;
      return;
    }

    // Bloque les interactions pendant la sortie
    root.style.pointerEvents = 'none';
    root.classList.remove('enter', 'exit-back');
    root.classList.add('exit-forward');

    setTimeout(() => {
      window.location.href = a.href;
    }, DURATION);
  });

  // Retour depuis le cache bfcache → rejouer entrée propre
  window.addEventListener('pageshow', (event) => {
    navLock = false; // relâche le lock quand la page revient
    const root = document.querySelector('.container');
    if (!root) return;

    root.style.pointerEvents = '';
    root.classList.remove('exit-forward', 'exit-back', 'enter');

    // Si la page vient du cache, pas de “tremblement”
    requestAnimationFrame(() => {
      requestAnimationFrame(() => root.classList.add('enter'));
    });
  });

  // Bouton retour navigateur → animation back
  window.addEventListener('popstate', () => {
    const root = document.querySelector('.container');
    if (!root) return;
    root.style.pointerEvents = 'none';
    root.classList.remove('enter', 'exit-forward');
    root.classList.add('exit-back');
    setTimeout(() => {
      root.style.pointerEvents = '';
    }, DURATION);
  });
})();
