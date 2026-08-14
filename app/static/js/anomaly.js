document.addEventListener("DOMContentLoaded", function () {
    const runBtn = document.getElementById("runBtn");
    if (!runBtn) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const methodSelect = document.getElementById("methodSelect");
    const methodHint = document.getElementById("methodHint");
    const thresholdWrapper = document.getElementById("thresholdWrapper");
    const contaminationWrapper = document.getElementById("contaminationWrapper");

    const resultsLoading = document.getElementById("resultsLoading");
    const resultsError = document.getElementById("resultsError");
    const resultsContent = document.getElementById("resultsContent");

    let chartInstance = null;

    const METHOD_HINTS = {
        iqr: "Flags values far outside the interquartile range. Good default for a single column.",
        zscore: "Flags values far from the mean in standard deviations. Sensitive to extreme outliers skewing the mean itself.",
        isolation_forest: "Detects unusual combinations across multiple columns at once.",
    };

    function updateMethodUI() {
        const method = methodSelect.value;
        methodHint.textContent = METHOD_HINTS[method] || "";
        thresholdWrapper.classList.toggle("d-none", method !== "zscore");
        contaminationWrapper.classList.toggle("d-none", method !== "isolation_forest");
    }
    methodSelect.addEventListener("change", updateMethodUI);
    updateMethodUI();

    function collectColumns() {
        return Array.from(document.querySelectorAll('input[name="anomaly_column"]:checked')).map((el) => el.value);
    }

    runBtn.addEventListener("click", function () {
        const columns = collectColumns();
        if (!columns.length) {
            resultsError.textContent = "Select at least one column.";
            resultsError.classList.remove("d-none");
            return;
        }

        const payload = { method: methodSelect.value, columns };
        if (methodSelect.value === "zscore") {
            payload.threshold = parseFloat(document.getElementById("thresholdInput").value) || 3.0;
        }
        if (methodSelect.value === "isolation_forest") {
            payload.contamination = parseFloat(document.getElementById("contaminationInput").value) || 0.05;
        }

        resultsError.classList.add("d-none");
        resultsContent.classList.add("d-none");
        resultsLoading.classList.remove("d-none");
        runBtn.disabled = true;

        fetch(ANOMALY_DETECT_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(payload),
        })
            .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                resultsLoading.classList.add("d-none");
                runBtn.disabled = false;
                if (!ok) {
                    resultsError.textContent = data.error || "Detection failed.";
                    resultsError.classList.remove("d-none");
                    return;
                }
                renderResults(data);
            })
            .catch(() => {
                resultsLoading.classList.add("d-none");
                runBtn.disabled = false;
                resultsError.textContent = "Detection failed. Please try again.";
                resultsError.classList.remove("d-none");
            });
    });

    function renderResults(data) {
        document.getElementById("anomalyCount").textContent = data.anomaly_count.toLocaleString();
        document.getElementById("rowsAnalyzed").textContent = data.row_count.toLocaleString();

        const truncatedNote = document.getElementById("truncatedNote");
        if (data.truncated) {
            truncatedNote.textContent = `Showing the top ${data.anomalies.length} most severe anomalies out of ${data.anomaly_count} found.`;
            truncatedNote.classList.remove("d-none");
        } else {
            truncatedNote.classList.add("d-none");
        }

        renderChart(data);
        renderTable(data);

        resultsContent.classList.remove("d-none");
    }

    function renderChart(data) {
        if (chartInstance) chartInstance.destroy();
        const ctx = document.getElementById("anomalyChart").getContext("2d");

        if (data.columns.length >= 2) {
            const anomalyPoints = data.anomalies
                .map((a) => ({ x: a.row[data.columns[0]], y: a.row[data.columns[1]] }))
                .filter((p) => p.x !== null && p.y !== null && p.x !== undefined && p.y !== undefined);

            chartInstance = new Chart(ctx, {
                type: "scatter",
                data: {
                    datasets: [
                        { label: "Anomalies", data: anomalyPoints, backgroundColor: "#dc2626", pointRadius: 5 },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { title: { display: true, text: data.columns[0] } },
                        y: { title: { display: true, text: data.columns[1] } },
                    },
                },
            });
        } else {
            const sorted = [...data.anomalies].sort((a, b) => b.score - a.score).slice(0, 30);
            chartInstance = new Chart(ctx, {
                type: "bar",
                data: {
                    labels: sorted.map((a) => `Row ${a.row_index}`),
                    datasets: [{ label: "Anomaly score", data: sorted.map((a) => a.score), backgroundColor: "#dc2626" }],
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
            });
        }
    }

    function renderTable(data) {
        const headRow = document.getElementById("anomalyTableHead");
        const bodyRows = document.getElementById("anomalyTableBody");

        if (!data.anomalies.length) {
            headRow.innerHTML = "";
            bodyRows.innerHTML = '<tr><td class="text-muted">No anomalies found with the current settings.</td></tr>';
            return;
        }

        const allColumns = Object.keys(data.anomalies[0].row);
        headRow.innerHTML = '<th>Score</th>' + allColumns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");

        bodyRows.innerHTML = data.anomalies
            .map((a) => {
                const cells = allColumns.map((c) => `<td>${escapeHtml(formatCell(a.row[c]))}</td>`).join("");
                return `<tr><td><span class="badge text-bg-danger">${a.score}</span></td>${cells}</tr>`;
            })
            .join("");
    }

    function formatCell(value) {
        if (value === null || value === undefined) return "";
        return String(value);
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
});
