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
            "http://127.0.0.1:8000/upload",
            {
                method: "POST",
                body: formData
            }
        );

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

            const growthClass =
                item.growth_percent >= 0
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
                        ${item.growth_percent}%
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
            data.ai_insights.ai_analysis;

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