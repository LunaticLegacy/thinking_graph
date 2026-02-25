const state = {
    selectedNodeId: null,
    selectedConnectionId: null,
    nodes: [],
    connections: [],
    savedGraphs: [],
};

const nodesDataset = new vis.DataSet([]);
const edgesDataset = new vis.DataSet([]);

const networkContainer = document.getElementById("network");
const network = new vis.Network(
    networkContainer,
    { nodes: nodesDataset, edges: edgesDataset },
    {
        autoResize: true,
        nodes: {
            shape: "dot",
            scaling: { min: 14, max: 44 },
            font: {
                face: "Space Grotesk",
                color: "#1f2c34",
                size: 16,
            },
            borderWidth: 2,
            shadow: true,
        },
        edges: {
            smooth: {
                type: "dynamic",
                forceDirection: "horizontal",
                roundness: 0.4,
            },
            font: {
                face: "Space Grotesk",
                size: 10,
                color: "#495057",
                strokeWidth: 0,
            },
            arrows: {
                to: { enabled: true, scaleFactor: 0.7 },
            },
        },
        interaction: {
            hover: true,
            navigationButtons: true,
            keyboard: true,
        },
        physics: {
            barnesHut: {
                gravitationalConstant: -3200,
                springLength: 170,
                springConstant: 0.045,
                damping: 0.12,
            },
            stabilization: { iterations: 120 },
        },
    }
);

let networkKeyboardEnabled = true;

function showMessage(message, isError = false) {
    const tip = document.getElementById("selection-tip");
    if (!tip) {
        return;
    }
    // 尝试使用国际化消息，如果找不到则使用原始消息
    tip.textContent = message || "";
    tip.style.color = isError ? "#ca553d" : "#5f6f7c";
}

function currentLanguage() {
    if (typeof i18n !== "undefined" && typeof i18n.getCurrentLanguage === "function") {
        return i18n.getCurrentLanguage();
    }
    return "zh";
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
            "X-Actor": "web-ui",
            ...(options.headers || {}),
        },
        ...options,
    });

    let payload = {};
    try {
        payload = await response.json();
    } catch (_error) {
        payload = {};
    }

    if (!response.ok) {
        const errorMsg = payload.error || 
            (i18n ? i18n.t('errors.requestFailed', { status: response.status }) : `Request failed with status ${response.status}`);
        throw new Error(errorMsg);
    }

    return payload;
}

function setNetworkKeyboardEnabled(enabled) {
    if (networkKeyboardEnabled === enabled) {
        return;
    }
    networkKeyboardEnabled = enabled;
    network.setOptions({ interaction: { keyboard: enabled } });
}

function isTextInputLikeElement(element) {
    if (!(element instanceof HTMLElement)) {
        return false;
    }

    if (element.isContentEditable) {
        return true;
    }

    const tag = element.tagName.toLowerCase();
    if (tag === "textarea" || tag === "select") {
        return true;
    }

    if (tag !== "input") {
        return false;
    }

    const type = (element.getAttribute("type") || "text").toLowerCase();
    return !["button", "checkbox", "radio", "submit", "reset"].includes(type);
}

function isValidHexColor(value) {
    return /^#([0-9a-fA-F]{6})$/.test(value || "");
}

function setColorInputValue(value) {
    const colorInput = document.getElementById("node-color");
    if (!colorInput) {
        return;
    }
    if (isValidHexColor(value)) {
        colorInput.value = value;
        return;
    }
    colorInput.value = "#157f83";
}

function nodeDisplayLabel(node, index) {
    const base = node.summary || node.content.slice(0, 28);
    return `${index + 1}. ${base}`;
}

function renderGraph(visualization) {
    const nodeItems = (visualization.nodes || []).map((node) => ({
        id: node.id,
        label: node.label,
        title: node.title,
        value: node.value,
        color: node.color,
        x: node.x,
        y: node.y,
    }));

    const edgeItems = (visualization.edges || []).map((edge) => ({
        id: edge.id,
        from: edge.source,
        to: edge.target,
        label: edge.label,
        title: edge.title,
        width: edge.width,
        color: { color: edge.color },
        arrows: "to",
    }));

    nodesDataset.clear();
    edgesDataset.clear();
    nodesDataset.add(nodeItems);
    edgesDataset.add(edgeItems);
}

function refreshSelectors() {
    const sourceSelect = document.getElementById("source-node");
    const targetSelect = document.getElementById("target-node");
    if (!sourceSelect || !targetSelect) {
        return;
    }

    sourceSelect.innerHTML = "";
    targetSelect.innerHTML = "";

    state.nodes.forEach((node, index) => {
        const label = nodeDisplayLabel(node, index);

        const sourceOption = document.createElement("option");
        sourceOption.value = node.id;
        sourceOption.textContent = label;
        sourceSelect.appendChild(sourceOption);

        const targetOption = document.createElement("option");
        targetOption.value = node.id;
        targetOption.textContent = label;
        targetSelect.appendChild(targetOption);
    });
}

function renderAudits(audits) {
    const list = document.getElementById("audit-list");
    if (!list) {
        return;
    }

    list.innerHTML = "";

    for (const audit of audits) {
        const item = document.createElement("li");
        const action = (audit.action || "").toUpperCase();
        const entityType = audit.entity_type || "-";
        const entityId = (audit.entity_id || "").slice(0, 8);
        const actor = audit.actor || "-";
        item.textContent = i18n
            ? i18n.t("auditPanel.recordItem", { action, entityType, entityId, actor })
            : `${action} ${entityType} ${entityId} by ${actor}`;
        list.appendChild(item);
    }

    if (!audits.length) {
        const item = document.createElement("li");
        item.textContent = i18n ? i18n.t("auditPanel.noRecords") : "No audit records";
        list.appendChild(item);
    }
}

async function loadAudits() {
    const data = await api("/api/audits?limit=24");
    renderAudits(data.audits || []);
}

function renderSavedGraphs(graphs, preferredName = null) {
    const select = document.getElementById("saved-graphs");
    if (!select) {
        return;
    }

    const previous = preferredName || select.value;
    select.innerHTML = "";

    for (const graph of graphs) {
        const option = document.createElement("option");
        option.value = graph.name;
        option.textContent = `${graph.name} (${graph.node_count}N/${graph.connection_count}E)`;
        select.appendChild(option);
    }

    if (!graphs.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = i18n ? i18n.t("saveLoadPanel.noGraphs") : "No saved graphs";
        select.appendChild(option);
        select.value = "";
        return;
    }

    if (previous && graphs.some((item) => item.name === previous)) {
        select.value = previous;
    } else {
        select.selectedIndex = 0;
    }
}

async function loadSavedGraphs(preferredName = null) {
    const data = await api("/api/graphs/saved");
    state.savedGraphs = data.graphs || [];
    renderSavedGraphs(state.savedGraphs, preferredName);
}

const DEFAULT_NODE_COLOR = "#157f83";
function getDefaultNodeContent() {
    return i18n ? i18n.t("nodePanel.defaultContent") : "New node";
}

function renderAuditBadge(status) {
    const badge = document.getElementById("audit-status");
    if (!badge) {
        return;
    }

    const badgeStatus = status || badge.dataset.status || "unchecked";
    badge.dataset.status = badgeStatus;

    if (badgeStatus === "valid") {
        badge.textContent = i18n ? i18n.t("auditPanel.status.valid") : "Valid";
        badge.style.background = "#d7efe1";
        badge.style.color = "#2d936c";
        return;
    }

    if (badgeStatus === "invalid") {
        badge.textContent = i18n ? i18n.t("auditPanel.status.invalid") : "Invalid";
        badge.style.background = "#fde4df";
        badge.style.color = "#ca553d";
        return;
    }

    badge.textContent = i18n ? i18n.t("auditPanel.status.unchecked") : "Unchecked";
    badge.style.background = "#ece6dc";
    badge.style.color = "#5f6f7c";
}

function refreshRuntimeI18nText() {
    renderAuditBadge();
    renderSavedGraphs(state.savedGraphs || [], document.getElementById("saved-graphs")?.value || null);

    if (state.selectedNodeId) {
        const selectedNode = state.nodes.find((item) => item.id === state.selectedNodeId);
        if (selectedNode) {
            updateNodeFormModeHint(selectedNode);
        } else {
            updateNodeFormModeHint(null);
        }
    } else {
        updateNodeFormModeHint(null);
    }

    if (state.selectedNodeId) {
        const msg = i18n
            ? i18n.t("messages.nodeSelected", { nodeId: state.selectedNodeId.slice(0, 8) })
            : `Selected node: ${state.selectedNodeId.slice(0, 8)}`;
        showMessage(msg);
    } else if (state.selectedConnectionId) {
        const msg = i18n
            ? i18n.t("messages.connectionSelected", { connectionId: state.selectedConnectionId.slice(0, 8) })
            : `Selected connection: ${state.selectedConnectionId.slice(0, 8)}`;
        showMessage(msg);
    } else {
        showMessage(i18n ? i18n.t("canvasPanel.selectionTip") : "Click blank space to create a node. Click a node to edit its attributes.");
    }
}

function getNodeFormElements() {
    const form = document.getElementById("node-form");
    return {
        form,
        contentInput: document.getElementById("node-content"),
        summaryInput: document.getElementById("node-summary"),
        confidenceInput: document.getElementById("node-confidence"),
        colorInput: document.getElementById("node-color"),
        submitButton: form ? form.querySelector('button[type="submit"]') : null,
        modeHint: document.getElementById("node-form-mode"),
    };
}

function getNodeFormValues({ fallbackContent = "" } = {}) {
    const { contentInput, summaryInput, confidenceInput, colorInput } = getNodeFormElements();
    const rawContent = contentInput ? contentInput.value.trim() : "";
    const confidenceRaw = Number(confidenceInput ? confidenceInput.value : "1");

    return {
        content: rawContent || fallbackContent,
        summary: summaryInput ? summaryInput.value.trim() : "",
        confidence: Number.isFinite(confidenceRaw)
            ? Math.min(Math.max(confidenceRaw, 0), 1)
            : 1,
        color: (colorInput ? colorInput.value : DEFAULT_NODE_COLOR).trim() || DEFAULT_NODE_COLOR,
    };
}

function updateNodeFormModeHint(selectedNode = null) {
    const { submitButton, modeHint } = getNodeFormElements();
    if (selectedNode) {
        if (submitButton) {
            submitButton.textContent = i18n ? i18n.t('nodePanel.editNode', { nodeId: selectedNode.id.slice(0, 8) }) : "Update selected node";
        }
        if (modeHint) {
            modeHint.textContent = i18n ? i18n.t('messages.nodeEdited', { nodeId: selectedNode.id.slice(0, 8) }) : `Editing node ${selectedNode.id.slice(0, 8)}. Submitting the form updates this node.`;
        }
        return;
    }

    if (submitButton) {
        submitButton.textContent = i18n ? i18n.t('nodePanel.createNode') : "Create node";
    }
    if (modeHint) {
        modeHint.textContent = i18n ? i18n.t('messages.nodeCreatedBlank') : "Click blank canvas to create a node. Select a node, then submit the form to update it.";
    }
}

function resetNodeFormToCreateDefaults() {
    const { form, confidenceInput } = getNodeFormElements();
    if (form) {
        form.reset();
    }
    if (confidenceInput) {
        confidenceInput.value = "1";
    }
    setColorInputValue(DEFAULT_NODE_COLOR);
    updateNodeFormModeHint(null);
}

function syncNodeFormFromSelection() {
    if (!state.selectedNodeId) {
        updateNodeFormModeHint(null);
        return;
    }
    const selectedNode = state.nodes.find((item) => item.id === state.selectedNodeId);
    if (!selectedNode) {
        updateNodeFormModeHint(null);
        return;
    }

    const { contentInput, summaryInput, confidenceInput } = getNodeFormElements();
    if (contentInput) {
        contentInput.value = selectedNode.content || "";
    }
    if (summaryInput) {
        summaryInput.value = selectedNode.summary || "";
    }
    if (confidenceInput) {
        confidenceInput.value = String(selectedNode.confidence ?? 1);
    }
    setColorInputValue(selectedNode.color);
    updateNodeFormModeHint(selectedNode);
}

async function createNodeFromForm({
    position = null,
    reason = "created in web form",
    fallbackContent = "",
} = {}) {
    const payload = getNodeFormValues({ fallbackContent });

    if (!payload.content) {
        showMessage(i18n ? i18n.t('messages.nodeRequired') : "Node content is required.", true);
        return null;
    }
    if (!isValidHexColor(payload.color)) {
        const msg = i18n ? i18n.t('messages.invalidColor') : "Node color must be a valid hex color (for example #157f83).";
        showMessage(msg, true);
        return null;
    }

    if (
        position
        && Number.isFinite(position.x)
        && Number.isFinite(position.y)
    ) {
        payload.position = { x: Number(position.x), y: Number(position.y) };
    }

    payload.reason = reason;
    return api("/api/nodes", {
        method: "POST",
        body: JSON.stringify(payload),
    });
}

async function loadGraph(options = {}) {
    const preferredNodeId = options.preferredNodeId || null;
    const preferredConnectionId = options.preferredConnectionId || null;

    const snapshot = await api("/api/graph");
    state.nodes = snapshot.nodes || [];
    state.connections = snapshot.connections || [];

    renderGraph(snapshot.visualization || { nodes: [], edges: [] });
    refreshSelectors();

    const keepNodeSelection = (
        !!preferredNodeId
        && state.nodes.some((item) => item.id === preferredNodeId)
    );
    const keepConnectionSelection = (
        !!preferredConnectionId
        && state.connections.some((item) => item.id === preferredConnectionId)
    );

    state.selectedNodeId = keepNodeSelection ? preferredNodeId : null;
    state.selectedConnectionId = (
        state.selectedNodeId ? null : (keepConnectionSelection ? preferredConnectionId : null)
    );

    if (state.selectedNodeId) {
        syncNodeFormFromSelection();
        const msg = i18n ? i18n.t('messages.nodeSelected', { nodeId: state.selectedNodeId.slice(0, 8) }) : `Selected node: ${state.selectedNodeId.slice(0, 8)}`;
        showMessage(msg);
    } else if (state.selectedConnectionId) {
        updateNodeFormModeHint(null);
        const msg = i18n ? i18n.t('messages.connectionSelected', { connectionId: state.selectedConnectionId.slice(0, 8) }) : `Selected connection: ${state.selectedConnectionId.slice(0, 8)}`;
        showMessage(msg);
    } else {
        updateNodeFormModeHint(null);
        showMessage(i18n ? i18n.t("canvasPanel.selectionTip") : "Click blank space to create a node. Click a node to edit its attributes.");
    }

    await Promise.all([loadAudits(), loadSavedGraphs()]);
}

network.on("click", async (params) => {
    if (params.nodes.length > 0) {
        state.selectedNodeId = params.nodes[0];
        state.selectedConnectionId = null;
        syncNodeFormFromSelection();
        const msg = i18n ? i18n.t('messages.nodeSelected', { nodeId: state.selectedNodeId.slice(0, 8) }) : `Selected node: ${state.selectedNodeId.slice(0, 8)}`;
        showMessage(msg);
        return;
    }

    if (params.edges.length > 0) {
        state.selectedNodeId = null;
        state.selectedConnectionId = params.edges[0];
        updateNodeFormModeHint(null);
        const msg = i18n ? i18n.t('messages.connectionSelected', { connectionId: state.selectedConnectionId.slice(0, 8) }) : `Selected connection: ${state.selectedConnectionId.slice(0, 8)}`;
        showMessage(msg);
        return;
    }

    try {
        const created = await createNodeFromForm({
            position: params.pointer && params.pointer.canvas ? params.pointer.canvas : null,
            reason: "created by blank canvas click",
            fallbackContent: getDefaultNodeContent(),
        });
        if (!created || !created.id) {
            return;
        }

        resetNodeFormToCreateDefaults();
        await loadGraph({ preferredNodeId: created.id });
        const msg = i18n ? i18n.t('messages.nodeCreated', { nodeId: created.id.slice(0, 8) }) : `Created node: ${created.id.slice(0, 8)}`;
        showMessage(msg);
    } catch (error) {
        showMessage(error.message, true);
    }
});

network.on("dragEnd", async (params) => {
    if (!params.nodes.length) {
        return;
    }

    const nodeId = params.nodes[0];
    const pos = network.getPositions([nodeId])[nodeId];

    try {
        await api(`/api/nodes/${nodeId}`, {
            method: "PATCH",
            body: JSON.stringify({
                position: { x: pos.x, y: pos.y },
                reason: "drag node in graph",
            }),
        });
    } catch (error) {
        showMessage(error.message, true);
    }
});

document.addEventListener("focusin", (event) => {
    if (isTextInputLikeElement(event.target)) {
        setNetworkKeyboardEnabled(false);
    }
});

document.addEventListener("focusout", () => {
    const active = document.activeElement;
    if (!isTextInputLikeElement(active)) {
        setNetworkKeyboardEnabled(true);
    }
});

const nodeForm = document.getElementById("node-form");
if (nodeForm) {
    nodeForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const payload = getNodeFormValues();
        if (!payload.content) {
            const msg = i18n ? i18n.t('messages.nodeRequired') : "Node content is required.";
            showMessage(msg, true);
            return;
        }
        if (!isValidHexColor(payload.color)) {
            const msg = i18n ? i18n.t('messages.invalidColor') : "Node color must be a valid hex color (for example #157f83).";
            showMessage(msg, true);
            return;
        }

        try {
            if (state.selectedNodeId) {
                const nodeId = state.selectedNodeId;
                await api(`/api/nodes/${nodeId}`, {
                    method: "PATCH",
                    body: JSON.stringify({
                        content: payload.content,
                        summary: payload.summary,
                        confidence: payload.confidence,
                        color: payload.color,
                        reason: "update selected node attributes in web form",
                    }),
                });
                await loadGraph({ preferredNodeId: nodeId });
                const msg = i18n ? i18n.t('messages.nodeUpdated') : "Updated selected node attributes.";
                showMessage(msg);

                return;
            }

            const created = await createNodeFromForm({
                reason: "created in web form",
            });
            if (!created || !created.id) {
                return;
            }

            resetNodeFormToCreateDefaults();
            await loadGraph({ preferredNodeId: created.id });
            const msg = i18n ? i18n.t('messages.nodeCreated', { nodeId: created.id.slice(0, 8) }) : `Created node: ${created.id.slice(0, 8)}`;
            showMessage(msg);

        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const connectionForm = document.getElementById("connection-form");
if (connectionForm) {
    connectionForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const source_id = document.getElementById("source-node").value;
        const target_id = document.getElementById("target-node").value;
        const conn_type = document.getElementById("conn-type").value;
        const description = document.getElementById("conn-description").value;

        try {
            await api("/api/connections", {
                method: "POST",
                body: JSON.stringify({
                    source_id,
                    target_id,
                    conn_type,
                    description,
                    reason: "created in web form",
                }),
            });
            event.target.reset();
            await loadGraph();
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

async function stabilizeNetworkLayout(iterations = 320, timeoutMs = 2800) {
    await new Promise((resolve) => {
        let settled = false;
        const finish = () => {
            if (settled) {
                return;
            }
            settled = true;
            resolve();
        };

        const timer = window.setTimeout(() => {
            finish();
        }, timeoutMs);

        network.once("stabilizationIterationsDone", () => {
            window.clearTimeout(timer);
            finish();
        });

        network.stabilize(iterations);
    });
}

async function persistCurrentNodePositions(reason) {
    const nodeIds = state.nodes.map((node) => node.id);
    if (!nodeIds.length) {
        return { updated: 0, failed: 0 };
    }

    const positions = network.getPositions(nodeIds);
    const results = await Promise.all(
        nodeIds.map(async (nodeId) => {
            try {
                const pos = positions[nodeId];
                await api(`/api/nodes/${nodeId}`, {
                    method: "PATCH",
                    body: JSON.stringify({
                        position: { x: Number(pos.x), y: Number(pos.y) },
                        reason,
                    }),
                });
                return true;
            } catch (_error) {
                return false;
            }
        })
    );

    const updated = results.filter(Boolean).length;
    return { updated, failed: nodeIds.length - updated };
}

const tidyGraphButton = document.getElementById("tidy-graph");
if (tidyGraphButton) {
    tidyGraphButton.addEventListener("click", async () => {
        if (!state.nodes.length) {
            const msg = i18n ? i18n.t('messages.noNodesToTidy') : "No nodes to tidy.";
            showMessage(msg, true);
            return;
        }

        const previousSelectedNodeId = state.selectedNodeId;
        const originalText = tidyGraphButton.textContent;
        tidyGraphButton.disabled = true;
        tidyGraphButton.textContent = i18n ? i18n.t('messages.tidying') : "Tidying...";

        try {
            await stabilizeNetworkLayout();
            const stats = await persistCurrentNodePositions("tidy graph layout in web ui");
            await loadGraph({ preferredNodeId: previousSelectedNodeId });
            network.fit({
                animation: {
                    duration: 420,
                    easingFunction: "easeInOutQuad",
                },
            });

            if (stats.failed > 0) {
                const msg = i18n ? i18n.t('messages.layoutTidiedWithErrors', { failed: stats.failed }) : `Layout tidied, but ${stats.failed} node positions failed to save.`;
                showMessage(msg, true);
            } else {
                const msg = i18n ? i18n.t('messages.layoutTidied', { count: stats.updated }) : `Layout tidied and saved (${stats.updated} nodes).`;
                showMessage(msg);
            }
        } catch (error) {
            showMessage(error.message, true);
        } finally {
            tidyGraphButton.disabled = false;
            tidyGraphButton.textContent = originalText;
        }
    });
}

const deleteNodeButton = document.getElementById("delete-node");
if (deleteNodeButton) {
    deleteNodeButton.addEventListener("click", async () => {
        if (!state.selectedNodeId) {
            const msg = i18n ? i18n.t('messages.noNodeSelected') : "Please select a node first.";
            showMessage(msg, true);
            return;
        }

        try {
            await api(`/api/nodes/${state.selectedNodeId}`, {
                method: "DELETE",
                body: JSON.stringify({ reason: "delete from web action" }),
            });
            await loadGraph();
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const deleteConnectionButton = document.getElementById("delete-connection");
if (deleteConnectionButton) {
    deleteConnectionButton.addEventListener("click", async () => {
        if (!state.selectedConnectionId) {
            const msg = i18n ? i18n.t('messages.noConnectionSelected') : "Please select a connection first.";
            showMessage(msg, true);
            return;
        }

        try {
            await api(`/api/connections/${state.selectedConnectionId}`, {
                method: "DELETE",
                body: JSON.stringify({ reason: "delete from web action" }),
            });
            await loadGraph();
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const updateNodeColorButton = document.getElementById("update-node-color");
if (updateNodeColorButton) {
    updateNodeColorButton.addEventListener("click", async () => {
        if (!state.selectedNodeId) {
            const msg = i18n ? i18n.t('messages.noNodeSelected') : "Please select a node first.";
            showMessage(msg, true);
            return;
        }

        const color = document.getElementById("node-color").value;
        if (!isValidHexColor(color)) {
            const msg = i18n ? i18n.t('messages.invalidColor') : "Node color must be a valid hex color.";
            showMessage(msg, true);
            return;
        }

        try {
            const nodeId = state.selectedNodeId;
            await api(`/api/nodes/${nodeId}`, {
                method: "PATCH",
                body: JSON.stringify({
                    color,
                    reason: "update node color in web ui",
                }),
            });
            await loadGraph({ preferredNodeId: nodeId });
            const msg = i18n ? i18n.t("messages.nodeColorUpdated") : "Updated selected node color.";
            showMessage(msg);
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const graphSaveForm = document.getElementById("graph-save-form");
if (graphSaveForm) {
    graphSaveForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const input = document.getElementById("save-graph-name");
        const name = input.value.trim();

        if (!name) {
            const msg = i18n ? i18n.t('messages.snapshotNameRequired') : "Please enter a snapshot name.";
            showMessage(msg, true);
            return;
        }

        try {
            const result = await api("/api/graphs/save", {
                method: "POST",
                body: JSON.stringify({
                    name,
                    reason: "manual save in web ui",
                }),
            });
            await loadSavedGraphs(result.name);
            const msg = i18n ? i18n.t('messages.graphSaved', { name: result.name }) : `Saved graph: ${result.name}`;
            showMessage(msg);

        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const loadGraphButton = document.getElementById("load-graph");
if (loadGraphButton) {
    loadGraphButton.addEventListener("click", async () => {
        const select = document.getElementById("saved-graphs");
        const name = (select.value || "").trim();

        if (!name) {
            const msg = i18n ? i18n.t('messages.noGraphSelected') : "Please choose a saved graph first.";
            showMessage(msg, true);
            return;
        }

        try {
            const result = await api("/api/graphs/load", {
                method: "POST",
                body: JSON.stringify({
                    name,
                    reason: "manual load in web ui",
                }),
            });
            await loadGraph();
            const msg = i18n ? i18n.t('messages.graphLoaded', { name: result.name }) : `Loaded graph: ${result.name}`;
            showMessage(msg);

        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const deleteSavedGraphButton = document.getElementById("delete-saved-graph");
if (deleteSavedGraphButton) {
    deleteSavedGraphButton.addEventListener("click", async () => {
        const select = document.getElementById("saved-graphs");
        const name = (select.value || "").trim();

        if (!name) {
            const msg = i18n ? i18n.t('messages.noGraphSelected') : "Please choose a saved graph first.";
            showMessage(msg, true);
            return;
        }

        const confirmed = window.confirm(
            i18n ? i18n.t('messages.confirmDelete', { name: name }) : `Delete saved graph "${name}"?`
        );
        if (!confirmed) {
            return;
        }

        try {
            const result = await api("/api/graphs/delete", {
                method: "POST",
                body: JSON.stringify({
                    name,
                    reason: "manual delete saved graph in web ui",
                }),
            });
            await loadSavedGraphs();
            const msg = i18n ? i18n.t("messages.graphDeleted", { name: result.name }) : `Deleted graph: ${result.name}`;
            showMessage(msg);
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const clearGraphButton = document.getElementById("clear-graph");
if (clearGraphButton) {
    clearGraphButton.addEventListener("click", async () => {
        const confirmed = window.confirm(
            i18n
                ? i18n.t("messages.clearGraphConfirm")
                : "Clear the current graph? This action will be recorded in audit logs."
        );
        if (!confirmed) {
            return;
        }

        try {
            const result = await api("/api/graphs/clear", {
                method: "POST",
                body: JSON.stringify({
                    reason: "manual clear in web ui",
                }),
            });
            await loadGraph();
            const msg = i18n
                ? i18n.t("messages.graphCleared", {
                    nodes: result.cleared_nodes,
                    connections: result.cleared_connections,
                })
                : `Cleared current graph: ${result.cleared_nodes} nodes / ${result.cleared_connections} connections`;
            showMessage(msg);
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const exportGraphButton = document.getElementById("export-graph");
if (exportGraphButton) {
    exportGraphButton.addEventListener("click", async () => {
        try {
            const result = await api("/api/graphs/export");
            const payloadText = JSON.stringify(result, null, 2);
            const blob = new Blob([payloadText], { type: "application/json;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = result.suggested_file_name || "thinking-graph-export.json";
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);

            const msg = i18n
                ? i18n.t("messages.graphExported", {
                    nodes: result.node_count || 0,
                    connections: result.connection_count || 0,
                })
                : `Exported graph: ${result.node_count || 0} nodes / ${result.connection_count || 0} connections`;
            showMessage(msg);
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const importGraphFileInput = document.getElementById("import-graph-file");
const importGraphButton = document.getElementById("import-graph");
if (importGraphButton && importGraphFileInput) {
    importGraphButton.addEventListener("click", () => {
        importGraphFileInput.click();
    });

    importGraphFileInput.addEventListener("change", async (event) => {
        const file = event.target.files && event.target.files[0];
        if (!file) {
            return;
        }

        const confirmed = window.confirm(
            i18n
                ? i18n.t("messages.importGraphConfirm")
                : "Importing a graph will replace the current graph. Continue?"
        );
        if (!confirmed) {
            event.target.value = "";
            return;
        }

        try {
            const rawText = await file.text();
            let parsed;
            try {
                parsed = JSON.parse(rawText);
            } catch (_error) {
                throw new Error(i18n ? i18n.t("messages.invalidJsonFile") : "Invalid JSON file.");
            }

            const result = await api("/api/graphs/import", {
                method: "POST",
                body: JSON.stringify({
                    graph: parsed,
                    reason: `manual import in web ui: ${file.name}`,
                }),
            });
            await loadGraph();
            const msg = i18n
                ? i18n.t("messages.graphImported", {
                    nodes: result.node_count || 0,
                    connections: result.connection_count || 0,
                })
                : `Imported graph: ${result.node_count || 0} nodes / ${result.connection_count || 0} connections`;
            showMessage(msg);
        } catch (error) {
            showMessage(error.message, true);
        } finally {
            event.target.value = "";
        }
    });
}

const refreshSavedButton = document.getElementById("refresh-saved");
if (refreshSavedButton) {
    refreshSavedButton.addEventListener("click", async () => {
        try {
            await loadSavedGraphs();
            const msg = i18n ? i18n.t("messages.savedGraphListRefreshed") : "Saved graph list refreshed.";
            showMessage(msg);
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const verifyAuditButton = document.getElementById("verify-audit");
if (verifyAuditButton) {
    verifyAuditButton.addEventListener("click", async () => {
        try {
            const status = await api("/api/audits/verify");
            const badge = document.getElementById("audit-status");
            const issuesEl = document.getElementById("audit-issues");
            if (!badge || !issuesEl) {
                return;
            }
            issuesEl.innerHTML = "";

            if (status.ok) {
                renderAuditBadge("valid");
                const item = document.createElement("li");
                item.textContent = i18n
                    ? i18n.t("auditPanel.allChainsComplete")
                    : "All nodes and connections have complete audit chains.";
                issuesEl.appendChild(item);
            } else {
                renderAuditBadge("invalid");
                for (const issue of status.issues || []) {
                    const item = document.createElement("li");
                    item.textContent = issue;
                    issuesEl.appendChild(item);
                }
            }
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const llmForm = document.getElementById("llm-form");
if (llmForm) {
    llmForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const language = currentLanguage();
        const prompt = document.getElementById("llm-prompt").value;
        const output = document.getElementById("llm-response");
        output.textContent = i18n ? i18n.t("auditPanel.requesting") : "Requesting...";

        try {
            const result = await api("/api/llm/chat", {
                method: "POST",
                body: JSON.stringify({
                    prompt,
                    system_prompt: language === "en"
                        ? "You are a structured-thinking assistant. Answer concisely in English."
                        : "你是结构化思考助手。请用中文简洁回答。",
                    temperature: 0.3,
                    language,
                }),
            });
            output.textContent = result.response || (i18n ? i18n.t("auditPanel.emptyResponse") : "(empty response)");
        } catch (error) {
            output.textContent = error.message;
        }
    });
}

const llmReviewGraphButton = document.getElementById("llm-review-graph");
if (llmReviewGraphButton) {
    llmReviewGraphButton.addEventListener("click", async () => {
        const language = currentLanguage();
        const output = document.getElementById("llm-review-response");
        output.textContent = i18n ? i18n.t("auditPanel.reviewing") : "Reviewing...";

        try {
            const result = await api("/api/llm/review-graph", {
                method: "POST",
                body: JSON.stringify({ language }),
            });

            if ((result.verdict || "").toUpperCase() === "OK") {
                output.textContent = i18n ? i18n.t("auditPanel.ok") : "OK";
                return;
            }

            const rows = [];
            for (const item of result.conflicts || []) {
                const type = item.entity_type || (i18n ? i18n.t("auditPanel.globalScope") : "global");
                const id = item.entity_id || (i18n ? i18n.t("auditPanel.globalScope") : "global");
                const reason = item.reason || (i18n ? i18n.t("auditPanel.noReason") : "No reason provided.");
                rows.push(`[${type}] ${id}: ${reason}`);
            }

            if (rows.length) {
                output.textContent = rows.join("\n");
            } else {
                output.textContent = result.response || (i18n ? i18n.t("auditPanel.conflictsDetected") : "Conflicts detected.");
            }
        } catch (error) {
            output.textContent = error.message;
        }
    });
}

const llmGenerateForm = document.getElementById("llm-generate-form");
if (llmGenerateForm) {
    llmGenerateForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const language = currentLanguage();
        const topic = (document.getElementById("llm-generate-topic").value || "").trim();
        const output = document.getElementById("llm-generate-response");

        if (!topic) {
            output.textContent = i18n ? i18n.t("auditPanel.topicRequired") : "Please enter a topic first.";
            return;
        }

        const confirmed = window.confirm(
            i18n
                ? i18n.t("auditPanel.confirmOverwrite")
                : "This will replace the current graph and discard unsaved changes. Continue?"
        );
        if (!confirmed) {
            output.textContent = i18n ? i18n.t("auditPanel.cancelled") : "Cancelled.";
            return;
        }

        output.textContent = i18n ? i18n.t("auditPanel.generating") : "Generating...";

        try {
            const result = await api("/api/llm/generate-graph", {
                method: "POST",
                body: JSON.stringify({
                    topic,
                    temperature: 0.2,
                    max_tokens: 1400,
                    max_nodes: 18,
                    language,
                }),
            });

            if (!result.enabled) {
                output.textContent = result.message || (i18n ? i18n.t("auditPanel.llmUnavailable") : "LLM backend is unavailable.");
                return;
            }

            await loadGraph();
            output.textContent = i18n
                ? i18n.t("auditPanel.generatedResult", {
                    nodes: result.node_count,
                    connections: result.connection_count,
                })
                : `Generated and replaced graph: ${result.node_count} nodes / ${result.connection_count} connections`;
            showMessage(i18n ? i18n.t("messages.llmGeneratedReplaced") : "LLM generated and replaced the current graph.");
        } catch (error) {
            output.textContent = error.message;
        }
    });
}

const refreshAllButton = document.getElementById("refresh-all");
if (refreshAllButton) {
    refreshAllButton.addEventListener("click", async () => {
        try {
            await loadGraph();
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

setColorInputValue(DEFAULT_NODE_COLOR);

document.addEventListener("i18n:changed", () => {
    refreshRuntimeI18nText();
});

if (typeof i18n !== "undefined" && i18n.ready && typeof i18n.ready.then === "function") {
    i18n.ready
        .catch(() => {})
        .finally(() => {
            refreshRuntimeI18nText();
            loadGraph().catch((error) => {
                showMessage(error.message, true);
            });
        });
} else {
    loadGraph().catch((error) => {
        showMessage(error.message, true);
    });
}
