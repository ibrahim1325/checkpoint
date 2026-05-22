// static/script_messages.js

document.addEventListener("DOMContentLoaded", () => {
    // ==========================
    // 1) Auto-scroll en bas
    // ==========================
    const messagesScroll = document.getElementById("messagesScroll");
    if (messagesScroll) {
        messagesScroll.scrollTop = messagesScroll.scrollHeight;
    }

    // ==========================
    // 2) DM list filter
    // ==========================
    const dmSearchInput = document.getElementById("dmSearchInput");
    if (dmSearchInput) {
        dmSearchInput.addEventListener("input", () => {
            const query = dmSearchInput.value.trim().toLowerCase();
            const items = document.querySelectorAll(".dm-list .dm-item");

            items.forEach((item) => {
                const name = (item.dataset.name || "").toLowerCase();
                const match = !query || name.includes(query);
                item.classList.toggle("hidden", !match);
            });
        });
    }

    // ==========================
    // 3) Shared refs (form + inputs)
    // ==========================
    const messageForm  = document.querySelector(".message-input-bar");
    const messageInput = document.getElementById("chatMessageInput");
    const fileInput    = document.getElementById("messageFileInput");
    let currentObjectUrl = null;

    // ==========================
// 4) Plus button (upload + preview)
// ==========================
const plusBtn          = document.querySelector(".message-input-plus-btn");
const previewContainer = document.getElementById("uploadPreviewContainer");
const previewThumb     = document.getElementById("uploadPreviewThumb");
const previewName      = document.getElementById("uploadPreviewName");
const previewDeleteBtn = document.getElementById("uploadPreviewDelete");

// 2 MB file size limit
const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2 MB

if (plusBtn && messageForm && fileInput) {
    // avoid the + button being focusable with keyboard (so Enter doesn't trigger it)
    plusBtn.setAttribute("tabindex", "-1");

    plusBtn.addEventListener("click", (e) => {
        e.preventDefault();
        fileInput.click();
    });

    // After file selection, show preview + validate size and refocus message input
    fileInput.addEventListener("change", () => {
        if (!previewContainer || !previewName || !previewThumb) return;

        // Cleanup previous preview URL if any
        if (currentObjectUrl) {
            URL.revokeObjectURL(currentObjectUrl);
            currentObjectUrl = null;
        }

        if (fileInput.files && fileInput.files.length > 0) {
            const file = fileInput.files[0];

            // Size check (2 MB max)
            if (file.size > MAX_FILE_SIZE) {
                alert("File is too large. Maximum allowed size is 2 MB.");
                fileInput.value = "";
                previewContainer.classList.add("hidden");
                previewName.textContent = "";
                previewThumb.style.backgroundImage = "none";
                previewThumb.classList.remove("upload-thumb-has-image");

                if (messageInput) {
                    messageInput.focus();
                }
                return;
            }

            // Filename
            previewName.textContent = file.name;

            // If image -> show thumbnail
            if (file.type && file.type.startsWith("image/")) {
                currentObjectUrl = URL.createObjectURL(file);
                previewThumb.style.backgroundImage = `url("${currentObjectUrl}")`;
                previewThumb.classList.add("upload-thumb-has-image");
            } else {
                previewThumb.style.backgroundImage = "none";
                previewThumb.classList.remove("upload-thumb-has-image");
            }

            previewContainer.classList.remove("hidden");
        } else {
            previewContainer.classList.add("hidden");
            previewName.textContent = "";
            previewThumb.style.backgroundImage = "none";
            previewThumb.classList.remove("upload-thumb-has-image");
        }

        // Refocus text input after file selection
        if (messageInput) {
            messageInput.focus();
            const len = messageInput.value.length;
            messageInput.selectionStart = messageInput.selectionEnd = len;
        }
    });

    // Block Enter on the hidden file input (avoid reopening file picker)
    fileInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            if (messageInput) {
                messageInput.focus();
            }
        }
    });

    if (previewDeleteBtn) {
        previewDeleteBtn.addEventListener("click", (e) => {
            e.preventDefault();

            if (currentObjectUrl) {
                URL.revokeObjectURL(currentObjectUrl);
                currentObjectUrl = null;
            }

            fileInput.value = "";
            previewContainer.classList.add("hidden");
            previewName.textContent = "";
            previewThumb.style.backgroundImage = "none";
            previewThumb.classList.remove("upload-thumb-has-image");

            if (messageInput) {
                messageInput.focus();
            }
        });
    }
}

    // ==========================
    // 5) Emoji picker (Google-like)
    // ==========================
    const emojiBtn    = document.querySelector(".message-input-icon-btn");
    const emojiPicker = document.getElementById("emojiPicker");

    if (emojiBtn && emojiPicker && messageInput) {
        emojiBtn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            emojiPicker.classList.toggle("hidden");
        });

        emojiPicker.addEventListener("click", (e) => {
            e.stopPropagation();
        });

        emojiPicker.addEventListener("emoji-click", (event) => {
            const emoji = event.detail.unicode;
            const start = messageInput.selectionStart ?? messageInput.value.length;
            const end   = messageInput.selectionEnd   ?? messageInput.value.length;
            const text  = messageInput.value;

            messageInput.value =
                text.slice(0, start) + emoji + text.slice(end);

            const newPos = start + emoji.length;
            messageInput.focus();
            messageInput.selectionStart = messageInput.selectionEnd = newPos;
        });

        document.addEventListener("click", () => {
            emojiPicker.classList.add("hidden");
        });
    }

    // ==========================
    // 6) Enter to send
    // ==========================
    if (messageForm && messageInput) {
        messageInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.stopPropagation();

                const text    = messageInput.value.trim();
                const hasText = text !== "";
                const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;

                if (hasText || hasFile) {
                    messageForm.submit();
                }
            }
        });

        // Safety: prevent submit if absolutely nothing (Send button)
        messageForm.addEventListener("submit", (e) => {
            const text    = messageInput ? messageInput.value.trim() : "";
            const hasText = text !== "";
            const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;

            if (!hasText && !hasFile) {
                e.preventDefault();
                // Optional: toast / error later
            }
        });
    }

    // ==========================
    // 7) Three-dots menu per message
    // ==========================
    const menuToggles = document.querySelectorAll(".message-menu-toggle");
    const menus       = document.querySelectorAll(".message-menu");

    function closeAllMenus() {
        menus.forEach(menu => menu.classList.add("hidden"));
        menuToggles.forEach(btn => btn.setAttribute("aria-expanded", "false"));
    }

    menuToggles.forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const actions = btn.closest(".message-actions");
            if (!actions) return;
            const menu = actions.querySelector(".message-menu");
            if (!menu) return;

            const isOpen = !menu.classList.contains("hidden");

            closeAllMenus();

            if (!isOpen) {
                menu.classList.remove("hidden");
                btn.setAttribute("aria-expanded", "true");
            }
        });
    });

    document.addEventListener("click", () => {
        closeAllMenus();
    });

    // ==========================
    // 8) Inline edit (Discord-like)
    // ==========================
    const editButtons = document.querySelectorAll(".message-edit-btn");

    editButtons.forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();

            const msgRow  = btn.closest(".message-row");
            const actions = btn.closest(".message-actions");
            if (!msgRow || !actions) return;

            const content = msgRow.querySelector(".message-content");
            const bubble  = content?.querySelector(".message-bubble");
            const menu    = actions.querySelector(".message-menu");
            if (!content || !bubble || !menu) return;

            const editUrl = actions.dataset.editUrl;
            if (!editUrl) return;

            const originalText = bubble.textContent.trim();

            if (msgRow.classList.contains("editing")) return;
            msgRow.classList.add("editing");

            menu.classList.add("hidden");

            const form = document.createElement("form");
            form.method = "POST";
            form.action = editUrl;
            form.className = "inline-edit-form";

            const input = document.createElement("input");
            input.type  = "text";
            input.name  = "new_text";
            input.className = "inline-edit-input";
            input.value = originalText;

            form.appendChild(input);
            content.replaceChild(form, bubble);

            const helper = document.createElement("div");
            helper.className = "message-edit-helper";
            helper.innerHTML = `
                Escape to <a href="#" class="edit-cancel-link">cancel</a> ·
                Enter to <a href="#" class="edit-save-link">save</a>
            `;
            content.appendChild(helper);

            const cancelLink = helper.querySelector(".edit-cancel-link");
            const saveLink   = helper.querySelector(".edit-save-link");

            function cancelEdit() {
                content.replaceChild(bubble, form);
                helper.remove();
                msgRow.classList.remove("editing");
            }

            if (cancelLink) {
                cancelLink.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    cancelEdit();
                });
            }

            if (saveLink) {
                saveLink.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    const value = input.value.trim();
                    if (value === "") {
                        cancelEdit();
                        return;
                    }
                    form.submit();
                });
            }

            input.focus();
            input.setSelectionRange(input.value.length, input.value.length);

            input.addEventListener("keydown", (ev) => {
                if (ev.key === "Escape") {
                    ev.preventDefault();
                    cancelEdit();
                } else if (ev.key === "Enter" && !ev.shiftKey) {
                    const value = input.value.trim();
                    if (value === "") {
                        ev.preventDefault();
                        cancelEdit();
                        return;
                    }
                    // form.submit() as normal
                }
            });
        });
    });
});
