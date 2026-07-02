const API_URL = "/analyze";
let currentData = null;
let currentUser = null;

// Theme management
function initTheme() {
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme === "dark" || savedTheme === "light") {
        setTheme(savedTheme);
    } else {
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        setTheme(prefersDark ? "dark" : "light");
    }
}

function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
    const btn = document.getElementById("themeToggle");
    if (btn) {
        btn.innerText = theme === "dark" ? "☀️ Light Mode" : "🌙 Dark Mode";
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
    setTheme(currentTheme === "dark" ? "light" : "dark");
}

function handleFileChange(input, displayId) {
    const display = document.getElementById(displayId);
    if (!display) return;
    const file = input.files[0];
    if (file) {
        let name = file.name;
        // Clean up duplication if present
        if (name.startsWith("trial-balancetrial_balance")) {
            name = name.replace("trial-balancetrial_balance", "trial_balance");
        }
        display.textContent = name;
    } else {
        display.textContent = "No file chosen";
    }
}

function initFileListeners() {
    const curFile = document.getElementById("currentFile");
    const prevFile = document.getElementById("previousFile");

    if (curFile) {
        curFile.addEventListener("change", () => handleFileChange(curFile, "currentFileName"));
    }
    if (prevFile) {
        prevFile.addEventListener("change", () => handleFileChange(prevFile, "previousFileName"));
    }
}

async function handleMockUpload() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mockUpload") === "true") {
        try {
            const response = await fetch("/backend/uploads/trial-balancetrial_balance_30-05-2026-121835.xlsx");
            if (!response.ok) throw new Error("Failed to fetch test file");
            const blob = await response.blob();
            const file = new File([blob], "trial-balancetrial_balance_30-05-2026-121835.xlsx", {
                type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            });
            const input = document.getElementById("currentFile");
            if (input) {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                input.files = dataTransfer.files;
                input.dispatchEvent(new Event("change"));
            }
        } catch (err) {
            console.error("Mock upload failed:", err);
        }
    }
}

async function checkSession() {
    try {
        const res = await fetch("/api/auth/session");
        if (res.ok) {
            const data = await res.json();
            currentUser = data;
            updateUserUI();
            handleMockUpload();
        } else {
            currentUser = null;
            updateUserUI();
            initGoogleSignIn();
        }
    } catch (err) {
        console.error("Session verification failed:", err);
        currentUser = null;
        updateUserUI();
        initGoogleSignIn();
    }
}

async function initGoogleSignIn() {
    const errorEl = document.getElementById("loginError");
    
    // Polling check to verify GIS library loading
    const waitForGoogleAPI = () => {
        return new Promise((resolve, reject) => {
            if (window.google && window.google.accounts && window.google.accounts.id) {
                resolve();
                return;
            }
            
            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                if (window.google && window.google.accounts && window.google.accounts.id) {
                    clearInterval(interval);
                    resolve();
                } else if (attempts >= 30) { // 3 seconds timeout
                    clearInterval(interval);
                    reject(new Error("Google Identity Services is unavailable. Please check your network connection or adblocker."));
                }
            }, 100);
        });
    };

    try {
        await waitForGoogleAPI();
        console.log("Google API Loaded");
        
        const res = await fetch("/api/auth/config");
        const config = await res.json();
        const client_id = config.google_client_id;
        
        if (!client_id || client_id.trim() === "" || !isNaN(client_id) || !client_id.endsWith(".apps.googleusercontent.com")) {
            const errorMsg = `Invalid Google Client ID configuration: ${client_id}`;
            console.error(errorMsg);
            if (errorEl) {
                errorEl.innerText = errorMsg;
                errorEl.style.display = "block";
            }
            return;
        }
        console.log("Client ID Loaded");
        
        console.log("Authentication Callback Registered");
        google.accounts.id.initialize({
            client_id: client_id,
            callback: handleCredentialResponse,
            auto_select: false
        });
        
        // Force disable auto-select to prevent silent login and prompt for account selection
        google.accounts.id.disableAutoSelect();
        
        console.log("Rendering Google Button");
        google.accounts.id.renderButton(
            document.getElementById("googleSignInButton"),
            { theme: "outline", size: "large", shape: "pill", width: 300 }
        );
        console.log("Google Button Rendered");
    } catch (err) {
        console.error("Failed to load Google Sign-In:", err);
        if (errorEl) {
            errorEl.innerText = err.message || "Google Identity Services is currently unavailable.";
            errorEl.style.display = "block";
        }
    }
}

async function handleCredentialResponse(response) {
    const errorEl = document.getElementById("loginError");
    if (errorEl) errorEl.style.display = "none";
    
    try {
        const loginRes = await fetch("/api/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ credential: response.credential })
        });
        
        const data = await loginRes.json();
        if (!loginRes.ok) {
            throw new Error(data.detail || "Access Denied.\nOnly NoBroker employees can access FinSight AI.");
        }
        
        currentUser = data;
        updateUserUI();
        handleMockUpload();
    } catch (err) {
        console.error("Login failed:", err);
        if (errorEl) {
            errorEl.innerText = err.message;
            errorEl.style.display = "block";
        }
    }
}

async function logoutUser() {
    const previousEmail = currentUser ? currentUser.email : null;
    
    try {
        await fetch("/api/auth/logout", { method: "POST" });
    } catch (err) {
        console.error("Logout request failed:", err);
    }
    
    if (previousEmail) {
        try {
            google.accounts.id.revoke(previousEmail, done => {
                console.log("Google session revoked for", previousEmail);
            });
        } catch (revErr) {
            console.error("Failed to revoke Google session:", revErr);
        }
    }
    
    try {
        google.accounts.id.disableAutoSelect();
    } catch (disErr) {
        console.error("Failed to disable auto-select:", disErr);
    }
    
    currentUser = null;
    updateUserUI();
    
    currentData = null;
    
    const exportContainer = document.getElementById("exportContainer");
    if (exportContainer) exportContainer.style.display = "none";
    
    const analyticsCard = document.getElementById("analyticsCard");
    if (analyticsCard) analyticsCard.style.display = "none";
    
    const summaryContent = document.getElementById("summaryContent");
    if (summaryContent) summaryContent.innerHTML = "";
    
    const aiInsights = document.getElementById("aiInsights");
    if (aiInsights) aiInsights.innerHTML = "Upload a financial report to generate AI insights.";
    
    const searchContainer = document.getElementById("searchContainer");
    if (searchContainer) searchContainer.style.display = "none";
    
    const tbody = document.querySelector("#comparisonTable tbody");
    if (tbody) tbody.innerHTML = "";
    
    initGoogleSignIn();
}

function updateUserUI() {
    const overlay = document.getElementById("loginOverlay");
    const profile = document.getElementById("userProfile");
    const avatar = document.getElementById("userAvatar");
    const nameEl = document.getElementById("profileName");
    const emailEl = document.getElementById("profileEmail");
    
    if (currentUser) {
        if (overlay) overlay.style.display = "none";
        if (profile) profile.style.display = "flex";
        if (avatar) avatar.src = currentUser.picture || "https://www.gravatar.com/avatar/?d=mp";
        if (nameEl) nameEl.innerText = currentUser.name || "NoBroker User";
        if (emailEl) emailEl.innerText = currentUser.email || "";
    } else {
        if (overlay) overlay.style.display = "flex";
        if (profile) profile.style.display = "none";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initFileListeners();
    checkSession();
});

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

// Global helper to format raw value for clean excel cells
function formatRawNumber(value) {
    if (value === null || value === undefined || value === "") return "";
    const number = Number(value);
    return Number.isFinite(number) ? number : value;
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
        if (response.status === 401) {
            currentUser = null;
            updateUserUI();
            initGoogleSignIn();
            alert(data.detail || "Session expired. Please log in again.");
            return;
        }
        if (!response.ok) throw new Error(data.detail || "Upload failed");
        currentData = data;
        document.getElementById("exportContainer").style.display = "inline-block";
        renderSummary(data);
        renderAnalytics(data.analytics);
        renderResults(data);
        renderInsights(data.ai_insights);
    } catch (error) {
        console.error(error);
        alert(error.message || "Error uploading file");
    } finally {
        loader.style.display = "none";
    }
}

function renderAnalytics(analytics) {
    const card = document.getElementById("analyticsCard");
    if (!analytics) {
        card.style.display = "none";
        return;
    }
    card.style.display = "block";

    const getVal = (obj) => {
        if (!obj || obj.value === null || obj.value === undefined) return "Not Available";
        return formatAmount(obj.value);
    };

    document.getElementById("anCashBank").innerText = getVal(analytics.cash_and_bank);
    document.getElementById("anReceivables").innerText = getVal(analytics.receivables);
    document.getElementById("anPayables").innerText = getVal(analytics.payables);
    document.getElementById("anCurrentAssets").innerText = getVal(analytics.current_assets);
    document.getElementById("anCurrentLiabilities").innerText = getVal(analytics.current_liabilities);
    document.getElementById("anWorkingCapital").innerText = getVal(analytics.working_capital);
    document.getElementById("anFixedAssets").innerText = getVal(analytics.fixed_assets);
    document.getElementById("anInvestments").innerText = getVal(analytics.investments);

    const renderRankingList = (list, elementId) => {
        const el = document.getElementById(elementId);
        if (!list || !list.length) {
            el.innerHTML = "<li>Not Available</li>";
            return;
        }
        el.innerHTML = list.map(item => `
            <li><strong>${escapeHtml(item.account)}</strong>: ${escapeHtml(formatAmount(item.value))}</li>
        `).join("");
    };

    renderRankingList(analytics.largest_assets, "anLargestAssets");
    renderRankingList(analytics.largest_liabilities, "anLargestLiabilities");
    renderRankingList(analytics.largest_income_accounts, "anTopIncome");
    renderRankingList(analytics.largest_expense_accounts, "anTopExpenses");
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
        ["Equity", formatAmount(summary.equity)],
    ];
    document.getElementById("summaryContent").innerHTML = cards.map(([label, value]) => `
        <div class="summary-item"><h3>${escapeHtml(label)}</h3><p>${escapeHtml(value)}</p></div>
    `).join("");
}

function renderResults(data) {
    document.getElementById("searchContainer").style.display = "flex";
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

let searchLogTimeout = null;
function filterTable() {
    const query = document.getElementById("searchInput").value.toLowerCase().trim();
    const clearBtn = document.getElementById("clearSearchBtn");
    
    if (query) {
        clearBtn.style.display = "inline-block";
    } else {
        clearBtn.style.display = "none";
    }
    
    const rows = document.querySelectorAll("#comparisonTable tbody tr");
    rows.forEach(row => {
        const cells = row.querySelectorAll("td");
        if (cells.length >= 2) {
            const accName = cells[0].textContent.toLowerCase();
            const sectionName = cells[1].textContent.toLowerCase();
            if (accName.includes(query) || sectionName.includes(query)) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        }
    });
    

}

function clearSearch() {
    document.getElementById("searchInput").value = "";
    filterTable();
}

function renderInsights(insights) {
    const list = Array.isArray(insights) ? insights : [];
    document.getElementById("aiInsights").innerHTML = list.length
        ? `<ul>${list.map(point => `<li>${escapeHtml(point).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</li>`).join("")}</ul>`
        : "No AI insights generated.";
}

toggleComparisonFields();

function toggleExportMenu() {
    const menu = document.getElementById("exportMenu");
    menu.style.display = menu.style.display === "block" ? "none" : "block";
}

// Close menu when clicking outside
window.addEventListener("click", function(e) {
    if (!e.target.matches('.export-btn')) {
        const menu = document.getElementById("exportMenu");
        if (menu) menu.style.display = "none";
    }
});

function exportReport(format) {
    if (!currentData) {
        alert("No report data available to export");
        return;
    }
    if (format === 'pdf') {
        exportPDF(currentData);
    } else if (format === 'xlsx') {
        exportExcel(currentData);
    }
}

function exportPDF(data) {
    console.log("Beginning of exportPDF() execution with data:", data);
    if (!window.jspdf || !window.jspdf.jsPDF) {
        alert("PDF library failed to load.");
        return;
    }
    
    // Log PDF export to backend
    const currentFileName = document.getElementById("currentFileName") ? document.getElementById("currentFileName").textContent : "unknown";
    fetch("/api/log/pdf-export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            statement_type: data.statement_type || "unknown",
            filename: currentFileName,
            status: "SUCCESS"
        })
    }).catch(err => console.error("Failed to log PDF export:", err));
    
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    
    // Title
    doc.setFont("helvetica", "bold");
    doc.setFontSize(22);
    doc.setTextColor(37, 99, 235); // Blue color
    doc.text("FinSight AI - Financial Analysis Report", 14, 20);
    
    // Metadata
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(100, 116, 139);
    doc.text(`Generated on: ${new Date().toLocaleString()}`, 14, 26);
    doc.text(`Statement Type: ${(data.statement_type || "-").toUpperCase().replace("_", " ")}`, 14, 31);
    doc.text(`Mode: ${(data.mode || "-").toUpperCase().replace("_", " ")}`, 14, 36);
    doc.text(`Generated By: ${currentUser ? `${currentUser.name} (${currentUser.email})` : "-"}`, 14, 41);
    doc.text(`Application: FinSight AI`, 14, 46);
    doc.text(`Session ID: ${currentUser ? currentUser.session_id : "-"}`, 14, 51);
    
    // Separator line
    doc.setDrawColor(226, 232, 240);
    doc.line(14, 55, 196, 55);
    
    // Section 1: Financial Summary
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(30, 41, 59);
    doc.text("1. Financial Summary", 14, 63);
    
    const summary = data.summary || {};
    const summaryRows = [
        ["Total Income", formatAmount(summary.total_income)],
        ["Total Expenses", formatAmount(summary.total_expenses)],
        ["Total Assets", formatAmount(summary.total_assets)],
        ["Total Liabilities", formatAmount(summary.total_liabilities)],
        ["Total Equity", formatAmount(summary.equity)]
    ];
    
    doc.autoTable({
        startY: 67,
        head: [["Metric", "Amount"]],
        body: summaryRows,
        theme: "striped",
        headStyles: { fillColor: [37, 99, 235] },
        margin: { left: 14, right: 14 }
    });
    
    let currentY = doc.lastAutoTable.finalY + 10;
    
    // Section 2: Financial Analytics
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.text("2. Financial Analytics", 14, currentY);
    
    const analytics = data.analytics || {};
    const analyticsRows = [
        ["Cash & Bank", formatAmount(analytics.cash_and_bank?.value)],
        ["Receivables", formatAmount(analytics.receivables?.value)],
        ["Payables", formatAmount(analytics.payables?.value)],
        ["Current Assets", formatAmount(analytics.current_assets?.value)],
        ["Current Liabilities", formatAmount(analytics.current_liabilities?.value)],
        ["Working Capital", formatAmount(analytics.working_capital?.value)],
        ["Fixed Assets", formatAmount(analytics.fixed_assets?.value)],
        ["Investments", formatAmount(analytics.investments?.value)]
    ];
    
    doc.autoTable({
        startY: currentY + 4,
        head: [["Metric", "Value"]],
        body: analyticsRows,
        theme: "striped",
        headStyles: { fillColor: [16, 185, 129] }, // Emerald green
        margin: { left: 14, right: 14 }
    });
    
    currentY = doc.lastAutoTable.finalY + 10;
    
    // Check if we need to add a new page
    if (currentY > 230) {
        doc.addPage();
        currentY = 20;
    }
    
    // Section 3: AI Insights
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.text("3. AI Financial Insights", 14, currentY);
    
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(30, 41, 59);
    
    let insightsY = currentY + 6;
    const insights = data.ai_insights || [];
    if (insights.length === 0) {
        doc.text("No insights available.", 14, insightsY);
    } else {
        const splitText = [];
        insights.forEach(insight => {
            const cleanLine = `• ${insight.replace(/\*\*/g, "")}`;
            const split = doc.splitTextToSize(cleanLine, 180);
            splitText.push(...split);
        });
        
        doc.text(splitText, 14, insightsY);
    }
    
    const blob = doc.output("blob");
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "FinSight_AI_Report.pdf";
    console.log("Triggering PDF download anchor click. URL:", url);
    a.click();
}

function exportExcel(data) {
    // Log Excel export to backend
    const currentFileName = document.getElementById("currentFileName") ? document.getElementById("currentFileName").textContent : "unknown";
    fetch("/api/log/excel-export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            statement_type: data.statement_type || "unknown",
            filename: currentFileName,
            status: "SUCCESS"
        })
    }).catch(err => console.error("Failed to log Excel export:", err));

    const wb = XLSX.utils.book_new();
    
    // Sheet 1: Report Information
    const infoData = [
        ["Report Information"],
        ["Application", "FinSight AI NBH"],
        ["Version", "1.0"],
        ["Generated On", new Date().toLocaleString()],
        ["Generated By", currentUser ? currentUser.name : "-"],
        ["Employee Email", currentUser ? currentUser.email : "-"],
        ["Statement Type", (data.statement_type || "-").toUpperCase().replace("_", " ")],
        ["Mode", (data.mode || "-").toUpperCase().replace("_", " ")],
        ["Session ID", currentUser ? currentUser.session_id : "-"]
    ];
    const wsInfo = XLSX.utils.aoa_to_sheet(infoData);
    XLSX.utils.book_append_sheet(wb, wsInfo, "Report Information");
    
    // Sheet 1: Summary
    const summary = data.summary || {};
    const summaryData = [
        ["FinSight AI - Summary Report"],
        ["Generated on", new Date().toLocaleString()],
        ["Statement Type", (data.statement_type || "-").toUpperCase().replace("_", " ")],
        ["Mode", (data.mode || "-").toUpperCase().replace("_", " ")]
    ];
    
    summaryData.push(
        [],
        ["Metric", "Value"],
        ["Total Income", formatRawNumber(summary.total_income)],
        ["Total Expenses", formatRawNumber(summary.total_expenses)],
        ["Total Assets", formatRawNumber(summary.total_assets)],
        ["Total Liabilities", formatRawNumber(summary.total_liabilities)],
        ["Total Equity", formatRawNumber(summary.equity)]
    );
    const wsSummary = XLSX.utils.aoa_to_sheet(summaryData);
    XLSX.utils.book_append_sheet(wb, wsSummary, "Summary");
    
    // Sheet 2: Normalized Financial Data
    const comparisonResults = data.comparison_results || [];
    const tableData = [
        ["Account", "Section", "Previous Value", "Current Value", "Variance Amount", "Variance Percentage"]
    ];
    comparisonResults.forEach(item => {
        tableData.push([
            item.account,
            item.section,
            formatRawNumber(item.previous_value),
            formatRawNumber(item.current_value),
            formatRawNumber(item.variance_amount),
            formatRawNumber(item.variance_percentage)
        ]);
    });
    const wsData = XLSX.utils.aoa_to_sheet(tableData);
    XLSX.utils.book_append_sheet(wb, wsData, "Normalized Data");
    
    // Sheet 3: Analytics
    const analytics = data.analytics || {};
    const analyticsData = [
        ["FinSight AI - Financial Analytics"],
        [],
        ["Metric", "Value"],
        ["Cash & Bank", formatRawNumber(analytics.cash_and_bank?.value)],
        ["Receivables", formatRawNumber(analytics.receivables?.value)],
        ["Payables", formatRawNumber(analytics.payables?.value)],
        ["Current Assets", formatRawNumber(analytics.current_assets?.value)],
        ["Current Liabilities", formatRawNumber(analytics.current_liabilities?.value)],
        ["Working Capital", formatRawNumber(analytics.working_capital?.value)],
        ["Fixed Assets", formatRawNumber(analytics.fixed_assets?.value)],
        ["Investments", formatRawNumber(analytics.investments?.value)],
        [],
        ["Ranking List", "Account", "Value"]
    ];
    
    const addRankingToSheet = (listName, list) => {
        analyticsData.push([listName, "", ""]);
        if (list && list.length) {
            list.forEach(item => {
                analyticsData.push(["", item.account, formatRawNumber(item.value)]);
            });
        } else {
            analyticsData.push(["", "Not Available", ""]);
        }
    };
    
    addRankingToSheet("Largest Assets", analytics.largest_assets);
    addRankingToSheet("Largest Liabilities", analytics.largest_liabilities);
    addRankingToSheet("Top Income Accounts", analytics.largest_income_accounts);
    addRankingToSheet("Top Expense Accounts", analytics.largest_expense_accounts);
    
    const wsAnalytics = XLSX.utils.aoa_to_sheet(analyticsData);
    XLSX.utils.book_append_sheet(wb, wsAnalytics, "Analytics");
    
    // Sheet 4: AI Insights
    const insights = data.ai_insights || [];
    const insightsData = [
        ["FinSight AI - AI Insights"],
        []
    ];
    insights.forEach((insight, idx) => {
        const cleanInsight = insight.replace(/\*\*/g, "");
        insightsData.push([`${idx + 1}.`, cleanInsight]);
    });
    const wsInsights = XLSX.utils.aoa_to_sheet(insightsData);
    XLSX.utils.book_append_sheet(wb, wsInsights, "AI Insights");
    
    XLSX.writeFile(wb, "FinSight_AI_Report.xlsx");
}
