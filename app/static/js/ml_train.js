document.addEventListener("DOMContentLoaded", function () {
    const trainBtn = document.getElementById("trainBtn");
    if (!trainBtn) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const targetSelect = document.getElementById("targetColumn");
    const selectAllBtn = document.getElementById("selectAllBtn");
    const trainError = document.getElementById("trainError");
    const progressEmpty = document.getElementById("progressEmpty");
    const progressList = document.getElementById("progressList");

    let pollTimer = null;

    selectAllBtn.addEventListener("click", function () {
        const boxes = document.querySelectorAll(".feature-checkbox");
        const allChecked = Array.from(boxes).every((b) => b.checked);
        boxes.forEach((b) => (b.checked = !allChecked));
    });

    // Target column shouldn't also be a feature — auto-uncheck it.
    targetSelect.addEventListener("change", function () {
        document.querySelectorAll(".feature-checkbox").forEach((b) => {
            if (b.value === targetSelect.value) b.checked = false;
        });
    });

    trainBtn.addEventListener("click", function () {
        const target = targetSelect.value;
        const features = Array.from(document.querySelectorAll(".feature-checkbox:checked"))
            .map((b) => b.value)
            .filter((v) => v !== target);

        trainError.classList.add("d-none");
        trainBtn.disabled = true;

        fetch(ML_TRAIN_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
            body: JSON.stringify({ target_column: target, feature_columns: features }),
        })
            .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                trainBtn.disabled = false;
                if (!ok) {
                    trainError.textContent = data.error || "Could not start training.";
                    trainError.classList.remove("d-none");
                    return;
                }
                progressEmpty.classList.add("d-none");
                progressList.classList.remove("d-none");
                startPolling(data.training_run_id);
            })
            .catch(() => {
                trainBtn.disabled = false;
                trainError.textContent = "Could not start training. Please try again.";
                trainError.classList.remove("d-none");
            });
    });

    function startPolling(trainingRunId) {
        if (pollTimer) clearInterval(pollTimer);
        poll(trainingRunId);
        pollTimer = setInterval(() => poll(trainingRunId), 2000);
    }

    function poll(trainingRunId) {
        fetch(`${ML_STATUS_URL}?training_run_id=${encodeURIComponent(trainingRunId)}`)
            .then((res) => res.json())
            .then((data) => {
                renderProgress(data.models);
                const allDone = data.models.every((m) => m.status === "completed" || m.status === "failed");
                if (allDone) {
                    clearInterval(pollTimer);
                    setTimeout(() => window.location.reload(), 1200);
                }
            })
            .catch(() => {});
    }

    function renderProgress(models) {
        progressList.innerHTML = models
            .map((m) => {
                const icon = {
                    pending: '<i class="bi bi-hourglass text-muted"></i>',
                    running: '<i class="bi bi-arrow-repeat text-primary spin"></i>',
                    completed: '<i class="bi bi-check-circle-fill text-success"></i>',
                    failed: '<i class="bi bi-x-circle-fill text-danger"></i>',
                }[m.status] || "";

                let scoreText = "";
                if (m.metrics) {
                    scoreText = m.metrics.accuracy !== undefined
                        ? `accuracy ${m.metrics.accuracy}`
                        : `R\u00b2 ${m.metrics.r2}`;
                }

                return `<div class="d-flex justify-content-between align-items-center py-1 border-bottom">
                    <span>${icon} ${escapeHtml(m.algorithm)}</span>
                    <span class="text-muted small">${scoreText}</span>
                </div>`;
            })
            .join("");
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
});
