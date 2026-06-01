const API_URL = "https://finsight-ai-aiwu.onrender.com/analyze";

function toggleComparisonFields() {
    const comparing = document.getElementById("compareMode").value === "yes";
    document.querySelectorAll(".comparison-field").forEach(field => {
        field.style.display = comparing ? "flex" : "none";
    });
}

function formatAmount(value) {
    if (value === null || value === undefined || value === "") return "-";
    const number = Number(value);
    return Number.isFinite(number)
        ? number.toLocaleString(undefined, { maximumFractionDigits: 2 })
        : value;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
    })[character]);
}

async function uploadFile() {
    const loader = document.getElementById("loader");
    const currentFile = document.getElementById("currentFile");
    const previousFile = document.getElementById("previousFile");
    const compareMode = document.getElementById("compareMode").value;

    if (!currentFile.files.length) {
        alert("Please select the current period statement");
        return;
    }
    if (compareMode === "yes" && !previousFile.files.length) {
        alert("Please select the previous period statement");
        return;
    }

    loader.style.display = "block";
    const formData = new FormData();
    formData.append("current_file", currentFile.files[0]);
    if (compareMode === "yes") formData.append("previous_file", previousFile.files[0]);
    formData.append("statement_type", document.getElementById("statementType").value);
    formData.append("compare_mode", compareMode);
    formData.append("from_date", document.getElementById("fromDate").value);
    formData.append("to_date", document.getElementById("toDate").value);
    formData.append("compare_from_date", document.getElementById("compareFromDate").value);
    formData.append("compare_to_date", document.getElementById("compareToDate").value);

    try {
        const response = await fetch(API_URL, { method: "POST", body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Upload failed");
        renderSummary(data);
        renderResults(data);
        renderInsights(data.ai_insights);
    } catch (error) {
        console.error(error);
        alert(error.message || "Error uploading file");
    } finally {
        loader.style.display = "none";
    }
}

function renderSummary(data) {
    const summary = data.summary || {};
    const cards = [
        ["Statement Type", (data.statement_type || "-").replaceAll("_", " ")],
        ["Mode", (data.mode || "-").replaceAll("_", " ")],
        ["Income", formatAmount(summary.total_income)],
        ["Expenses", formatAmount(summary.total_expenses)],
        ["Assets", formatAmount(summary.total_assets)],
        ["Liabilities", formatAmount(summary.total_liabilities)],
        ["Net Result", formatAmount(summary.net_result)],
    ];
    document.getElementById("summaryContent").innerHTML = cards.map(([label, value]) => `
        <div class="summary-item"><h3>${escapeHtml(label)}</h3><p>${escapeHtml(value)}</p></div>
    `).join("");
}

function renderResults(data) {
    const comparing = data.mode === "comparison";
    document.querySelector("#comparisonTable thead").innerHTML = `
        <tr>
            <th>Account</th>
            <th>Section</th>
            ${comparing ? "<th>Previous Period</th>" : ""}
            <th>Current Period</th>
            ${comparing ? "<th>Variance</th><th>Variance %</th>" : ""}
        </tr>
    `;
    document.querySelector("#comparisonTable tbody").innerHTML =
        (data.comparison_results || []).map(item => {
            const variance = Number(item.variance_amount || 0);
            const varianceClass = variance >= 0 ? "positive" : "negative";
            return `
                <tr>
                    <td>${escapeHtml(item.account || "-")}</td>
                    <td>${escapeHtml((item.section || "-").replaceAll("_", " "))}</td>
                    ${comparing ? `<td>${escapeHtml(formatAmount(item.previous_value))}</td>` : ""}
                    <td>${escapeHtml(formatAmount(item.current_value))}</td>
                    ${comparing ? `<td class="${varianceClass}">${escapeHtml(formatAmount(item.variance_amount))}</td>` : ""}
                    ${comparing ? `<td class="${varianceClass}">${escapeHtml(formatAmount(item.variance_percentage))}%</td>` : ""}
                </tr>
            `;
        }).join("");
}

function renderInsights(insights) {
    const list = Array.isArray(insights) ? insights : [];
    document.getElementById("aiInsights").innerHTML = list.length
        ? `<ul>${list.map(point => `<li>${escapeHtml(point)}</li>`).join("")}</ul>`
        : "No AI insights generated.";
}

toggleComparisonFields();
