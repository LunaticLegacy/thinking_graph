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
    tip.textContent = message;
    tip.style.color = isError ? "#ca553d" : "#5f6f7c";
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
        throw new Error(payload.error || `Request failed with status ${response.status}`);
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
        item.textContent = `${audit.action.toUpperCase()} ${audit.entity_type} ${audit.entity_id.slice(0, 8)} by ${audit.actor}`;
        list.appendChild(item);
    }

    if (!audits.length) {
        const item = document.createElement("li");
        item.textContent = "暂无审计记录";
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
        option.textContent = "暂无已保存思考图";
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

function syncColorInputFromSelection() {
    if (!state.selectedNodeId) {
        return;
    }
    const selectedNode = state.nodes.find((item) => item.id === state.selectedNodeId);
    if (!selectedNode) {
        return;
    }
    setColorInputValue(selectedNode.color);
}

async function loadGraph() {
    const snapshot = await api("/api/graph");
    state.nodes = snapshot.nodes || [];
    state.connections = snapshot.connections || [];

    renderGraph(snapshot.visualization || { nodes: [], edges: [] });
    refreshSelectors();

    state.selectedNodeId = null;
    state.selectedConnectionId = null;
    showMessage("点击节点或连接查看并操作");

    await Promise.all([loadAudits(), loadSavedGraphs()]);
}

network.on("click", (params) => {
    if (params.nodes.length > 0) {
        state.selectedNodeId = params.nodes[0];
        state.selectedConnectionId = null;
        syncColorInputFromSelection();
        showMessage(`已选中节点: ${state.selectedNodeId.slice(0, 8)}`);
        return;
    }

    if (params.edges.length > 0) {
        state.selectedNodeId = null;
        state.selectedConnectionId = params.edges[0];
        showMessage(`已选中连接: ${state.selectedConnectionId.slice(0, 8)}`);
        return;
    }

    state.selectedNodeId = null;
    state.selectedConnectionId = null;
    showMessage("未选中元素");
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

        const content = document.getElementById("node-content").value;
        const summary = document.getElementById("node-summary").value;
        const confidence = Number(document.getElementById("node-confidence").value);
        const color = document.getElementById("node-color").value;

        try {
            await api("/api/nodes", {
                method: "POST",
                body: JSON.stringify({
                    content,
                    summary,
                    confidence,
                    color,
                    reason: "created in web form",
                }),
            });
            event.target.reset();
            document.getElementById("node-confidence").value = "1";
            setColorInputValue("#157f83");
            await loadGraph();
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

const deleteNodeButton = document.getElementById("delete-node");
if (deleteNodeButton) {
    deleteNodeButton.addEventListener("click", async () => {
        if (!state.selectedNodeId) {
            showMessage("请先选中一个节点", true);
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
            showMessage("请先选中一条连接", true);
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
            showMessage("请先选中一个节点", true);
            return;
        }

        const color = document.getElementById("node-color").value;
        if (!isValidHexColor(color)) {
            showMessage("节点颜色格式无效", true);
            return;
        }

        try {
            await api(`/api/nodes/${state.selectedNodeId}`, {
                method: "PATCH",
                body: JSON.stringify({
                    color,
                    reason: "update node color in web ui",
                }),
            });
            await loadGraph();
            showMessage("已更新节点颜色");
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
            showMessage("请输入快照名称", true);
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
            showMessage(`已保存思考图: ${result.name}`);
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
            showMessage("请先选择一个已保存思考图", true);
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
            showMessage(`已加载思考图: ${result.name}`);
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
            showMessage("请先选择一个已保存思考图", true);
            return;
        }

        const confirmed = window.confirm(`确认删除已保存思考图“${name}”？`);
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
            showMessage(`已删除思考图: ${result.name}`);
        } catch (error) {
            showMessage(error.message, true);
        }
    });
}

const clearGraphButton = document.getElementById("clear-graph");
if (clearGraphButton) {
    clearGraphButton.addEventListener("click", async () => {
        const confirmed = window.confirm("确认清空当前思考图？该操作会记录审计日志。");
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
            showMessage(`已清空当前图: ${result.cleared_nodes} 节点 / ${result.cleared_connections} 连接`);
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

            showMessage(`Exported graph: ${result.node_count || 0} nodes / ${result.connection_count || 0} connections`);
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
            "Importing a graph will replace the current graph. Continue?"
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
                throw new Error("Invalid JSON file.");
            }

            const result = await api("/api/graphs/import", {
                method: "POST",
                body: JSON.stringify({
                    graph: parsed,
                    reason: `manual import in web ui: ${file.name}`,
                }),
            });
            await loadGraph();
            showMessage(
                `Imported graph: ${result.node_count || 0} nodes / ${result.connection_count || 0} connections`
            );
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
            showMessage("已刷新已保存思考图列表");
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
                badge.textContent = "通过";
                badge.style.background = "#d7efe1";
                badge.style.color = "#2d936c";
                const item = document.createElement("li");
                item.textContent = "所有节点与连接都具备审计链路";
                issuesEl.appendChild(item);
            } else {
                badge.textContent = "未通过";
                badge.style.background = "#fde4df";
                badge.style.color = "#ca553d";
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

        const prompt = document.getElementById("llm-prompt").value;
        const output = document.getElementById("llm-response");
        output.textContent = "请求中...";

        try {
            const result = await api("/api/llm/chat", {
                method: "POST",
                body: JSON.stringify({
                    prompt,
                    system_prompt: "你是观点结构化助手，输出简洁中文。",
                    temperature: 0.3,
                }),
            });
            output.textContent = result.response || "(空响应)";
        } catch (error) {
            output.textContent = error.message;
        }
    });
}

const llmReviewGraphButton = document.getElementById("llm-review-graph");
if (llmReviewGraphButton) {
    llmReviewGraphButton.addEventListener("click", async () => {
        const output = document.getElementById("llm-review-response");
        output.textContent = "审核中...";

        try {
            const result = await api("/api/llm/review-graph", {
                method: "POST",
                body: JSON.stringify({}),
            });

            if ((result.verdict || "").toUpperCase() === "OK") {
                output.textContent = "OK";
                return;
            }

            const rows = [];
            for (const item of result.conflicts || []) {
                const type = item.entity_type || "global";
                const id = item.entity_id || "global";
                const reason = item.reason || "未提供原因";
                rows.push(`[${type}] ${id}: ${reason}`);
            }

            if (rows.length) {
                output.textContent = rows.join("\n");
            } else {
                output.textContent = result.response || "检测到冲突";
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

        const topic = (document.getElementById("llm-generate-topic").value || "").trim();
        const output = document.getElementById("llm-generate-response");

        if (!topic) {
            output.textContent = "请先输入主题。";
            return;
        }

        const confirmed = window.confirm("该操作会覆盖当前思考图，未保存内容会丢失。是否继续？");
        if (!confirmed) {
            output.textContent = "已取消。";
            return;
        }

        output.textContent = "生成中...";

        try {
            const result = await api("/api/llm/generate-graph", {
                method: "POST",
                body: JSON.stringify({
                    topic,
                    temperature: 0.2,
                    max_tokens: 1400,
                    max_nodes: 18,
                }),
            });

            if (!result.enabled) {
                output.textContent = result.message || "LLM 后端不可用。";
                return;
            }

            await loadGraph();
            output.textContent = `已生成并覆盖当前图：${result.node_count} 节点 / ${result.connection_count} 连接`;
            showMessage("LLM 已生成并覆盖当前思考图");
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

setColorInputValue("#157f83");

loadGraph().catch((error) => {
    showMessage(error.message, true);
});
