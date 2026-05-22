document.addEventListener("DOMContentLoaded", () => {
    const friend = document.body.dataset.friend;
    const week1 = document.body.dataset.week1;
    const week2 = document.body.dataset.week2;

    if (!friend) return;

    const isUnavailable = txt =>
        ["indisponible", "unavailable"].includes(txt.trim().toLowerCase());
    const isAvailable = txt =>
        ["disponible", "available"].includes(txt.trim().toLowerCase());

    function fillGrid(grid, items) {
        const cells = grid.querySelectorAll(".calendar-cell");

        // reset
        cells.forEach(c => {
            c.textContent = "";
            c.classList.remove("available", "unavailable");
        });

        items.forEach(it => {
            const cell = cells[it.cell_id];
            if (!cell) return;

            const content = (it.content || "").trim();
            cell.textContent = content;

            if (it.state === "unavailable" || isUnavailable(content)) {
                cell.classList.add("unavailable");
            } else if (content.length || isAvailable(content)) {
                cell.classList.add("available");
            }
        });
    }

    function loadWeek(weekKey, grid) {
        if (!weekKey || !grid) return;

        fetch(`/api/planning?week=${encodeURIComponent(weekKey)}&user=${encodeURIComponent(friend)}`)
            .then(r => r.json())
            .then(payload => {
                const items = payload.items || [];
                fillGrid(grid, items);
            })
            .catch(err => console.error("Error loading friend planning:", err));
    }

    // Current & next week grids
    const grids = document.querySelectorAll(".calendar-grid.friend-grid");
    grids.forEach(grid => {
        const wk = grid.dataset.week;
        loadWeek(wk, grid);
    });

    // Désactiver toute tentative d'édition
    document.querySelectorAll(".calendar-cell").forEach(cell => {
        cell.addEventListener("click", e => {
            e.stopPropagation();
        });
    });
});
