document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("generateBtn");
    if (!btn) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const loadingEl = document.getElementById("insightsLoading");
    const errorEl = document.getElementById("insightsError");
    const resultEl = document.getElementById("insightsResult");
    const textEl = document.getElementById("insightsText");
    const factsEl = document.getElementById("insightsFacts");

    btn.addEventListener("click", function () {
        errorEl.classList.add("d-none");
        resultEl.classList.add("d-none");
        loadingEl.classList.remove("d-none");
        btn.disabled = true;

        fetch(INSIGHTS_GENERATE_URL, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
        })
            .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                loadingEl.classList.add("d-none");
                btn.disabled = false;
                if (!ok) {
                    errorEl.textContent = data.error || "Could not generate insights.";
                    errorEl.classList.remove("d-none");
                    return;
                }
                textEl.textContent = data.insights_text;
                factsEl.textContent = JSON.stringify(data.facts, null, 2);
                resultEl.classList.remove("d-none");
            })
            .catch(() => {
                loadingEl.classList.add("d-none");
                btn.disabled = false;
                errorEl.textContent = "Could not generate insights. Please try again.";
                errorEl.classList.remove("d-none");
            });
    });
});
