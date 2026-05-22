// static/script_friends.js

document.addEventListener("DOMContentLoaded", function () {
    // ===============================
    // 1) Modale "Delete friend"
    // ===============================
    const deleteButtons   = document.querySelectorAll(".delete-friend-btn");
    const backdrop        = document.getElementById("deleteModalBackdrop");
    const modal           = document.getElementById("deleteFriendModal");
    const friendNameSpan  = document.getElementById("deleteFriendName");
    const deleteForm      = document.getElementById("deleteFriendForm");
    const cancelBtn       = document.getElementById("cancelDeleteBtn");

    function openDeleteModal(friendName, actionUrl) {
        if (!modal || !backdrop || !friendNameSpan || !deleteForm) return;

        friendNameSpan.textContent = friendName;
        deleteForm.setAttribute("action", actionUrl);

        backdrop.hidden = false;
        modal.hidden = false;
        document.body.classList.add("modal-open");
    }

    function closeDeleteModal() {
        if (!modal || !backdrop) return;

        backdrop.hidden = true;
        modal.hidden = true;
        document.body.classList.remove("modal-open");
    }

    deleteButtons.forEach((btn) => {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            const friendName = this.dataset.friend;
            const parentForm = this.closest("form");
            const actionUrl  = parentForm ? parentForm.getAttribute("action") : "#";
            openDeleteModal(friendName, actionUrl);
        });
    });

    if (cancelBtn && backdrop) {
        cancelBtn.addEventListener("click", function (e) {
            e.preventDefault();
            closeDeleteModal();
        });

        backdrop.addEventListener("click", closeDeleteModal);
    }

    // ===============================
    // 2) Barre de recherche DM
    // ===============================
    const dmSearchInput = document.getElementById("dmSearchInput");
    if (dmSearchInput) {
        const dmItems = Array.from(document.querySelectorAll(".dm-list .dm-item"));

        dmSearchInput.addEventListener("input", function () {
            const q = this.value.trim().toLowerCase();

            dmItems.forEach((li) => {
                const name = (li.dataset.name || "").toLowerCase();
                li.style.display = !q || name.includes(q) ? "" : "none";
            });
        });
    }

    // ===============================
    // 3) Menu "3 points" + planning
    // ===============================
    const menuToggles = document.querySelectorAll(".friend-menu-toggle");
    const menus       = document.querySelectorAll(".friend-menu-dropdown");

    function closeAllMenus() {
        menus.forEach((menu) => menu.classList.add("hidden"));
    }

    // Ouvrir / fermer le menu quand on clique sur les 3 points
    menuToggles.forEach((toggle) => {
        toggle.addEventListener("click", (event) => {
            event.stopPropagation();

            const menu   = toggle.parentElement.querySelector(".friend-menu-dropdown");
            const isOpen = menu && !menu.classList.contains("hidden");

            closeAllMenus();

            if (menu && !isOpen) {
                menu.classList.remove("hidden");
            }
        });
    });

    // Cliquer ailleurs ferme les menus
    document.addEventListener("click", () => {
        closeAllMenus();
    });

    // Bouton "Consulter planning"
    const planningButtons = document.querySelectorAll(".view-planning-btn");

    planningButtons.forEach((btn) => {
        btn.addEventListener("click", (event) => {
            event.stopPropagation();

            const menu     = btn.closest(".friend-menu-dropdown");
            const username = menu?.dataset.friendUsername;

            if (!username) {
                console.warn("Impossible de récupérer le username pour le planning.");
                return;
            }

            const url = `/friends/${encodeURIComponent(username)}/planning`;
            window.location.href = url;
        });
    });
});
