"use strict";

const $ = (selector) => document.querySelector(selector);

const elements = {
    processCount: $("#process-count"),
    resourceCount: $("#resource-count"),
    safetyStatus: $("#safety-status"),
    safetyDescription: $("#safety-description"),
    requestCount: $("#request-count"),
    availableResources: $("#available-resources"),
    allocationTable: $("#allocation-table"),
    safeSequence: $("#safe-sequence"),
    requestForm: $("#request-form"),
    processId: $("#process-id"),
    requestInputs: [
        $("#request-r0"),
        $("#request-r1"),
        $("#request-r2")
    ],
    requestResult: $("#request-result"),
    activityTable: $("#activity-table"),
    clearLog: $("#clear-log")
};

const initialState = {
    n: 5,
    m: 3,
    available: [3, 3, 2],
    max: [
        [7, 5, 3],
        [3, 2, 2],
        [9, 0, 2],
        [2, 2, 2],
        [4, 3, 3]
    ],
    alloc: [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 2],
        [2, 1, 1],
        [0, 0, 2]
    ]
};

let currentState = structuredClone(initialState);
let requestCount = 0;
let activityLog = [];

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function calculateNeed(state) {
    return state.max.map((row, i) =>
        row.map((value, j) => value - state.alloc[i][j])
    );
}

async function apiPost(endpoint, data) {
    const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });

    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "The server rejected the request.");
    }

    return result;
}

function statePayload(state = currentState) {
    return {
        n: state.n,
        m: state.m,
        available: state.available,
        max: state.max,
        alloc: state.alloc
    };
}

function renderAvailable(state) {
    elements.availableResources.innerHTML = state.available
        .map((amount, j) => `
            <div class="resource-pill">
                <span>R${j}</span>
                <strong>${amount}</strong>
                <small>available</small>
            </div>
        `)
        .join("");
}

function renderAllocationTable(state) {
    const need = calculateNeed(state);

    const header = `
        <tr>
            <th>Process</th>
            ${Array.from({ length: state.m }, (_, j) => `<th>Alloc R${j}</th>`).join("")}
            ${Array.from({ length: state.m }, (_, j) => `<th>Max R${j}</th>`).join("")}
            ${Array.from({ length: state.m }, (_, j) => `<th>Need R${j}</th>`).join("")}
            <th>Action</th>
        </tr>
    `;

    const rows = state.alloc.map((allocation, i) => `
        <tr>
            <th scope="row">P${i}</th>
            ${allocation.map(value => `<td>${value}</td>`).join("")}
            ${state.max[i].map(value => `<td>${value}</td>`).join("")}
            ${need[i].map(value => `<td>${value}</td>`).join("")}
            <td><button type="button" class="release-btn" data-pid="${i}">Release</button></td>
        </tr>
    `).join("");

    elements.allocationTable.innerHTML = header + rows;
}

function renderSequence(result) {
    if (!result.safe) {
        elements.safeSequence.textContent = "No safe sequence exists.";
        return;
    }

    elements.safeSequence.innerHTML =
        result.safe_sequence
            .map(pid => `<span class="sequence-step">P${pid}</span>`)
            .join('<span aria-hidden="true"> → </span>');
}

function renderSummary(result) {
    elements.processCount.textContent = result.n;
    elements.resourceCount.textContent = result.m;
    elements.safetyStatus.textContent = result.safe ? "SAFE" : "UNSAFE";
    elements.safetyDescription.textContent = result.safe
        ? "A safe sequence exists"
        : "No safe sequence exists";

    elements.safetyStatus.classList.toggle("safe-text", result.safe);
    elements.safetyStatus.classList.toggle("unsafe-text", !result.safe);
}

function renderState(result) {
    currentState = {
        n: result.n,
        m: result.m,
        available: result.available,
        max: result.max,
        alloc: result.alloc
    };

    renderAvailable(currentState);
    renderAllocationTable(currentState);
    renderSequence(result);
    renderSummary(result);
}

function showResult(title, message, status) {
    elements.requestResult.className = `result-box ${({ success: 'granted', warning: 'waiting', error: 'denied' })[status] || ''}`;
    elements.requestResult.innerHTML = `
        <strong>${escapeHtml(title)}</strong>
        <p>${escapeHtml(message)}</p>
    `;
}

function renderActivity() {
    if (!activityLog.length) {
        elements.activityTable.innerHTML = `
            <tr id="empty-log">
                <td colspan="5">No activity yet. Submit a request to begin.</td>
            </tr>
        `;
        return;
    }

    elements.activityTable.innerHTML = activityLog.map(item => `
        <tr>
            <td>${escapeHtml(item.time)}</td>
            <td>P${item.pid}</td>
            <td>${escapeHtml(item.request)}</td>
            <td>${escapeHtml(item.result)}</td>
            <td>${escapeHtml(item.reason)}</td>
        </tr>
    `).join("");
}

function addActivity(pid, requested, result, reason) {
    activityLog.unshift({
        time: new Date().toLocaleTimeString(),
        pid,
        request: `(${requested.join(", ")})`,
        result,
        reason
    });

    if (activityLog.length > 50) activityLog.pop();
    renderActivity();
}

function populateProcessSelect(n) {
    const previous = Number(elements.processId.value);
    elements.processId.innerHTML = Array.from({ length: n }, (_, i) =>
        `<option value="${i}">P${i}</option>`
    ).join("");

    if (previous >= 0 && previous < n) {
        elements.processId.value = String(previous);
    }
}

async function refreshSafety() {
    const result = await apiPost("/api/check", statePayload());
    renderState(result);
}

elements.requestForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const pid = Number(elements.processId.value);
    const requested = elements.requestInputs.map(input => Number(input.value));

    if (requested.some(value => !Number.isSafeInteger(value) || value < 0)) {
        showResult("Invalid request", "Enter non-negative whole numbers.", "error");
        return;
    }

    const requestVector = requested.slice(0, currentState.m);

    if (requestVector.length !== currentState.m) {
        showResult("Configuration error", "The form does not match the resource count.", "error");
        return;
    }

    try {
        const result = await apiPost("/api/request", {
            ...statePayload(),
            pid,
            request: requestVector
        });

        const labels = {
            GRANTED: "Request granted",
            WAIT: "Request must wait",
            UNSAFE: "Request denied: unsafe state",
            INVALID: "Invalid request"
        };

        showResult(
            labels[result.result] || result.result,
            result.reason,
            result.result === "GRANTED" ? "success" :
                result.result === "WAIT" ? "warning" : "error"
        );

        addActivity(pid, requestVector, result.result, result.reason);
        requestCount++;
        elements.requestCount.textContent = requestCount;

        // A granted request changes the state. Other decisions leave it unchanged.
        renderState(result.state);

    } catch (error) {
        showResult("Connection error", error.message, "error");
    }
});

elements.requestForm.addEventListener("reset", () => {
    window.setTimeout(() => {
        elements.requestInputs.forEach(input => { input.value = 0; });
    }, 0);
});

elements.clearLog.addEventListener("click", () => {
    activityLog = [];
    renderActivity();
});

elements.allocationTable.addEventListener("click", async (event) => {
    const button = event.target.closest(".release-btn");
    if (!button) return;

    const pid = Number(button.dataset.pid);

    try {
        const result = await apiPost("/api/release", { ...statePayload(), pid });

        showResult(
            "Resources released",
            `P${pid} returned (${result.released.join(", ")}) to the available pool.`,
            "success"
        );

        addActivity(pid, result.released, "RELEASED",
                    "process finished and returned its resources");
        renderState(result.state);
    } catch (error) {
        showResult("Release failed", error.message, "error");
    }
});

async function initialize() {
    try {
        populateProcessSelect(currentState.n);
        await refreshSafety();
        renderActivity();
        showResult(
            "Simulator ready",
            "The C Banker’s Algorithm is connected. Submit a resource request to test it.",
            "success"
        );
    } catch (error) {
        showResult(
            "Backend connection failed",
            "Make sure Flask is running on port 5000. " + error.message,
            "error"
        );
    }
}

initialize();
