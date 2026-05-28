async function uploadFile() {

    // =========================
    // SHOW LOADER
    // =========================

    document.getElementById(
        "loader"
    ).style.display = "block";

    // =========================
    // GET FILE
    // =========================

    const fileInput = document.getElementById(
        "fileInput"
    );

    if (!fileInput.files.length) {

        alert("Please select a file");

        document.getElementById(
            "loader"
        ).style.display = "none";

        return;
    }

    const file = fileInput.files[0];

    // =========================
    // CREATE FORM DATA
    // =========================

    const formData = new FormData();

    formData.append("file", file);

    try {

        // =========================
        // API CALL
        // =========================

        const response = await fetch(
            "https://finsight-ai-aiwu.onrender.com/upload",
            {
                method: "POST",
                body: formData
            }
        );

        // =========================
        // CHECK RESPONSE
        // =========================

        if (!response.ok) {

            throw new Error(
                "API request failed"
            );
        }

        const data = await response.json();

        console.log(data);

        // =========================
        // SUMMARY SECTION
        // =========================

        const summaryDiv = document.getElementById(
            "summaryContent"
        );

        summaryDiv.innerHTML = `
            <div class="summary-item">
                <h3>Statement Type</h3>
                <p>${data.summary.statement_type}</p>
            </div>

            <div class="summary-item">
                <h3>Assets</h3>
                <p>${data.summary.total_sections.assets}</p>
            </div>

            <div class="summary-item">
                <h3>Liabilities</h3>
                <p>${data.summary.total_sections.liabilities}</p>
            </div>

            <div class="summary-item">
                <h3>Equity</h3>
                <p>${data.summary.total_sections.equity}</p>
            </div>

            <div class="summary-item">
                <h3>Revenue</h3>
                <p>${data.summary.total_sections.revenue}</p>
            </div>

            <div class="summary-item">
                <h3>Expenses</h3>
                <p>${data.summary.total_sections.expenses}</p>
            </div>

            <div class="summary-item">
                <h3>Unknown</h3>
                <p>${data.summary.total_sections.unknown}</p>
            </div>
        `;

        // =========================
        // COMPARISON TABLE
        // =========================

        const tableBody = document.querySelector(
            "#comparisonTable tbody"
        );

        tableBody.innerHTML = "";

        data.comparison_results.forEach(item => {

            const growth =
                parseFloat(
                    item.growth_percent || 0
                );

            const growthClass =
                growth >= 0
                ? "positive"
                : "negative";

            const row = `
                <tr>

                    <td>${item.account}</td>

                    <td>
                        ${item.year1_value}
                    </td>

                    <td>
                        ${item.year2_value}
                    </td>

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

        const insightsDiv = document.getElementById(
            "aiInsights"
        );

        // If AI exists
        if (
            data.ai_insights &&
            data.ai_insights.status === "success"
        ) {

            insightsDiv.innerHTML =
                formatAIResponse(
                    data.ai_insights.ai_analysis
                );

        } else {

            insightsDiv.innerHTML = `
                <p>
                    AI insights are currently unavailable.
                </p>

                <p>
                    Financial analysis completed successfully.
                </p>
            `;
        }

        // =========================
        // HIDE LOADER
        // =========================

        document.getElementById(
            "loader"
        ).style.display = "none";

    } catch (error) {

        console.error(error);

        // =========================
        // HIDE LOADER
        // =========================

        document.getElementById(
            "loader"
        ).style.display = "none";

        alert(
            "Error uploading file"
        );
    }
}

// =========================
// FORMAT AI RESPONSE
// =========================

function formatAIResponse(text) {

    if (!text) {

        return `
            <p>
                No AI analysis available.
            </p>
        `;
    }

    return text

        // Bold markdown
        .replace(
            /\*\*(.*?)\*\*/g,
            "<strong>$1</strong>"
        )

        // Line breaks
        .replace(/\n/g, "<br>");
}