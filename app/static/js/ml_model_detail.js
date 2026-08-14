document.addEventListener("DOMContentLoaded", function () {
    if (typeof MODEL_METRICS === "undefined") return; // not on model detail page

    // --- Confusion matrix ---
    if (MODEL_TASK_TYPE === "classification" && MODEL_METRICS && MODEL_METRICS.confusion_matrix) {
        renderConfusionMatrix(MODEL_METRICS.confusion_matrix, MODEL_METRICS.labels);
    }

    // --- Feature importance chart ---
    if (FEATURE_IMPORTANCE && FEATURE_IMPORTANCE.top_features && FEATURE_IMPORTANCE.top_features.length) {
        renderImportanceChart(FEATURE_IMPORTANCE.top_features);
    }

    function renderConfusionMatrix(matrix, labels) {
        const table = document.getElementById("confusionMatrix");
        let html = "<thead><tr><th></th>";
        labels.forEach((l) => (html += `<th>Predicted ${escapeHtml(l)}</th>`));
        html += "</tr></thead><tbody>";
        matrix.forEach((row, i) => {
            html += `<tr><th>Actual ${escapeHtml(labels[i])}</th>`;
            row.forEach((count, j) => {
                const isDiagonal = i === j;
                const bg = isDiagonal ? "rgba(22,163,74,0.25)" : "rgba(220,38,38,0.12)";
                html += `<td style="background:${bg}">${count}</td>`;
            });
            html += "</tr>";
        });
        html += "</tbody>";
        table.innerHTML = html;
    }

    function renderImportanceChart(topFeatures) {
        const ctx = document.getElementById("importanceChart").getContext("2d");
        new Chart(ctx, {
            type: "bar",
            data: {
                labels: topFeatures.map((f) => f.feature),
                datasets: [{ label: "Importance", data: topFeatures.map((f) => f.importance_pct), backgroundColor: "#4f46e5" }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { title: { display: true, text: "% relative influence" } } },
            },
        });
    }

    // --- Prediction form ---
    const predictForm = document.getElementById("predictForm");
    if (predictForm) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
        const errorEl = document.getElementById("predictError");
        const resultEl = document.getElementById("predictResult");

        predictForm.addEventListener("submit", function (e) {
            e.preventDefault();
            errorEl.classList.add("d-none");
            resultEl.classList.add("d-none");

            const payload = {};
            document.querySelectorAll(".predict-field").forEach((input) => {
                payload[input.dataset.column] = input.value;
            });

            fetch(PREDICT_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify(payload),
            })
                .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
                .then(({ ok, data }) => {
                    if (!ok) {
                        errorEl.textContent = data.error || "Prediction failed.";
                        errorEl.classList.remove("d-none");
                        return;
                    }
                    let text = `Prediction: ${data.prediction}`;
                    if (data.probabilities) {
                        text += ` (confidence: ${Math.max(...data.probabilities).toFixed(2)})`;
                    }
                    resultEl.textContent = text;
                    resultEl.classList.remove("d-none");
                })
                .catch(() => {
                    errorEl.textContent = "Prediction failed. Please try again.";
                    errorEl.classList.remove("d-none");
                });
        });
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
});
