async function uploadFile() {

    document.getElementById("loader").style.display = "block";

    const fileInput = document.getElementById("fileInput");

    if (!fileInput.files.length) {

        alert("Please select a file");

        document.getElementById("loader").style.display = "none";

        return;
    }

    const file = fileInput.files[0];

    const formData = new FormData();

    formData.append("file", file);

    formData.append(
        "statement_type",
        document.getElementById("statementType").value
    );

    formData.append(
        "report_period_type",
        document.getElementById("reportPeriodType").value
    );

    formData.append(
        "from_date",
        document.getElementById("fromDate").value
    );

    formData.append(
        "to_date",
        document.getElementById("toDate").value
    );

    formData.append(
        "compare_report",
        document.getElementById("compareReport").value
    );

    formData.append(
        "compare_from_date",
        document.getElementById("compareFromDate").value
    );

    formData.append(
        "compare_to_date",
        document.getElementById("compareToDate").value
    );

    try {

        const response = await fetch(
            "https://finsight-ai-aiwu.onrender.com/upload",
            {
                method: "POST",
                body: formData
            }
        );

        if (!response.ok) {

            throw new Error("Upload failed");
        }

        const data = await response.json();

        console.log(data);

        // =========================
        // SUMMARY
        // =========================

        const summary = data.summary;

        document.getElementById(
            "summaryContent"
        ).innerHTML = `
            <div class="summary-item">
                <h3>Statement Type</h3>
                <p>${summary.statement_type || "-"}</p>
            </div>

            <div class="summary-item">
                <h3>Assets</h3>
                <p>${summary.total_sections.assets || 0}</p>
            </div>

            <div class="summary-item">
                <h3>Liabilities</h3>
                <p>${summary.total_sections.liabilities || 0}</p>
            </div>

            <div class="summary-item">
                <h3>Equity</h3>
                <p>${summary.total_sections.equity || 0}</p>
            </div>

            <div class="summary-item">
                <h3>Revenue</h3>
                <p>${summary.total_sections.revenue || 0}</p>
            </div>

            <div class="summary-item">
                <h3>Expenses</h3>
                <p>${summary.total_sections.expenses || 0}</p>
            </div>
        `;

        // =========================
        // TABLE
        // =========================

        const tableBody = document.querySelector(
            "#comparisonTable tbody"
        );

        tableBody.innerHTML = "";

        data.comparison_results.forEach(item => {

            const growth =
                parseFloat(item.growth_percent || 0);

            const growthClass =
                growth >= 0
                ? "positive"
                : "negative";

            const row = `
                <tr>
                    <td>${item.account || "-"}</td>

                    <td>${item.year1_value || 0}</td>

                    <td>${item.year2_value || 0}</td>

                    <td class="${growthClass}">
                        ${growth}%
                    </td>
                </tr>
            `;

            tableBody.innerHTML += row;
        });

        // =========================
        // AI INSIGHTS
        // =========================

        document.getElementById(
            "aiInsights"
        ).innerText =
            data.ai_insights.ai_analysis ||
            "No AI insights generated.";

    } catch (error) {

        console.error(error);

        alert("Error uploading file");
    }

    document.getElementById(
        "loader"
    ).style.display = "none";
}