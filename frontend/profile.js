(()=> {
  const openBtn = document.getElementById('openProfile');
  const panel   = document.getElementById('profilePanel');
  const closeBtn= document.getElementById('ppClose');
  const backdrop= document.getElementById('profileBackdrop');
  const statusDotInMe = document.querySelector('.me .status');

  function openPanel(){
    panel.hidden = false;
    backdrop.hidden = false;
    // focus le bouton fermer pour accessibilité
    closeBtn.focus();
  }
  function closePanel(){
    panel.hidden = true;
    backdrop.hidden = true;
    openBtn.focus();
  }

  // Ouverture (click & Enter/Space sur le conteneur profil)
  if (openBtn){
    openBtn.addEventListener('click', openPanel);
    openBtn.addEventListener('keydown', e=>{
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPanel(); }
    });
  }

  // Fermetures
  closeBtn?.addEventListener('click', closePanel);
  backdrop?.addEventListener('click', closePanel);
  document.addEventListener('keydown', e=>{
    if (!panel.hidden && e.key === 'Escape') closePanel();
  });

  // Choix de statut
  panel?.querySelectorAll('.pp-status').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const s = btn.dataset.status;
      // met à jour la couleur du point dans le bloc .me (sans toucher CSS global)
      const map = {
        online:   '#4ade80',
        idle:     '#f59e0b',
        dnd:      '#ef4444',
        invisible:'#9ca3af'
      };
      if (statusDotInMe) statusDotInMe.style.background = map[s] || '#4ade80';
      closePanel();
    });
  });

  // Déconnexion (placeholder)
  document.getElementById('ppLogout')?.addEventListener('click', ()=>{
    // Ici tu déclencheras ton vrai logout plus tard.
    alert('Déconnexion (prototype)');
    closePanel();
  });
})();
