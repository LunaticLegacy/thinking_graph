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

function showMessage(message, isError = false) {
    const tip = document.getElementById("selection-tip");
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

    sourceSelect.innerHTML = "";
    targetSelect.innerHTML = "";

    for (const node of state.nodes) {
        const label = node.summary || node.content.slice(0, 28);

        const sourceOption = document.createElement("option");
        sourceOption.value = node.id;
        sourceOption.textContent = label;
        sourceSelect.appendChild(sourceOption);

        const targetOption = document.createElement("option");
        targetOption.value = node.id;
        targetOption.textContent = label;
        targetSelect.appendChild(targetOption);
    }
}

function renderAudits(audits) {
    const list = document.getElementById("audit-list");
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

document.getElementById("node-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const content = document.getElementById("node-content").value;
    const summary = document.getElementById("node-summary").value;
    const confidence = Number(document.getElementById("node-confidence").value);

    try {
        await api("/api/nodes", {
            method: "POST",
            body: JSON.stringify({
                content,
                summary,
                confidence,
                reason: "created in web form",
            }),
        });
        event.target.reset();
        document.getElementById("node-confidence").value = "1";
        await loadGraph();
    } catch (error) {
        showMessage(error.message, true);
    }
});

document.getElementById("connection-form").addEventListener("submit", async (event) => {
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

document.getElementById("delete-node").addEventListener("click", async () => {
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

document.getElementById("delete-connection").addEventListener("click", async () => {
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

document.getElementById("graph-save-form").addEventListener("submit", async (event) => {
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

document.getElementById("load-graph").addEventListener("click", async () => {
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

document.getElementById("clear-graph").addEventListener("click", async () => {
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

document.getElementById("refresh-saved").addEventListener("click", async () => {
    try {
        await loadSavedGraphs();
        showMessage("已刷新已保存思考图列表");
    } catch (error) {
        showMessage(error.message, true);
    }
});

document.getElementById("verify-audit").addEventListener("click", async () => {
    try {
        const status = await api("/api/audits/verify");
        const badge = document.getElementById("audit-status");
        const issuesEl = document.getElementById("audit-issues");
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

document.getElementById("llm-form").addEventListener("submit", async (event) => {
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

document.getElementById("llm-review-graph").addEventListener("click", async () => {
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

document.getElementById("refresh-all").addEventListener("click", async () => {
    try {
        await loadGraph();
    } catch (error) {
        showMessage(error.message, true);
    }
});

loadGraph().catch((error) => {
    showMessage(error.message, true);
});
