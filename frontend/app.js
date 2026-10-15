const API_BASE_URL = window.API_BASE_URL || "";

let currentPage = 1;
const pageLimit = 20;

document.addEventListener("DOMContentLoaded", () => {
    setupTabs();
    setupEventListeners();
    loadLaureates();
});

function setupTabs() {
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));

            btn.classList.add("active");
            const targetTab = btn.getAttribute("data-tab");
            document.getElementById(targetTab).classList.add("active");

            if (targetTab === "laureates" && document.getElementById("laureates-table-body").children.length <= 1) {
                loadLaureates();
            } else if (targetTab === "multiple") {
                loadMultipleLaureates();
            } else if (targetTab === "stats") {
                loadStats();
            }
        });
    });
}

function setupEventListeners() {
    document.getElementById("apply-filters-btn").addEventListener("click", () => {
        currentPage = 1;
        loadLaureates();
    });

    document.getElementById("reset-filters-btn").addEventListener("click", () => {
        document.getElementById("filter-category").value = "";
        document.getElementById("filter-year-start").value = "";
        document.getElementById("filter-year-end").value = "";
        currentPage = 1;
        loadLaureates();
    });

    document.getElementById("prev-page-btn").addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            loadLaureates();
        }
    });

    document.getElementById("next-page-btn").addEventListener("click", () => {
        currentPage++;
        loadLaureates();
    });

    document.getElementById("search-btn").addEventListener("click", performSearch);
    document.getElementById("search-input").addEventListener("keypress", (e) => {
        if (e.key === "Enter") performSearch();
    });
}

async function loadLaureates() {
    const tbody = document.getElementById("laureates-table-body");
    tbody.innerHTML = '<tr><td colspan="5" class="loading">Loading laureates...</td></tr>';

    const category = document.getElementById("filter-category").value;
    const yearStart = document.getElementById("filter-year-start").value;
    const yearEnd = document.getElementById("filter-year-end").value;

    const offset = (currentPage - 1) * pageLimit;
    let url = `${API_BASE_URL}/api/laureates?limit=${pageLimit}&offset=${offset}`;

    if (category) url += `&category=${encodeURIComponent(category)}`;
    if (yearStart) url += `&year_start=${encodeURIComponent(yearStart)}`;
    if (yearEnd) url += `&year_end=${encodeURIComponent(yearEnd)}`;

    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
        const data = await resp.json();

        renderLaureatesTable(data.laureates, tbody);
        updatePagination(data.total);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="loading">Error loading data: ${escapeHtml(err.message)}</td></tr>`;
    }
}

function renderLaureatesTable(laureates, tbody) {
    if (!laureates || laureates.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading">No laureates found matching criteria.</td></tr>';
        return;
    }

    let html = "";
    laureates.forEach(l => {
        const name = l.full_name || l.known_name;
        const type = l.is_organization ? "Organization" : (l.gender ? capitalize(l.gender) : "Individual");
        const country = l.birth_country || "N/A";

        const years = l.prizes.map(p => p.award_year).join(", ");
        const prizesHtml = l.prizes.map(p => {
            const badgeClass = getCategoryBadgeClass(p.category);
            return `<div>
                <span class="badge ${badgeClass}">${escapeHtml(p.category)} (${p.award_year})</span>
                <small>${escapeHtml(p.motivation || "No motivation recorded")}</small>
            </div>`;
        }).join("<br>");

        html += `
            <tr>
                <td><strong>${escapeHtml(name)}</strong></td>
                <td>${escapeHtml(type)}</td>
                <td>${escapeHtml(country)}</td>
                <td>${escapeHtml(years)}</td>
                <td>${prizesHtml}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

function updatePagination(total) {
    const totalPages = Math.ceil(total / pageLimit) || 1;
    document.getElementById("page-info").textContent = `Page ${currentPage} of ${totalPages} (${total} total)`;
    document.getElementById("prev-page-btn").disabled = currentPage <= 1;
    document.getElementById("next-page-btn").disabled = currentPage >= totalPages;
}

async function performSearch() {
    const q = document.getElementById("search-input").value.trim();
    const summary = document.getElementById("search-results-summary");
    const tbody = document.getElementById("search-table-body");

    if (!q) {
        summary.textContent = "";
        tbody.innerHTML = '<tr><td colspan="4" class="placeholder">Please enter a search term.</td></tr>';
        return;
    }

    tbody.innerHTML = '<tr><td colspan="4" class="loading">Searching motivations...</td></tr>';

    try {
        const resp = await fetch(`${API_BASE_URL}/api/search?q=${encodeURIComponent(q)}`);
        if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
        const data = await resp.json();

        summary.textContent = `Found ${data.count} result(s) for "${q}"`;

        if (!data.results || data.results.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="loading">No motivations matched your query.</td></tr>';
            return;
        }

        let html = "";
        data.results.forEach(r => {
            const badgeClass = getCategoryBadgeClass(r.category);
            html += `
                <tr>
                    <td><strong>${escapeHtml(r.known_name)}</strong></td>
                    <td>${escapeHtml(String(r.award_year))}</td>
                    <td><span class="badge ${badgeClass}">${escapeHtml(r.category)}</span></td>
                    <td>${escapeHtml(r.motivation)}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
    } catch (err) {
        summary.textContent = "";
        tbody.innerHTML = `<tr><td colspan="4" class="loading">Error searching: ${escapeHtml(err.message)}</td></tr>`;
    }
}

async function loadMultipleLaureates() {
    const tbody = document.getElementById("multiple-table-body");
    tbody.innerHTML = '<tr><td colspan="4" class="loading">Loading multiple prize winners...</td></tr>';

    try {
        const resp = await fetch(`${API_BASE_URL}/api/laureates/multiple`);
        if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
        const data = await resp.json();

        if (!data.laureates || data.laureates.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="loading">No multiple prize laureates found.</td></tr>';
            return;
        }

        let html = "";
        data.laureates.forEach(l => {
            const country = l.birth_country || "N/A";
            const prizesHtml = l.prizes.map(p => {
                const badgeClass = getCategoryBadgeClass(p.category);
                return `<div style="margin-bottom: 0.3rem;">
                    <span class="badge ${badgeClass}">${escapeHtml(p.category)} (${p.award_year})</span>:
                    <em>"${escapeHtml(p.motivation || "")}"</em>
                </div>`;
            }).join("");

            html += `
                <tr>
                    <td><strong>${escapeHtml(l.known_name)}</strong></td>
                    <td>${escapeHtml(country)}</td>
                    <td><strong>${l.prize_count}</strong></td>
                    <td>${prizesHtml}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="4" class="loading">Error loading multiple prize winners: ${escapeHtml(err.message)}</td></tr>`;
    }
}

async function loadStats() {
    const grid = document.getElementById("stats-grid");
    grid.innerHTML = '<div class="loading">Loading statistics...</div>';

    try {
        const resp = await fetch(`${API_BASE_URL}/api/stats/countries`);
        if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
        const data = await resp.json();

        if (!data.countries || data.countries.length === 0) {
            grid.innerHTML = '<div class="loading">No country statistics available.</div>';
            return;
        }

        let html = "";
        data.countries.forEach(c => {
            html += `
                <div class="stat-card">
                    <div class="country-name">${escapeHtml(c.birth_country)}</div>
                    <div class="count">${c.laureate_count}</div>
                    <small>Laureate(s)</small>
                </div>
            `;
        });
        grid.innerHTML = html;
    } catch (err) {
        grid.innerHTML = `<div class="loading">Error loading statistics: ${escapeHtml(err.message)}</div>`;
    }
}

function getCategoryBadgeClass(category) {
    if (!category) return "";
    const cat = category.toLowerCase();
    if (cat.includes("physic")) return "badge-physics";
    if (cat.includes("chem")) return "badge-chemistry";
    if (cat.includes("med") || cat.includes("physiol")) return "badge-medicine";
    if (cat.includes("liter")) return "badge-literature";
    if (cat.includes("peace")) return "badge-peace";
    if (cat.includes("econ")) return "badge-economics";
    return "";
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function capitalize(str) {
    if (!str) return "";
    return str.charAt(0).toUpperCase() + str.slice(1);
}
