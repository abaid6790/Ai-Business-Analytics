document.addEventListener("DOMContentLoaded", function () {
    const dropzone = document.getElementById("dropzone");
    if (!dropzone) return; // not on the upload page

    const fileInput = document.getElementById("fileInput");
    const browseBtn = document.getElementById("browseBtn");
    const uploadStep = document.getElementById("uploadStep");
    const previewStep = document.getElementById("previewStep");
    const uploadError = document.getElementById("uploadError");
    const uploadLoading = document.getElementById("uploadLoading");
    const startOverBtn = document.getElementById("startOverBtn");

    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    let currentTempFilename = null;

    browseBtn.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length) handleFile(fileInput.files[0]);
    });

    function showError(message) {
        uploadError.textContent = message;
        uploadError.classList.remove("d-none");
    }

    function clearError() {
        uploadError.classList.add("d-none");
        uploadError.textContent = "";
    }

    function handleFile(file) {
        clearError();
        uploadLoading.classList.remove("d-none");
        dropzone.classList.add("d-none");

        const formData = new FormData();
        formData.append("file", file);

        fetch(UPLOAD_PREVIEW_URL, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: formData,
        })
            .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                uploadLoading.classList.add("d-none");
                if (!ok) {
                    dropzone.classList.remove("d-none");
                    showError(data.error || "Upload failed.");
                    return;
                }
                renderPreview(data);
            })
            .catch(() => {
                uploadLoading.classList.add("d-none");
                dropzone.classList.remove("d-none");
                showError("Upload failed. Please try again.");
            });
    }

    function renderPreview(data) {
        currentTempFilename = data.temp_filename;

        document.getElementById("fieldTempFilename").value = data.temp_filename;
        document.getElementById("fieldOriginalFilename").value = data.original_filename;
        document.getElementById("fieldFileType").value = data.file_type;
        document.getElementById("fieldFileSize").value = data.file_size_bytes;

        const nameField = document.getElementById("name");
        if (nameField && !nameField.value) {
            nameField.value = data.original_filename.replace(/\.[^/.]+$/, "");
        }

        renderStats(data.stats);
        renderTable(data.preview);

        uploadStep.classList.add("d-none");
        previewStep.classList.remove("d-none");
    }

    function renderStats(stats) {
        const grid = document.getElementById("statGrid");
        const items = [
            ["bi-table", "Rows", stats.row_count.toLocaleString()],
            ["bi-columns-gap", "Columns", stats.column_count],
            ["bi-exclamation-circle", "Missing values", stats.missing_values_count.toLocaleString()],
            ["bi-copy", "Duplicate rows", stats.duplicate_rows_count === null ? "—" : stats.duplicate_rows_count.toLocaleString()],
            ["bi-hdd", "Memory usage", formatBytes(stats.memory_usage_bytes)],
            ["bi-123", "Numeric cols", stats.numeric_columns.length],
            ["bi-tag", "Categorical cols", stats.categorical_columns.length],
            ["bi-calendar3", "Date cols", stats.datetime_columns.length],
        ];

        grid.innerHTML = items
            .map(
                ([icon, label, value]) => `
            <div class="stat-card">
                <div class="stat-icon bg-primary-subtle text-primary"><i class="bi ${icon}"></i></div>
                <div>
                    <div class="stat-value">${value}</div>
                    <div class="stat-label">${label}</div>
                </div>
            </div>`
            )
            .join("");

        document.getElementById("chunkedWarning").classList.toggle(
            "d-none",
            !stats.duplicate_detection_skipped
        );
    }

    function renderTable(preview) {
        const headRow = document.getElementById("previewHeadRow");
        const bodyRows = document.getElementById("previewBodyRows");

        headRow.innerHTML = preview.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");

        bodyRows.innerHTML = preview.rows
            .map((row) => {
                const cells = preview.columns
                    .map((c) => `<td>${escapeHtml(formatCell(row[c]))}</td>`)
                    .join("");
                return `<tr>${cells}</tr>`;
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

    function formatBytes(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
        return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
    }

    startOverBtn.addEventListener("click", () => {
        if (currentTempFilename) {
            fetch(UPLOAD_DISCARD_URL, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body: `temp_filename=${encodeURIComponent(currentTempFilename)}`,
            }).catch(() => {});
        }
        currentTempFilename = null;
        fileInput.value = "";
        previewStep.classList.add("d-none");
        uploadStep.classList.remove("d-none");
        dropzone.classList.remove("d-none");
    });
});
