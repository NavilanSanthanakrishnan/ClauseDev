const form = document.getElementById("upload-form");
const fileInput = document.getElementById("bill-file");
const submitButton = document.getElementById("submit-button");
const statusNode = document.getElementById("status");
const resultsNode = document.getElementById("results");
const profileNode = document.getElementById("profile-output");
const conflictsNode = document.getElementById("conflicts-output");
const metaNode = document.getElementById("meta-output");

function setStatus(message) {
  statusNode.textContent = message;
}

function renderConflict(conflict) {
  const wrapper = document.createElement("article");
  wrapper.className = "conflict-item";

  const title = document.createElement("h3");
  title.textContent = `${conflict.citation} · ${conflict.conflict_type}`;
  wrapper.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "conflict-meta";
  meta.textContent = `${conflict.source_system} · severity=${conflict.severity} · confidence=${conflict.confidence}`;
  wrapper.appendChild(meta);

  if (conflict.heading) {
    const heading = document.createElement("p");
    heading.textContent = conflict.heading;
    wrapper.appendChild(heading);
  }

  const explanation = document.createElement("p");
  explanation.textContent = conflict.explanation;
  wrapper.appendChild(explanation);

  if (conflict.bill_excerpt) {
    const billQuote = document.createElement("blockquote");
    billQuote.textContent = `Bill: ${conflict.bill_excerpt}`;
    wrapper.appendChild(billQuote);
  }

  if (conflict.statute_excerpt) {
    const statuteQuote = document.createElement("blockquote");
    statuteQuote.textContent = `Statute: ${conflict.statute_excerpt}`;
    wrapper.appendChild(statuteQuote);
  }

  if (conflict.source_url) {
    const link = document.createElement("a");
    link.href = conflict.source_url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "Open source";
    wrapper.appendChild(link);
  }

  return wrapper;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = fileInput.files?.[0];
  if (!file) {
    setStatus("Choose a bill file first.");
    return;
  }

  submitButton.disabled = true;
  resultsNode.classList.add("hidden");
  conflictsNode.innerHTML = "";
  setStatus("Analyzing the bill and retrieving candidate statutes...");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Request failed.");
    }

    profileNode.textContent = JSON.stringify(payload.profile, null, 2);
    metaNode.textContent = JSON.stringify(
      {
        filename: payload.filename,
        candidate_counts: payload.candidate_counts,
        timings: payload.timings,
        warnings: payload.warnings,
      },
      null,
      2,
    );

    if (payload.conflicts.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No conflicts were confirmed in the top candidate statutes.";
      conflictsNode.appendChild(empty);
    } else {
      payload.conflicts.forEach((conflict) => {
        conflictsNode.appendChild(renderConflict(conflict));
      });
    }

    resultsNode.classList.remove("hidden");
    setStatus(`Analysis complete. ${payload.conflicts.length} conflicts returned.`);
  } catch (error) {
    setStatus(error.message || "Analysis failed.");
  } finally {
    submitButton.disabled = false;
  }
});
