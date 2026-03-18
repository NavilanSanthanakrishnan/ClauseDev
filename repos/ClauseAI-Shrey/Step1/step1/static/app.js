const form = document.getElementById("upload-form");
const fileInput = document.getElementById("bill-file");
const submitButton = document.getElementById("submit-button");
const statusElement = document.getElementById("status");
const workspace = document.getElementById("workspace");
const approvalPanel = document.getElementById("approval-panel");
const approveButton = document.getElementById("approve-button");
const rejectButton = document.getElementById("reject-button");
const steerForm = document.getElementById("steer-form");
const steerInput = document.getElementById("steer-input");
const steerButton = document.getElementById("steer-button");
const downloadLink = document.getElementById("download-link");
const generateMetadataButton = document.getElementById("generate-metadata-button");
const saveMetadataButton = document.getElementById("save-metadata-button");
const startSearchButton = document.getElementById("start-search-button");
const metadataForm = document.getElementById("metadata-form");

const metadataInputs = {
    title: document.getElementById("metadata-title-input"),
    jurisdiction_hints: document.getElementById("metadata-jurisdictions-input"),
    description: document.getElementById("metadata-description-input"),
    summary: document.getElementById("metadata-summary-input"),
    policy_intent: document.getElementById("metadata-policy-intent-input"),
    policy_domain: document.getElementById("metadata-domains-input"),
    bill_type_hints: document.getElementById("metadata-bill-types-input"),
    legal_mechanisms: document.getElementById("metadata-mechanisms-input"),
    affected_entities: document.getElementById("metadata-entities-input"),
    enforcement_mechanisms: document.getElementById("metadata-enforcement-input"),
    fiscal_elements: document.getElementById("metadata-fiscal-input"),
    search_phrases: document.getElementById("metadata-search-phrases-input"),
};

let workflowState = null;
let sessionStream = null;
let requestInFlight = false;
let metadataDirty = false;
let lastProfileFingerprint = "";

function setStatus(message, className) {
    statusElement.textContent = message;
    statusElement.className = `status ${className}`;
}

function stageLabel(stage) {
    const labels = {
        upload: "Upload",
        metadata: "Metadata",
        similarity: "Similarity",
        step3: "Step 3",
        step4: "Step 4",
        step5: "Step 5",
        done: "Done",
    };
    return labels[stage] || "Workflow";
}

function statusLabel(status) {
    const labels = {
        waiting_user: "Waiting",
        running: "Running",
        waiting_approval: "Review diff",
        completed: "Completed",
        error: "Error",
    };
    return labels[status] || "Idle";
}

function listToText(values) {
    return (values || []).join("\n");
}

function textToList(value) {
    return [...new Set(
        (value || "")
            .split(/[\n,]/)
            .map((item) => item.trim())
            .filter(Boolean)
    )];
}

function readMetadataForm() {
    return {
        title: metadataInputs.title.value.trim(),
        description: metadataInputs.description.value.trim(),
        summary: metadataInputs.summary.value.trim(),
        policy_domain: textToList(metadataInputs.policy_domain.value),
        policy_intent: metadataInputs.policy_intent.value.trim(),
        legal_mechanisms: textToList(metadataInputs.legal_mechanisms.value),
        affected_entities: textToList(metadataInputs.affected_entities.value),
        enforcement_mechanisms: textToList(metadataInputs.enforcement_mechanisms.value),
        fiscal_elements: textToList(metadataInputs.fiscal_elements.value),
        bill_type_hints: textToList(metadataInputs.bill_type_hints.value),
        jurisdiction_hints: textToList(metadataInputs.jurisdiction_hints.value),
        search_phrases: textToList(metadataInputs.search_phrases.value),
    };
}

function populateMetadataForm(profile) {
    const safeProfile = profile || {};
    metadataInputs.title.value = safeProfile.title || "";
    metadataInputs.description.value = safeProfile.description || "";
    metadataInputs.summary.value = safeProfile.summary || "";
    metadataInputs.policy_domain.value = listToText(safeProfile.policy_domain);
    metadataInputs.policy_intent.value = safeProfile.policy_intent || "";
    metadataInputs.legal_mechanisms.value = listToText(safeProfile.legal_mechanisms);
    metadataInputs.affected_entities.value = listToText(safeProfile.affected_entities);
    metadataInputs.enforcement_mechanisms.value = listToText(safeProfile.enforcement_mechanisms);
    metadataInputs.fiscal_elements.value = listToText(safeProfile.fiscal_elements);
    metadataInputs.bill_type_hints.value = listToText(safeProfile.bill_type_hints);
    metadataInputs.jurisdiction_hints.value = listToText(safeProfile.jurisdiction_hints);
    metadataInputs.search_phrases.value = listToText(safeProfile.search_phrases);
    metadataDirty = false;
    lastProfileFingerprint = JSON.stringify(safeProfile);
}

function renderChips(targetId, values) {
    const target = document.getElementById(targetId);
    target.innerHTML = "";
    (values || []).forEach((value) => {
        const chip = document.createElement("span");
        chip.className = "chip soft";
        chip.textContent = value;
        target.appendChild(chip);
    });
}

function renderResults(results, timings, progressMessage, similarityStatus) {
    const root = document.getElementById("results");
    const timingsRoot = document.getElementById("timings");
    const statusRoot = document.getElementById("similarity-status");
    const timingPairs = Object.entries(timings || {}).map(([key, value]) => `${key}: ${value}s`);
    timingsRoot.textContent = timingPairs.join(" | ");
    statusRoot.textContent = progressMessage || (
        similarityStatus === "running"
            ? "Finding similar bills..."
            : "Similar-bill search has not started yet."
    );

    if (!results || !results.length) {
        root.innerHTML = `<div class="empty-card">${similarityStatus === "running" ? "Waiting for ranked bill candidates..." : "No similar bills staged yet."}</div>`;
        return;
    }

    root.innerHTML = results.map((bill) => {
        const action = bill.latest_action_date
            ? `${bill.latest_action_date} · ${bill.latest_action_description}`
            : bill.latest_action_description;
        const tags = (bill.section_headings || []).slice(0, 4).map((tag) => `<span class="chip soft">${tag}</span>`).join("");
        const link = bill.primary_bill_url
            ? `<a href="${bill.primary_bill_url}" target="_blank" rel="noreferrer">Open source bill</a>`
            : "";
        return `
            <article class="result-card">
                <div class="result-head">
                    <div>
                        <h3>${bill.identifier}</h3>
                        <p class="meta-line">${bill.title}</p>
                        <p class="meta-line">${bill.jurisdiction_name} · ${bill.derived_status}</p>
                    </div>
                    <div class="score-pill">${Math.round((bill.final_score || 0) * 100)}</div>
                </div>
                <p class="detail-copy">${bill.description || bill.structured_summary || bill.match_reason || ""}</p>
                <p class="meta-line">${bill.match_reason || ""}</p>
                <p class="meta-line">${action || ""}</p>
                <div class="chips">${tags}</div>
                ${link ? `<div class="result-actions">${link}</div>` : ""}
            </article>
        `;
    }).join("");
}

function renderSourceBills(sourceBills) {
    const root = document.getElementById("source-bills");
    if (!sourceBills || !sourceBills.length) {
        root.innerHTML = `<div class="empty-card">No source bills staged yet.</div>`;
        return;
    }

    root.innerHTML = sourceBills.map((bill) => {
        const sections = (bill.sections || []).slice(0, 3).map((section) => {
            const title = section.heading || (section.label ? `Section ${section.label}` : "Section");
            return `<span class="chip soft">${title}</span>`;
        }).join("");
        const link = bill.primary_bill_url
            ? `<a href="${bill.primary_bill_url}" target="_blank" rel="noreferrer">Open</a>`
            : "";
        return `
            <article class="source-card">
                <div class="result-head">
                    <div>
                        <h3>${bill.identifier}</h3>
                        <p class="meta-line">${bill.title}</p>
                    </div>
                    <span class="source-status">${bill.derived_status || "context"}</span>
                </div>
                <p class="detail-copy">${bill.summary || bill.excerpt || ""}</p>
                <div class="chips">${sections}</div>
                ${link ? `<div class="result-actions">${link}</div>` : ""}
            </article>
        `;
    }).join("");
}

function renderStakeholderReport(report) {
    const safeReport = report || {};
    document.getElementById("stakeholder-summary").textContent = safeReport.summary
        || (safeReport.status === "in_progress" ? "Step 5 stakeholder analysis is in progress." : "Step 5 has not started yet.");
    document.getElementById("stakeholder-entities").textContent = safeReport.estimated_affected_entities || "No affected-entity estimate yet.";
    document.getElementById("stakeholder-viability").textContent = safeReport.political_viability || "No political viability assessment yet.";
    document.getElementById("stakeholder-feasibility").textContent = safeReport.implementation_feasibility || "No implementation assessment yet.";
    document.getElementById("stakeholder-sme").textContent = safeReport.sme_impact_test || "No SME impact test yet.";
    document.getElementById("stakeholder-distribution").textContent = safeReport.distributional_impacts
        || safeReport.beneficiaries_vs_cost_bearers
        || "No distributional assessment yet.";
    renderChips("stakeholder-focus", safeReport.optimization_focus || []);

    const improvementsRoot = document.getElementById("stakeholder-improvements");
    const improvements = safeReport.proposed_improvements || [];
    if (!improvements.length) {
        improvementsRoot.innerHTML = `<div class="empty-card">No Step 5 improvement plan recorded yet.</div>`;
    } else {
        improvementsRoot.innerHTML = improvements.slice(0, 8).map((improvement) => `
            <article class="source-card">
                <div class="result-head">
                    <div>
                        <h3>${improvement.title || "Untitled improvement"}</h3>
                        <p class="meta-line">${improvement.objective || improvement.legislative_strategy || ""}</p>
                    </div>
                    <span class="source-status">${improvement.status || "planned"}</span>
                </div>
                <p class="detail-copy">${improvement.reason || improvement.stakeholder_problem || ""}</p>
                <p class="meta-line">${improvement.expected_effect || ""}</p>
                <div class="chips">${(improvement.stakeholder_groups || []).slice(0, 4).map((group) => `<span class="chip soft">${group}</span>`).join("")}</div>
            </article>
        `).join("");
    }

    const actorsRoot = document.getElementById("stakeholder-actors");
    const actors = safeReport.actors || [];
    if (!actors.length) {
        actorsRoot.innerHTML = `<div class="empty-card">No stakeholder actors recorded yet.</div>`;
    } else {
        actorsRoot.innerHTML = actors.slice(0, 6).map((actor) => `
            <article class="source-card">
                <div class="result-head">
                    <div>
                        <h3>${actor.name || "Unnamed stakeholder"}</h3>
                        <p class="meta-line">${actor.category || ""}</p>
                    </div>
                    <span class="source-status">${actor.likely_position || "mixed"}</span>
                </div>
                <p class="detail-copy">${actor.lobbying_power ? `Influence: ${actor.lobbying_power}. ` : ""}${actor.affected_entities_estimate || ""}${actor.sme_exposure ? ` SME exposure: ${actor.sme_exposure}.` : ""}</p>
                <div class="chips">${(actor.key_concerns || []).slice(0, 4).map((concern) => `<span class="chip soft">${concern}</span>`).join("")}</div>
            </article>
        `).join("");
    }

    const sourcesRoot = document.getElementById("stakeholder-sources");
    const sources = safeReport.sources || [];
    if (!sources.length) {
        sourcesRoot.innerHTML = `<div class="empty-card">No stakeholder evidence sources yet.</div>`;
    } else {
        sourcesRoot.innerHTML = sources.slice(0, 6).map((source) => `
            <article class="source-card">
                <div class="result-head">
                    <div>
                        <h3>${source.title || "Untitled source"}</h3>
                        <p class="meta-line">${source.organization || ""}${source.published_at ? ` · ${source.published_at}` : ""}${source.source_type ? ` · ${source.source_type}` : ""}</p>
                    </div>
                </div>
                <p class="detail-copy">${source.summary || source.relevance || ""}</p>
                ${source.url ? `<div class="result-actions"><a href="${source.url}" target="_blank" rel="noreferrer">Open</a></div>` : ""}
            </article>
        `).join("");
    }
}

function renderEventFeed(events) {
    const root = document.getElementById("event-feed");
    if (!events || !events.length) {
        root.innerHTML = `<div class="empty-card">Workflow activity will appear here.</div>`;
        return;
    }

    root.innerHTML = [...events].reverse().map((event) => `
        <article class="event-card ${event.kind}">
            <div class="event-head">
                <strong>${event.title || "Update"}</strong>
                <span class="event-kind">${event.kind}</span>
            </div>
            ${event.body ? `<pre>${event.body}</pre>` : ""}
        </article>
    `).join("");
}

function metadataStatusText(session) {
    if (session.thread_id) {
        return "Metadata is locked because the live Codex editing loop is active.";
    }
    if (session.metadata_status === "generating") {
        return "Codex is generating draft metadata for this bill.";
    }
    if (session.metadata_status === "ready") {
        return "Review and edit the metadata, then start similar-bill search.";
    }
    if (session.metadata_status === "confirmed") {
        return session.similarity_status === "running"
            ? "Metadata is confirmed. Similar-bill search is running."
            : "Metadata is confirmed and ready for retrieval.";
    }
    return "Generate metadata to start the workflow.";
}

function workflowMessage(session) {
    if (session.error_message) {
        return session.error_message;
    }
    if (session.status === "waiting_approval") {
        return "Codex is paused on a proposed draft diff.";
    }
    if (session.current_stage === "upload") {
        return "The bill is loaded. Generate metadata to continue.";
    }
    if (session.current_stage === "metadata") {
        return metadataStatusText(session);
    }
    if (session.current_stage === "similarity") {
        return session.similarity_progress_message || "Searching similar bills.";
    }
    if (session.completion_summary) {
        return session.completion_summary;
    }
    if (session.status === "running") {
        return "Codex is actively editing the bill.";
    }
    return "Workflow session ready.";
}

function renderSession(session) {
    workflowState = session;
    workspace.classList.remove("hidden");

    document.getElementById("session-stage").textContent = stageLabel(session.current_stage);
    document.getElementById("session-stage").className = `pill ${session.current_stage}`;
    document.getElementById("session-status").textContent = statusLabel(session.status);
    document.getElementById("session-status").className = `pill status-${session.status}`;
    document.getElementById("metadata-title").textContent = session.profile?.title || "Bill metadata";
    document.getElementById("metadata-status").textContent = metadataStatusText(session);
    document.getElementById("draft-meta").textContent = `Version ${session.current_draft_version}`;
    document.getElementById("draft-text").textContent = session.current_draft_text || "";
    document.getElementById("workflow-message").textContent = workflowMessage(session);
    document.getElementById("live-message").textContent = session.latest_agent_message || session.final_message || "";

    const profileFingerprint = JSON.stringify(session.profile || {});
    if (!metadataDirty || profileFingerprint !== lastProfileFingerprint) {
        populateMetadataForm(session.profile || {});
    }

    const pending = session.pending_approval;
    if (pending) {
        document.getElementById("approval-diff").textContent = pending.diff || "Diff preview unavailable.";
        document.getElementById("approval-caption").textContent = pending.reason || "Codex is waiting for your decision on this diff.";
        approvalPanel.classList.remove("hidden");
    } else {
        approvalPanel.classList.add("hidden");
    }

    const metadataLocked = Boolean(session.thread_id);
    const metadataInputsDisabled = requestInFlight || metadataLocked || session.metadata_status === "generating" || session.similarity_status === "running";
    generateMetadataButton.textContent = session.metadata_status === "ready" ? "Regenerate metadata" : "Generate metadata";
    generateMetadataButton.disabled = requestInFlight || metadataLocked || session.metadata_status === "generating";
    saveMetadataButton.disabled = requestInFlight || metadataLocked || session.metadata_status === "generating" || session.similarity_status === "running";
    startSearchButton.disabled = requestInFlight || metadataLocked || session.metadata_status === "generating" || session.similarity_status === "running";
    Object.values(metadataInputs).forEach((input) => {
        input.disabled = metadataInputsDisabled;
    });
    approveButton.disabled = requestInFlight || !pending;
    rejectButton.disabled = requestInFlight || !pending;
    steerButton.disabled = requestInFlight || !session.thread_id || Boolean(pending);
    submitButton.disabled = requestInFlight;

    downloadLink.href = `/api/workflow/${session.session_id}/draft`;
    downloadLink.classList.remove("hidden");

    renderResults(
        session.results || [],
        session.search_timings || {},
        session.similarity_progress_message,
        session.similarity_status
    );
    renderSourceBills(session.source_bills || []);
    renderStakeholderReport(session.stakeholder_report || {});
    renderEventFeed(session.events || []);
}

function connectStream(sessionId) {
    if (sessionStream) {
        sessionStream.close();
    }
    sessionStream = new EventSource(`/api/workflow/${sessionId}/stream`);
    sessionStream.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        renderSession(payload);
    };
    sessionStream.onerror = () => {
        setStatus("Lost the live session stream. Refresh to reconnect.", "error");
    };
}

async function postJson(url, body, workingMessage) {
    if (requestInFlight) {
        return null;
    }
    requestInFlight = true;
    setStatus(workingMessage, "working");
    if (workflowState) {
        renderSession(workflowState);
    }

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: body ? { "Content-Type": "application/json" } : {},
            body: body ? JSON.stringify(body) : undefined,
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || "Request failed.");
        }
        renderSession(payload);
        setStatus("Session updated.", "done");
        return payload;
    } catch (error) {
        setStatus(error.message || "Request failed.", "error");
        return null;
    } finally {
        requestInFlight = false;
        if (workflowState) {
            renderSession(workflowState);
        }
    }
}

async function saveMetadata(showMessage = true) {
    if (!workflowState) {
        return null;
    }
    const payload = await postJson(
        `/api/workflow/${workflowState.session_id}/metadata`,
        { profile: readMetadataForm() },
        showMessage ? "Saving metadata..." : "Saving metadata before search..."
    );
    if (payload) {
        metadataDirty = false;
    }
    return payload;
}

metadataForm.addEventListener("input", () => {
    metadataDirty = true;
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
        setStatus("Choose a PDF, DOCX, or TXT bill first.", "error");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    submitButton.disabled = true;
    requestInFlight = true;
    setStatus("Uploading bill and creating workflow session...", "working");

    try {
        const response = await fetch("/api/workflow/upload", {
            method: "POST",
            body: formData,
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.detail || "Upload failed.");
        }
        renderSession(payload);
        connectStream(payload.session_id);
        setStatus("Bill loaded. Generate metadata to continue.", "done");
    } catch (error) {
        setStatus(error.message || "Upload failed.", "error");
    } finally {
        requestInFlight = false;
        submitButton.disabled = false;
        if (workflowState) {
            renderSession(workflowState);
        }
    }
});

generateMetadataButton.addEventListener("click", async () => {
    if (!workflowState) {
        return;
    }
    metadataDirty = false;
    await postJson(
        `/api/workflow/${workflowState.session_id}/metadata/generate`,
        null,
        "Generating metadata..."
    );
});

saveMetadataButton.addEventListener("click", async () => {
    await saveMetadata(true);
});

startSearchButton.addEventListener("click", async () => {
    if (!workflowState) {
        return;
    }
    if (metadataDirty) {
        const saved = await saveMetadata(false);
        if (!saved) {
            return;
        }
    }
    await postJson(
        `/api/workflow/${workflowState.session_id}/similar-bills/start`,
        null,
        "Starting similar-bill search..."
    );
});

approveButton.addEventListener("click", async () => {
    if (!workflowState) {
        return;
    }
    await postJson(`/api/workflow/${workflowState.session_id}/approve`, null, "Approving diff...");
});

rejectButton.addEventListener("click", async () => {
    if (!workflowState) {
        return;
    }
    await postJson(`/api/workflow/${workflowState.session_id}/reject`, null, "Rejecting diff...");
});

steerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!workflowState) {
        return;
    }
    const message = steerInput.value.trim();
    if (!message) {
        setStatus("Enter some feedback for Codex first.", "error");
        return;
    }
    const payload = await postJson(
        `/api/workflow/${workflowState.session_id}/steer`,
        { message },
        "Sending feedback to Codex..."
    );
    if (payload) {
        steerInput.value = "";
    }
});
