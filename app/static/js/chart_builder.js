document.addEventListener("DOMContentLoaded", function () {
    const previewBtn = document.getElementById("previewBtn");
    if (!previewBtn) return; // not on the chart builder page

    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const chartTypeEl = document.getElementById("chartType");
    const xAxisEl = document.getElementById("xAxis");
    const yAxisEl = document.getElementById("yAxis");
    const aggregationEl = document.getElementById("aggregation");
    const groupByEl = document.getElementById("groupBy");
    const filtersContainer = document.getElementById("filtersContainer");
    const addFilterBtn = document.getElementById("addFilterBtn");

    const previewLoading = document.getElementById("previewLoading");
    const previewError = document.getElementById("previewError");
    const previewCanvasWrapper = document.getElementById("previewCanvasWrapper");
    const saveChartSection = document.getElementById("saveChartSection");
    const downloadChartBtn = document.getElementById("downloadChartBtn");

    let chartInstance = null;
    let lastSpec = null;
    let filterCount = 0;

    // --- Show/hide fields based on chart type ---
    function updateFieldVisibility() {
        const type = chartTypeEl.value;
        const isHistogram = type === "histogram";
        const isScatter = type === "scatter";
        const isPie = type === "pie" || type === "doughnut";

        document.getElementById("yAxisWrapper").classList.toggle("d-none", isHistogram);
        document.getElementById("aggregationWrapper").classList.toggle("d-none", isHistogram || isScatter);
        document.getElementById("groupByWrapper").classList.toggle("d-none", isHistogram || isScatter || isPie);
    }
    chartTypeEl.addEventListener("change", updateFieldVisibility);
    updateFieldVisibility();

    // --- Dynamic filter rows ---
    function addFilterRow() {
        filterCount += 1;
        const row = document.createElement("div");
        row.className = "filter-row";
        row.dataset.filterId = filterCount;

        const columnOptions = ALL_COLUMNS.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");

        row.innerHTML = `
            <select class="form-select form-select-sm filter-column">${columnOptions}</select>
            <select class="form-select form-select-sm filter-operator">
                <option value="equals">=</option>
                <option value="not_equals">≠</option>
                <option value="greater_than">&gt;</option>
                <option value="less_than">&lt;</option>
                <option value="contains">contains</option>
            </select>
            <input type="text" class="form-control form-control-sm filter-value" placeholder="value">
            <button type="button" class="btn btn-sm btn-outline-danger remove-filter-btn"><i class="bi bi-x"></i></button>
        `;
        row.querySelector(".remove-filter-btn").addEventListener("click", () => row.remove());
        filtersContainer.appendChild(row);
    }
    addFilterBtn.addEventListener("click", addFilterRow);

    function collectFilters() {
        return Array.from(filtersContainer.querySelectorAll(".filter-row")).map((row) => ({
            column: row.querySelector(".filter-column").value,
            operator: row.querySelector(".filter-operator").value,
            value: row.querySelector(".filter-value").value,
        })).filter((f) => f.value !== "");
    }

    function buildSpec() {
        return {
            chart_type: chartTypeEl.value,
            x: xAxisEl.value,
            y: yAxisEl.value || null,
            aggregation: aggregationEl.value,
            group_by: groupByEl.value || null,
            filters: collectFilters(),
        };
    }

    previewBtn.addEventListener("click", function () {
        const spec = buildSpec();
        lastSpec = spec;

        previewError.classList.add("d-none");
        previewLoading.classList.remove("d-none");
        previewCanvasWrapper.classList.add("d-none");
        saveChartSection.classList.add("d-none");

        fetch(CHART_PREVIEW_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(spec),
        })
            .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                previewLoading.classList.add("d-none");
                if (!ok) {
                    previewError.textContent = data.error || "Could not build chart.";
                    previewError.classList.remove("d-none");
                    return;
                }
                renderChart(data.data);
                previewCanvasWrapper.classList.remove("d-none");
                saveChartSection.classList.remove("d-none");

                document.getElementById("saveChartType").value = spec.chart_type;
                document.getElementById("saveConfigJson").value = JSON.stringify(spec);
            })
            .catch(() => {
                previewLoading.classList.add("d-none");
                previewError.textContent = "Could not build chart. Please try again.";
                previewError.classList.remove("d-none");
            });
    });

    function renderChart(data) {
        if (chartInstance) {
            chartInstance.destroy();
        }
        const ctx = document.getElementById("previewCanvas").getContext("2d");
        const type = data.chart_type === "area" ? "line" : data.chart_type;
        const palette = ["#4f46e5", "#0ea5e9", "#16a34a", "#d97706", "#dc2626", "#7c3aed"];

        const datasets = data.datasets.map((ds, i) => ({
            label: ds.label,
            data: ds.data,
            backgroundColor: type === "line" ? "transparent" : palette[i % palette.length],
            borderColor: palette[i % palette.length],
            fill: data.chart_type === "area",
        }));

        chartInstance = new Chart(ctx, {
            type: type === "scatter" ? "scatter" : type,
            data: { labels: data.labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: datasets.length > 1 || type === "pie" || type === "doughnut" } },
            },
        });
    }

    downloadChartBtn.addEventListener("click", function () {
        if (!chartInstance) return;
        const link = document.createElement("a");
        link.download = "chart.png";
        link.href = chartInstance.toBase64Image();
        link.click();
    });

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
});
