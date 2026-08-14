document.addEventListener("DOMContentLoaded", function () {
    const forecastBtn = document.getElementById("forecastBtn");
    if (!forecastBtn) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const loadingEl = document.getElementById("forecastLoading");
    const errorEl = document.getElementById("forecastError");
    const contentEl = document.getElementById("forecastContent");
    const badgesEl = document.getElementById("forecastBadges");
    const confidenceNote = document.getElementById("confidenceNote");

    let chartInstance = null;

    const METHOD_LABELS = {
        holt_winters_seasonal: "Holt-Winters (trend + seasonality)",
        holt_linear_trend: "Holt's linear trend",
        linear_regression_fallback: "Linear trend (limited history)",
    };

    forecastBtn.addEventListener("click", function () {
        const payload = {
            date_column: document.getElementById("dateColumn").value,
            value_column: document.getElementById("valueColumn").value,
            periods: parseInt(document.getElementById("periodsInput").value, 10) || 12,
        };

        errorEl.classList.add("d-none");
        contentEl.classList.add("d-none");
        loadingEl.classList.remove("d-none");
        forecastBtn.disabled = true;

        fetch(FORECAST_GENERATE_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
            body: JSON.stringify(payload),
        })
            .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                loadingEl.classList.add("d-none");
                forecastBtn.disabled = false;
                if (!ok) {
                    errorEl.textContent = data.error || "Could not generate forecast.";
                    errorEl.classList.remove("d-none");
                    return;
                }
                renderResult(data);
            })
            .catch(() => {
                loadingEl.classList.add("d-none");
                forecastBtn.disabled = false;
                errorEl.textContent = "Could not generate forecast. Please try again.";
                errorEl.classList.remove("d-none");
            });
    });

    function renderResult(data) {
        renderBadges(data);
        renderChart(data);
        confidenceNote.textContent = `Confidence band: ${data.confidence_method}`;
        contentEl.classList.remove("d-none");
    }

    function renderBadges(data) {
        const trendIcon = {
            increasing: "bi-arrow-up-right", decreasing: "bi-arrow-down-right",
            stable: "bi-arrow-right", insufficient_data: "bi-question",
        }[data.trend.direction] || "bi-arrow-right";
        const trendColor = { increasing: "success", decreasing: "danger", stable: "secondary" }[data.trend.direction] || "secondary";

        const badges = [
            `<span class="badge text-bg-light border"><i class="bi bi-cpu"></i> ${METHOD_LABELS[data.method] || data.method}</span>`,
            `<span class="badge text-bg-${trendColor}"><i class="bi ${trendIcon}"></i> Trend: ${data.trend.direction}</span>`,
        ];
        if (data.seasonality.detected) {
            badges.push(`<span class="badge text-bg-info">Seasonality detected (period: ${data.seasonality.period}, strength: ${data.seasonality.strength})</span>`);
        } else {
            badges.push(`<span class="badge text-bg-light border">No strong seasonality detected</span>`);
        }
        badgesEl.innerHTML = badges.join(" ");
    }

    function renderChart(data) {
        if (chartInstance) chartInstance.destroy();
        const ctx = document.getElementById("forecastChart").getContext("2d");

        const historyLabels = data.history.map((h) => h.date.slice(0, 10));
        const forecastLabels = data.forecast.map((f) => f.date.slice(0, 10));
        const labels = [...historyLabels, ...forecastLabels];

        const historyData = data.history.map((h) => h.value);
        const forecastData = new Array(historyLabels.length - 1).fill(null)
            .concat([data.history[data.history.length - 1].value])
            .concat(data.forecast.map((f) => f.value));
        const upperData = new Array(historyLabels.length).fill(null).concat(data.forecast.map((f) => f.upper));
        const lowerData = new Array(historyLabels.length).fill(null).concat(data.forecast.map((f) => f.lower));

        chartInstance = new Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Upper bound", data: upperData, borderColor: "transparent",
                        backgroundColor: "rgba(79,70,229,0.1)", fill: "+1", pointRadius: 0, order: 3,
                    },
                    {
                        label: "Lower bound", data: lowerData, borderColor: "transparent",
                        backgroundColor: "rgba(79,70,229,0.1)", fill: false, pointRadius: 0, order: 3,
                    },
                    {
                        label: "Historical", data: historyData, borderColor: "#4f46e5",
                        backgroundColor: "transparent", pointRadius: 2, order: 1,
                    },
                    {
                        label: "Forecast", data: forecastData, borderColor: "#dc2626",
                        borderDash: [6, 4], backgroundColor: "transparent", pointRadius: 2, order: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { labels: { filter: (item) => item.text === "Historical" || item.text === "Forecast" } },
                },
            },
        });
    }
});
