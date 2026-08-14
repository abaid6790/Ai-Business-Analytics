document.addEventListener("DOMContentLoaded", function () {
    // --- Password show/hide toggle ---
    document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const wrapper = btn.closest(".password-field-wrapper");
            const input = wrapper.querySelector("input");
            const icon = btn.querySelector("i");
            const isHidden = input.type === "password";

            input.type = isHidden ? "text" : "password";
            icon.classList.toggle("bi-eye-fill", !isHidden);
            icon.classList.toggle("bi-eye-slash-fill", isHidden);
            btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
        });
    });

    // --- Sidebar toggle (mobile) ---
    const sidebarToggle = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("appSidebar");
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener("click", function () {
            sidebar.classList.toggle("open");
        });
    }

    // --- Bootstrap toast auto-init ---
    document.querySelectorAll(".toast").forEach(function (el) {
        new bootstrap.Toast(el).show();
    });
});
