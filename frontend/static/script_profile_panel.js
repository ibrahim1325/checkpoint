// script_profile_panel.js

// ------- Références -------
const openBtn = document.getElementById('openProfile');
const panel = document.getElementById('profilePanel');
const backdrop = document.getElementById('profileBackdrop');
const closeBtn = document.getElementById('ppClose');

// Elements statut (mini-profil + panel)
const meBtn = document.getElementById('openProfile');
const meStatusDot = document.getElementById('meStatusDot');
const meStatusText = document.getElementById('meStatusText');
const ppStatusDot = document.getElementById('ppStatusDot');
const ppStatusText = document.getElementById('ppStatusText');

// ------- Helpers -------

// Positionne le panneau pour qu'il RECOUVRE le mini-profil
function positionPanelFromButton() {
    if (!openBtn || !panel) return;

    // on rend visible (sans animation) le temps de mesurer
    panel.hidden = false;
    panel.classList.remove('is-open');
    panel.style.visibility = 'hidden';

    const r = openBtn.getBoundingClientRect();

    // même gauche, bas du panel aligné sur le bas du mini-profil
    const desiredLeft = r.left;
    const desiredTop = r.top + r.height - panel.offsetHeight;

    const margin = 16;
    const left = Math.max(
        margin,
        Math.min(desiredLeft, window.innerWidth - panel.offsetWidth - margin)
    );
    const top = Math.max(
        margin,
        Math.min(desiredTop, window.innerHeight - panel.offsetHeight - margin)
    );

    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;

    // prêt pour l'animation
    panel.style.visibility = 'visible';
}

// Met à jour les indicateurs de statut (mini-profil + panel)
function updateStatusUI(status) {
    const map = {
        online: { cls: 'dot-online', text: 'Online' },
        idle: { cls: 'dot-idle', text: 'Idle' },
        dnd: { cls: 'dot-dnd', text: 'Do Not Disturb' },
        invisible: { cls: 'dot-invisible', text: 'Invisible' },
    };
    const info = map[status] || map.online;

    if (ppStatusDot) ppStatusDot.className = `dot ${info.cls}`;
    if (ppStatusText) ppStatusText.textContent = info.text;

    if (meStatusDot) meStatusDot.className = `dot ${info.cls}`;

    const ppAvatarDot = document.getElementById('ppAvatarDot');
    if (ppAvatarDot) ppAvatarDot.className = `pp-avatar-dot ${info.cls}`;

    if (meStatusText) meStatusText.textContent = info.text;

    if (meBtn) {
        meBtn.classList.remove('status-online', 'status-idle', 'status-dnd', 'status-invisible');
        meBtn.classList.add(`status-${status}`);
    }
}

// Normalise un label texte ("Do Not Disturb") vers une valeur de statut ('dnd')
function normalizeStatusLabel(label) {
    const t = (label || '').trim().toLowerCase().replace(/\s+/g, '');
    if (!t) return 'online';
    if (t === 'donotdisturb') return 'dnd';
    if (t === 'online') return 'online';
    if (t === 'idle') return 'idle';
    if (t === 'dnd') return 'dnd';
    if (t === 'invisible') return 'invisible';
    return 'online';
}

// Envoie le statut au backend pour persistance
function persistStatus(status) {
    fetch('/set_status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
    }).catch(() => {
        // on ignore les erreurs réseau pour ne pas bloquer l'UI
    });
}

// ------- Open / Close -------
function openPanel() {
    positionPanelFromButton();

    requestAnimationFrame(() => {
        if (backdrop) backdrop.hidden = false;
        if (panel) panel.classList.add('is-open');
    });
}

function closePanel() {
    if (!panel || !backdrop) return;
    panel.classList.remove('is-open');
    setTimeout(() => {
        backdrop.hidden = true;
        panel.hidden = true;
    }, 230); // durée > à la transition CSS (.22s)
}

if (openBtn) openBtn.addEventListener('click', openPanel);
if (backdrop) backdrop.addEventListener('click', closePanel);
if (closeBtn) closeBtn.addEventListener('click', closePanel);
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePanel();
});

// ------- Changement de statut (UI + POST + fermeture) -------
document.querySelectorAll('.pp-status').forEach((btn) => {
    btn.addEventListener('click', () => {
        const status = btn.dataset.status; // online / idle / dnd / invisible
        if (!status) return;

        // bouton actif
        document.querySelectorAll('.pp-status').forEach((b) =>
            b.classList.remove('is-current')
        );
        btn.classList.add('is-current');

        // UI immédiate
        updateStatusUI(status);

        // Persistance côté serveur
        persistStatus(status);

        // Fermeture du panel
        closePanel();
    });
});

// ------- Sync initial (statut rendu côté serveur) -------
(() => {
    if (!meStatusText && !ppStatusText) return;

    const labelSource = (meStatusText && meStatusText.textContent) ||
                        (ppStatusText && ppStatusText.textContent) ||
                        'Online';

    const initialStatus = normalizeStatusLabel(labelSource);
    updateStatusUI(initialStatus);
})();
