// ================================
// WEEK SELECTOR — MINI CALENDAR
// ================================

// Lundi de la semaine actuelle (stocké quand l'utilisateur clique)
let currentWeekMonday = null;

// Formatage des jours
function updateWeekHeaders(mondayDate) {
    const headers = document.querySelectorAll(".day-header");
    if (!headers.length) return;

    for (let i = 0; i < headers.length; i++) {
        const d = new Date(mondayDate);
        d.setDate(d.getDate() + i);

        const weekday = d.toLocaleDateString("en-US", { weekday: "short" });
        const dayMonth = d.toLocaleDateString("en-US", { day: "numeric" });

        headers[i].textContent = `${weekday} ${dayMonth}`;
    }
}

function getMonday(d) {
    const date = new Date(d);
    const day = (date.getDay() + 6) % 7;
    date.setDate(date.getDate() - day);
    return date;
}

// ================================
// INITIALISATION DOM — UN SEUL LISTENER
// ================================
window.addEventListener("DOMContentLoaded", () => {

    // ==========================================
    // PLANNING — EDIT MODE, POPUPS, SAVE, LOAD
    // (déclaré ici pour être hoisté et utilisable partout)
    // ==========================================
    const cells = document.querySelectorAll(".calendar-cell");
    const editButton = document.querySelector(".add-button");
    let editMode = false;

    const isUnavailable = txt => ["indisponible", "unavailable"].includes(txt.trim().toLowerCase());
    const isAvailable = txt => ["disponible", "available"].includes(txt.trim().toLowerCase());

    // On le déclare ici pour pouvoir l'appeler depuis le listener weekChange
    function loadSchedule() {
        if (!currentWeekMonday) return; // sécurité

        fetch(`/api/planning?week=${encodeURIComponent(currentWeekMonday)}`)
            .then(r => r.json())
            .then(payload => {
                const items = payload.items || [];
                const cells = document.querySelectorAll(".calendar-cell");

                // Clear grid BEFORE applying DB values
                cells.forEach(c => {
                    c.textContent = "";
                    c.classList.remove("available", "unavailable");
                });

                items.forEach(it => {
                    const cell = cells[it.cell_id];
                    if (!cell) return;

                    cell.textContent = it.content || "";

                    if (it.state === "unavailable") {
                        cell.classList.add("unavailable");
                    } else if (cell.textContent.length) {
                        cell.classList.add("available");
                    }
                });
            });
    }

    function saveSchedule() {
        if (!currentWeekMonday) return; // sécurité

        const data = [];
        document.querySelectorAll(".calendar-cell").forEach((cell, index) => {
            data.push({
                cell_id: index,
                content: cell.textContent.trim(),
                state: cell.classList.contains("unavailable") ? "unavailable" : "available"
            });
        });

        fetch("/api/planning", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                week: currentWeekMonday,
                items: data
            })
        });
    }

    // ==========================================
    // MINI CALENDAR LOGIC
    // ==========================================
    const cal = document.querySelector(".mini-calendar");
    if (cal) {
        const monthLabel = cal.querySelector(".cal-month");
        const grid = cal.querySelector(".cal-grid");
        const prevBtn = cal.querySelector(".prev-month");
        const nextBtn = cal.querySelector(".next-month");

        let current = new Date();

        const monthFormatter = new Intl.DateTimeFormat("en-US", {
            month: "long",
            year: "numeric",
        });

        function buildMonth(dateToShow) {
            grid.querySelectorAll(".day").forEach(n => n.remove());

            const y = dateToShow.getFullYear();
            const m = dateToShow.getMonth();

            monthLabel.textContent = monthFormatter.format(dateToShow);

            const first = new Date(y, m, 1);
            const last = new Date(y, m + 1, 0);

            let offset = (first.getDay() + 6) % 7;

            // En-têtes (L M M J V S D) sont déjà dans le HTML

            for (let i = 0; i < offset; i++) {
                const empty = document.createElement("div");
                empty.classList.add("day", "empty");
                grid.appendChild(empty);
            }

            for (let d = 1; d <= last.getDate(); d++) {
                const date = new Date(y, m, d);
                const div = document.createElement("div");

                div.classList.add("day");
                div.textContent = d;

                // 🔥 données nécessaires
                div.dataset.day = d;
                div.dataset.month = m;
                div.dataset.year = y;
                div.dataset.date = date.toISOString(); // 🔥 obligatoire pour le hover

                div.addEventListener("click", () => {
                    selectWeek(date);
                    highlightWeek(date);
                });

                grid.appendChild(div);
            }
        }

        function clearSelection() {
            grid.querySelectorAll(".day.selected").forEach(d =>
                d.classList.remove("selected")
            );
        }

        //  VERSION CORRIGÉE : on utilise toujours "YYYY-MM-DD" comme clé de semaine
        function selectWeek(date) {
            clearSelection();

            const monday = getMonday(date);

            // Clé de semaine canonique (monday) : "YYYY-MM-DD"
            const weekKey = monday.toISOString().split("T")[0];
            currentWeekMonday = weekKey;

            updateWeekHeaders(monday);

            highlightWeek(date);

            grid.querySelectorAll(".day").forEach(cell => {
                if (!cell.dataset.date) return;

                const cellDate = new Date(cell.dataset.date);
                const diff = (cellDate - monday) / (1000 * 3600 * 24);

                if (diff >= 0 && diff < 7) cell.classList.add("selected");
            });

            // On émet aussi la clé "YYYY-MM-DD"
            document.dispatchEvent(new CustomEvent("weekChange", {
                detail: { monday: weekKey }
            }));
        }

        // On écoute weekChange AVANT d'appeler selectWeek()
        //  VERSION CORRIGÉE : on ne remet plus un ISO complet, on garde "YYYY-MM-DD"
        document.addEventListener("weekChange", e => {
            currentWeekMonday = e.detail.monday;
            loadSchedule();
        });

        prevBtn.addEventListener("click", () => {
            current.setMonth(current.getMonth() - 1);
            buildMonth(current);
        });

        nextBtn.addEventListener("click", () => {
            current.setMonth(current.getMonth() + 1);
            buildMonth(current);
        });

        buildMonth(current);
        selectWeek(new Date());   // choisit la semaine courante
        loadSchedule();           // 🔥 force le chargement du planning au 1er affichage


        // =========================
        // HOVER : highlight toute la semaine
        // =========================
        grid.addEventListener("mouseover", (e) => {
            const cell = e.target.closest(".day");
            if (!cell || !cell.dataset.date) return;

            highlightHoverWeek(new Date(cell.dataset.date));
        });

        grid.addEventListener("mouseout", () => {
            document.querySelectorAll(".day.week-hover").forEach(d =>
                d.classList.remove("week-hover")
            );
        });
    }

    // ==========================================
    // PLANNING — EDIT POPUP + INIT CLASSES
    // ==========================================

    cells.forEach(cell => {
        const t = cell.textContent.trim();
        cell.classList.remove("available", "unavailable");

        if (isUnavailable(t)) cell.classList.add("unavailable");
        else if (isAvailable(t) || t.length) cell.classList.add("available");
    });

    function setButtonInactive() {
        editButton.classList.remove("active");
        editButton.innerHTML = `<i class="fa-solid fa-plus"></i> Add Slot`;
    }
    function setButtonActive() {
        editButton.classList.add("active");
        editButton.textContent = "Finish editing";
    }
    setButtonInactive();

    editButton.addEventListener("click", () => {
        editMode = !editMode;
        if (editMode) setButtonActive();
        else {
            setButtonInactive();
            document.querySelectorAll(".edit-popup").forEach(p => p.remove());
        }
    });

    function openEditPopup(cell) {
        document.querySelectorAll(".edit-popup").forEach(p => p.remove());

        const popup = document.createElement("div");
        popup.classList.add("edit-popup");
        popup.innerHTML = `
        <input class="edit-input" value="${cell.textContent.trim()}">

        <div class="quick-options">
            <button class="quick-btn available-btn">Available</button>
            <button class="quick-btn unavailable-btn">Unavailable</button>
        </div>

        <div class="popup-actions">
            <button class="save-btn">✔</button>
            <button class="delete-btn">✖</button>
        </div>

        <div class="error-msg" style="display:none; color:#ff5555; margin-top:6px; font-size:13px;">
            Invalid text (letters, numbers, accents only, max 30 chars)
        </div>
        `;
        document.body.appendChild(popup);

        const r = cell.getBoundingClientRect();
        popup.style.left = `${r.left + window.scrollX}px`;
        popup.style.top = `${r.top + window.scrollY - 160}px`;

        const input = popup.querySelector(".edit-input");
        const errorBox = popup.querySelector(".error-msg");

        const validFreeInput = /^[a-zA-Z0-9À-ÿ\s\-']{1,30}$/;

        function showError(msg) {
            errorBox.style.display = "block";
            errorBox.textContent = msg;

            input.classList.add("input-error");
            input.style.animation = "none";
            void input.offsetWidth;
            input.style.animation = "shake 0.25s ease";
        }

        function clearError() {
            errorBox.style.display = "none";
            input.classList.remove("input-error");
        }

        function apply(val) {
            const raw = val.trim().toLowerCase();

            if (raw === "") {
                showError("This field cannot be empty.");
                return;
            }

            if (
                !isAvailable(raw) &&
                !isUnavailable(raw) &&
                !validFreeInput.test(raw)
            ) {
                showError("Invalid text (letters, numbers, accents only, max 30 chars)");
                return;
            }

            clearError();
            cell.classList.remove("available", "unavailable");

            if (isUnavailable(raw)) {
                cell.textContent = "Unavailable";
                cell.classList.add("unavailable");
            } else if (isAvailable(raw)) {
                cell.textContent = "Available";
                cell.classList.add("available");
            } else {
                cell.textContent = val.trim();
                cell.classList.add("available");
            }

            popup.remove();
            saveSchedule();
        }

        popup.querySelector(".save-btn").onclick = () => apply(input.value);
        popup.querySelector(".delete-btn").onclick = () => {
            cell.textContent = "";
            cell.classList.remove("available", "unavailable");
            popup.remove();
            saveSchedule();
        };

        popup.querySelector(".available-btn").onclick = () => apply("Available");
        popup.querySelector(".unavailable-btn").onclick = () => apply("Unavailable");
    }

    cells.forEach(cell => {
        cell.addEventListener("click", e => {
            if (!editMode) return;
            e.stopPropagation();
            openEditPopup(cell);
        });
    });
    // ==============================
    // PRIVACY MODAL
    // ==============================
    const openPrivacyBtn   = document.getElementById("openPrivacy");
    const privacyBackdrop  = document.getElementById("privacyBackdrop");
    const privacyModal     = document.getElementById("privacyModal");
    const closePrivacyBtn  = document.getElementById("closePrivacy");
    const cancelPrivacyBtn = document.getElementById("cancelPrivacy");
    const savePrivacyBtn   = document.getElementById("savePrivacy");
    const customBlock      = document.getElementById("privacyCustomBlock");
    const friendListDiv    = document.getElementById("privacyFriendList");

    function mapServerModeToUi(mode) {
        // mode backend: "friends", "everyone", "none", "custom"
        if (mode === "none") return "private";
        if (mode === "custom") return "custom";
        // "friends" ou "everyone" => on coche "All friends"
        return "friends";
    }

    function mapUiModeToServer(uiMode) {
        // radio values: "friends", "custom", "private"
        if (uiMode === "private") return "none";
        if (uiMode === "custom")  return "custom";
        return "friends";
    }

    function updateCustomVisibility() {
        if (!customBlock) return;
        const selected = document.querySelector('input[name="schedulePrivacy"]:checked');
        if (!selected) return;
        customBlock.style.display = (selected.value === "custom") ? "block" : "none";
    }

    function buildFriendList(friends, allowedSet, uiMode) {
        if (!friendListDiv) return;
        friendListDiv.innerHTML = "";

        if (!friends.length) {
            const p = document.createElement("p");
            p.className = "privacy-helper";
            p.textContent = "You don't have any friends yet.";
            friendListDiv.appendChild(p);
            return;
        }

        friends.forEach(friend => {
            const label = document.createElement("label");
            label.className = "privacy-friend-item";

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = friend.username;

            // cocher ceux autorisés quand on est en mode custom
            if (uiMode === "custom" && allowedSet.has(friend.username)) {
                checkbox.checked = true;
            }

            const avatar = document.createElement("img");
            avatar.className = "privacy-friend-avatar";
            avatar.alt = friend.username;
            if (friend.avatar_url) {
                avatar.src = friend.avatar_url;
            } else {
                // petit fallback neutre
                avatar.src = "https://via.placeholder.com/40x40?text=?";
            }

            const span = document.createElement("span");
            span.textContent = friend.username;

            label.appendChild(checkbox);
            label.appendChild(avatar);
            label.appendChild(span);

            friendListDiv.appendChild(label);
        });
    }

    async function openPrivacyModal() {
        if (!privacyModal || !privacyBackdrop) return;

        privacyBackdrop.hidden = false;
        privacyModal.hidden = false;

        try {
            // On récupère en parallèle: liste d'amis + réglages actuels
            const [friendsResp, privacyResp] = await Promise.all([
                fetch("/api/friends"),
                fetch("/api/schedule/privacy")
            ]);

            const friendsData  = await friendsResp.json();
            const privacyData  = await privacyResp.json();

            const friends      = friendsData.friends || [];
            const modeServer   = privacyData.mode || "friends";
            const allowedList  = privacyData.allowed_friends || [];
            const allowedSet   = new Set(allowedList);
            const uiMode       = mapServerModeToUi(modeServer);

            // cocher le bon radio
            const radio = document.querySelector(
                `input[name="schedulePrivacy"][value="${uiMode}"]`
            );
            if (radio) {
                radio.checked = true;
            }

            // construire la liste d'amis
            buildFriendList(friends, allowedSet, uiMode);

            updateCustomVisibility();
        } catch (err) {
            console.error("Error loading privacy settings:", err);
        }
    }

    function hidePrivacyModal() {
        if (!privacyModal || !privacyBackdrop) return;
        privacyBackdrop.hidden = true;
        privacyModal.hidden = true;
    }

    if (openPrivacyBtn)   openPrivacyBtn.addEventListener("click", openPrivacyModal);
    if (closePrivacyBtn)  closePrivacyBtn.addEventListener("click", hidePrivacyModal);
    if (cancelPrivacyBtn) cancelPrivacyBtn.addEventListener("click", hidePrivacyModal);
    if (privacyBackdrop) {
        privacyBackdrop.addEventListener("click", (e) => {
            if (e.target === privacyBackdrop) hidePrivacyModal();
        });
    }

    // quand on change de mode => on affiche / cache le bloc custom
    document.querySelectorAll('input[name="schedulePrivacy"]').forEach(radio => {
        radio.addEventListener("change", updateCustomVisibility);
    });

    if (savePrivacyBtn) {
        savePrivacyBtn.addEventListener("click", async () => {
            const selected = document.querySelector('input[name="schedulePrivacy"]:checked');
            if (!selected) return;

            const uiMode = selected.value;
            const mode   = mapUiModeToServer(uiMode);

            let allowed = [];
            if (uiMode === "custom" && friendListDiv) {
                const checks = friendListDiv.querySelectorAll('input[type="checkbox"]:checked');
                allowed = Array.from(checks).map(c => c.value);
            }

            try {
                await fetch("/api/schedule/privacy", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        mode: mode,
                        allowed_friends: allowed
                    })
                });
            } catch (err) {
                console.error("Error saving privacy settings:", err);
            }

            hidePrivacyModal();
        });
    }

});

// ================================
// HIGHLIGHT HELPERS (en dehors du DOMContentLoaded)
// ================================
function highlightWeek(selectedDate) {
    const days = document.querySelectorAll('.mini-calendar .day');

    days.forEach(d => d.classList.remove('week-highlight', 'week-selected'));

    if (!selectedDate) return;

    const sel = new Date(selectedDate);
    const weekday = sel.getDay(); // 0=Sun, 1=Mon...

    const monday = new Date(sel);
    monday.setDate(sel.getDate() - ((weekday + 6) % 7));

    for (let i = 0; i < 7; i++) {
        const day = new Date(monday);
        day.setDate(monday.getDate() + i);

        const match = [...days].find(d =>
            Number(d.textContent) === day.getDate() &&
            d.dataset.month == day.getMonth() &&
            d.dataset.year == day.getFullYear()
        );

        if (match) {
            match.classList.add("week-highlight");
            if (day.toDateString() === sel.toDateString()) {
                match.classList.add("week-selected");
            }
        }
    }
}

function highlightHoverWeek(date) {
    document.querySelectorAll(".day.week-hover").forEach(d =>
        d.classList.remove("week-hover")
    );

    const monday = getMonday(date);

    const days = document.querySelectorAll(".mini-calendar .day");
    for (let i = 0; i < 7; i++) {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);

        const match = [...days].find(x =>
            Number(x.textContent) === d.getDate() &&
            x.dataset.month == d.getMonth() &&
            x.dataset.year == d.getFullYear()
        );

        if (match) match.classList.add("week-hover");
    }
}
