document.addEventListener("DOMContentLoaded", function () {
    const loadingEl = document.getElementById("edaLoading");
    const errorEl = document.getElementById("edaError");
    const contentEl = document.getElementById("edaContent");
    if (!loadingEl) return; // not on the EDA page

    const chartInstances = [];

    fetch(EDA_DATA_URL)
        .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
        .then(({ ok, data }) => {
            loadingEl.classList.add("d-none");
            if (!ok) {
                errorEl.textContent = data.error || "Could not load analysis.";
                errorEl.classList.remove("d-none");
                return;
            }
            contentEl.classList.remove("d-none");
            renderAutoCharts(data.charts);
            renderNumericStats(data.stats.numeric);
            renderCategoricalStats(data.stats.categorical);
            renderCorrelation(data.correlation);
            setupTabs();
        })
        .catch(() => {
            loadingEl.classList.add("d-none");
            errorEl.textContent = "Could not load analysis. Please try again.";
            errorEl.classList.remove("d-none");
        });

    function setupTabs() {
        document.querySelectorAll("#edaTabs .nav-link").forEach((btn) => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("#edaTabs .nav-link").forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
                document.querySelectorAll(".eda-tab-panel").forEach((p) => p.classList.add("d-none"));
                document.getElementById(`panel-${btn.dataset.tab}`).classList.remove("d-none");
            });
        });
    }

    function renderAutoCharts(charts) {
        const grid = document.getElementById("autoChartsGrid");
        if (!charts.length) {
            grid.innerHTML = '<p class="text-muted">Not enough data to suggest charts automatically.</p>';
            return;
        }

        charts.forEach((chart, i) => {
            const panel = document.createElement("div");
            panel.className = "card-panel";
            panel.innerHTML = `
                <div class="card-panel-header"><h5>${escapeHtml(chart.title)}</h5></div>
                <div class="chart-canvas-wrapper"><canvas id="autoChart${i}"></canvas></div>
            `;
            grid.appendChild(panel);

            const ctx = panel.querySelector("canvas").getContext("2d");
            const cfg = toChartJsConfig(chart.data);
            chartInstances.push(new Chart(ctx, cfg));
        });
    }

    function renderNumericStats(numericStats) {
        const tbody = document.querySelector("#numericStatsTable tbody");
        const cols = Object.keys(numericStats);
        if (!cols.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-muted">No numeric columns detected.</td></tr>';
            return;
        }
        tbody.innerHTML = cols
            .map((col) => {
                const s = numericStats[col];
                return `<tr>
                    <td>${escapeHtml(col)}</td>
                    <td>${fmt(s.count)}</td><td>${fmt(s.mean)}</td><td>${fmt(s.median)}</td>
                    <td>${fmt(s.std)}</td><td>${fmt(s.min)}</td><td>${fmt(s.q1)}</td>
                    <td>${fmt(s.q3)}</td><td>${fmt(s.max)}</td>
                </tr>`;
            })
            .join("");
    }

    function renderCategoricalStats(categoricalStats) {
        const grid = document.getElementById("categoricalStatsGrid");
        const cols = Object.keys(categoricalStats);
        if (!cols.length) {
            grid.innerHTML = '<p class="text-muted">No categorical columns detected.</p>';
            return;
        }
        grid.innerHTML = cols
            .map((col) => {
                const s = categoricalStats[col];
                const rows = (s.top_values || [])
                    .map((tv) => `<li>${escapeHtml(tv.value)} <span class="text-muted float-end">${tv.count}</span></li>`)
                    .join("");
                return `<div class="card-panel">
                    <div class="card-panel-header"><h6>${escapeHtml(col)}</h6>
                        <p class="text-muted small mb-0">${s.unique_count} unique values</p>
                    </div>
                    <ul class="list-clean">${rows}</ul>
                </div>`;
            })
            .join("");
    }

    function renderCorrelation(correlation) {
        const container = document.getElementById("correlationHeatmap");
        const emptyMsg = document.getElementById("correlationEmpty");

        if (!correlation.columns.length || correlation.matrix.length < 2) {
            container.innerHTML = "";
            emptyMsg.textContent = "Need at least two numeric columns to compute correlations.";
            return;
        }
        emptyMsg.textContent = "";

        const cols = correlation.columns;
        let html = '<table class="table table-sm heatmap-table"><thead><tr><th></th>';
        cols.forEach((c) => (html += `<th>${escapeHtml(c)}</th>`));
        html += "</tr></thead><tbody>";

        correlation.matrix.forEach((row, i) => {
            html += `<tr><th>${escapeHtml(cols[i])}</th>`;
            row.forEach((value) => {
                const bg = correlationColor(value);
                html += `<td style="background:${bg}">${value.toFixed(2)}</td>`;
            });
            html += "</tr>";
        });
        html += "</tbody></table>";
        container.innerHTML = html;
    }

    function correlationColor(value) {
        // -1 -> red, 0 -> neutral, 1 -> blue
        const alpha = Math.min(Math.abs(value), 1) * 0.65;
        return value >= 0
            ? `rgba(79, 70, 229, ${alpha})`
            : `rgba(220, 38, 38, ${alpha})`;
    }

    function toChartJsConfig(data) {
        const type = data.chart_type === "area" ? "line" : data.chart_type;
        const palette = ["#4f46e5", "#0ea5e9", "#16a34a", "#d97706", "#dc2626", "#7c3aed"];

        const datasets = data.datasets.map((ds, i) => ({
            label: ds.label,
            data: ds.data,
            backgroundColor: type === "line" ? "transparent" : palette[i % palette.length],
            borderColor: palette[i % palette.length],
            fill: data.chart_type === "area",
        }));

        return {
            type: type === "scatter" ? "scatter" : type,
            data: { labels: data.labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: datasets.length > 1 } },
            },
        };
    }

    function fmt(v) {
        return v === null || v === undefined ? "—" : v;
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
});
