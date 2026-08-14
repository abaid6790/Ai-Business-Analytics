(function () {
    const STORAGE_KEY = "ai-analytics-theme";

    function getPreferredTheme() {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) return stored;
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-bs-theme", theme);
        const darkIcon = document.getElementById("themeIconDark");
        const lightIcon = document.getElementById("themeIconLight");
        if (darkIcon && lightIcon) {
            darkIcon.classList.toggle("d-none", theme === "dark");
            lightIcon.classList.toggle("d-none", theme === "light");
        }
    }

    // Apply immediately to avoid a flash of the wrong theme.
    applyTheme(getPreferredTheme());

    document.addEventListener("DOMContentLoaded", function () {
        applyTheme(getPreferredTheme());

        const toggleBtn = document.getElementById("themeToggle");
        if (toggleBtn) {
            toggleBtn.addEventListener("click", function () {
                const current = document.documentElement.getAttribute("data-bs-theme");
                const next = current === "dark" ? "light" : "dark";
                localStorage.setItem(STORAGE_KEY, next);
                applyTheme(next);
            });
        }
    });
})();
