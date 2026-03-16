const form = document.getElementById("upload-form");
const fileInput = document.getElementById("bill-file");
const submitButton = document.getElementById("submit-button");
const statusElement = document.getElementById("status");
const profilePanel = document.getElementById("profile-panel");
const resultsPanel = document.getElementById("results-panel");

function setStatus(message, className) {
    statusElement.textContent = message;
    statusElement.className = `status ${className}`;
}

function renderChips(targetId, values) {
    const target = document.getElementById(targetId);
    target.innerHTML = "";
    (values || []).forEach((value) => {
        const element = document.createElement("span");
        element.className = "chip";
        element.textContent = value;
        target.appendChild(element);
    });
}

function renderProfile(profile) {
    document.getElementById("profile-title").textContent = profile.title || "No title extracted";
    document.getElementById("profile-description").textContent = profile.description || "No description extracted";
    document.getElementById("profile-summary").textContent = profile.summary || "No summary extracted";
    renderChips("profile-domains", profile.policy_domain || []);
    renderChips("profile-mechanisms", profile.legal_mechanisms || []);
    renderChips("profile-search-phrases", profile.search_phrases || []);
    profilePanel.classList.remove("hidden");
}

function badge(text) {
    return `<span class="badge">${text}</span>`;
}

function renderResults(results, timings) {
    const resultsRoot = document.getElementById("results");
    const timingsRoot = document.getElementById("timings");
    const timingPairs = Object.entries(timings || {}).map(([key, value]) => `${key}: ${value}s`);
    timingsRoot.textContent = timingPairs.join(" | ");
    resultsRoot.className = "results";

    if (!results || !results.length) {
        resultsRoot.innerHTML = `<article class="result"><p class="meta">No matching bills were returned.</p></article>`;
        resultsPanel.classList.remove("hidden");
        return;
    }

    resultsRoot.innerHTML = results.map((bill) => {
        const subjects = (bill.subjects || []).slice(0, 8).map(badge).join("");
        const dimensions = (bill.match_dimensions || []).map(badge).join("");
        const action = bill.latest_action_date ? `${bill.latest_action_date}: ${bill.latest_action_description}` : bill.latest_action_description;
        const url = bill.primary_bill_url
            ? `<div class="actions"><a href="${bill.primary_bill_url}" target="_blank" rel="noreferrer">Open source bill</a></div>`
            : "";
        return `
            <article class="result">
                <div class="result-top">
                    <div>
                        <h3>${bill.identifier} · ${bill.title}</h3>
                        <p class="meta">${bill.jurisdiction_name} · ${bill.session_identifier} · ${bill.derived_status}</p>
                        <p class="meta">${action}</p>
                    </div>
                    <div class="score-block">
                        <div class="score">${Math.round((bill.final_score || 0) * 100)}</div>
                        <div class="score-label">match score</div>
                    </div>
                </div>
                <div class="chips">${subjects}${dimensions}</div>
                <p class="reason"><strong>Why it matched:</strong> ${bill.match_reason || "Semantic and lexical match."}</p>
                <p class="excerpt">${bill.excerpt || ""}</p>
                ${url}
            </article>
        `;
    }).join("");
    resultsPanel.classList.remove("hidden");
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
        setStatus("Choose a PDF, DOCX, or TXT bill first.", "error");
        return;
    }

    submitButton.disabled = true;
    setStatus("Extracting the bill, building the search profile, and scoring similar bills...", "working");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/api/search", {
            method: "POST",
            body: formData,
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || "Search failed.");
        }
        renderProfile(payload.profile);
        renderResults(payload.results, payload.timings);
        setStatus(`Completed. Found ${payload.results.length} similar bills.`, "done");
    } catch (error) {
        setStatus(error.message || "Search failed.", "error");
    } finally {
        submitButton.disabled = false;
    }
});
