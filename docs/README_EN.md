<div align="center">

<br />

<img src="https://raw.githubusercontent.com/LunaticLegacy/thinking_graph/main/assets/logo.png" width="120" alt="Thinking Graph Logo" />

# Thinking Graph

### Make Thinking Visible · Make Logic Tangible

**An open-source tool for visualizing thoughts and argumentation**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1+-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/LunaticLegacy/thinking_graph?style=social)](https://github.com/LunaticLegacy/thinking_graph)

[📖 Docs](https://github.com/LunaticLegacy/thinking_graph/wiki) · [🚀 Live Demo](https://demo.thinking-graph.dev) · [💬 Discussions](https://github.com/LunaticLegacy/thinking_graph/discussions) · [🇨🇳 中文](../README.md)

<br />

<img src="https://raw.githubusercontent.com/LunaticLegacy/thinking_graph/main/assets/screenshot.png" width="90%" alt="Thinking Graph Screenshot" />

</div>

---

## ✨ Why Thinking Graph?

> *"Complex thoughts deserve to be seen, not forgotten in the margins of a notebook."*

In an age of information overload, we're constantly absorbing viewpoints, forming judgments, and engaging in discussions. But thinking is linear, while **true understanding is often a network**.

Thinking Graph helps you:

- 🧩 **Visualize thought processes** — Organize scattered ideas into clear argumentation networks
- ⚡ **Multi-backend LLM support** — Local NPU inference or cloud APIs, your choice
- 🔍 **Intelligent auditing** — AI automatically checks for logical conflicts and argument completeness
- 📜 **Full traceability** — Every change is recorded, thought evolution leaves a trail

---

## 🚀 Get Started in 5 Minutes

### Installation

```bash
# Clone the repository
git clone https://github.com/LunaticLegacy/thinking_graph.git
cd thinking_graph

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the config file
cp app_config_example.toml app_config.toml

# Edit to choose your LLM backend:
# - remote_api: DeepSeek / OpenAI / Claude
# - local_api: Ollama / LM Studio / vLLM
# - onnxruntime / openvino: Local NPU acceleration
```

### Launch

```bash
python main.py
```

Open your browser at `http://localhost:5000` and start building your first thinking graph!

---

## 🎯 Core Features

### 📊 Visual Argumentation Networks

```python
from thinking_graph import GraphBuilder

builder = GraphBuilder()
builder.add_node("Remote work boosts productivity", confidence=0.85)
builder.add_node("Reduced commute time", confidence=0.95)
builder.connect("Reduced commute time", "Remote work boosts productivity", type="supports")

graph = builder.build()
graph.visualize()  # Generate interactive network graph
```

- **Nodes**: Represent viewpoints with confidence scores, tags, and evidence
- **Connections**: Five relationship types: supports / opposes / relates / leads_to / derives_from
- **Interactive UI**: Drag-to-layout, zoom navigation, click-to-edit

### 🤖 Multi-Backend LLM Integration

| Backend | Latency | Privacy | Best For |
|---------|---------|---------|----------|
| Remote API | ⚡⚡⚡ | 🔒 | Rapid prototyping, high-accuracy needs |
| Local API | ⚡⚡ | 🔒🔒 | Balancing performance & privacy |
| ONNXRuntime | ⚡ | 🔒🔒🔒 | Fully local, NPU accelerated |
| OpenVINO | ⚡ | 🔒🔒🔒 | Intel NPU optimized |

### 🔎 Intelligent Logic Auditing

```python
# AI automatically checks argument consistency
review_result = graph.ai_review()
# {
#   "verdict": "CONFLICT",
#   "conflicts": [
#     {
#       "entity_type": "connection",
#       "entity_id": "conn_001",
#       "reason": "Same node pair has both supports and opposes relationships"
#     }
#   ]
# }
```

Built-in audit rules:
- ✅ No empty content nodes
- ✅ No self-loop connections
- ✅ Detect contradictory support/oppose relationships
- ✅ Validate node reference integrity

### 📜 Complete Audit Trail

Every create, update, and delete operation is logged:

```json
{
  "entity_type": "node",
  "entity_id": "node_abc123",
  "action": "update",
  "actor": "luna",
  "reason": "Correcting confidence score",
  "before_state": { "confidence": 0.7, ... },
  "after_state": { "confidence": 0.85, ... },
  "created_at": "2026-02-24T14:32:00Z"
}
```

Supports exporting audit reports, verifying data integrity, and rolling back to any historical version.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  React UI   │  │ Vis.js Graph │  │  Interactive Canvas │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Flask Backend                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Routes    │  │   Services  │  │    Repository       │  │
│  │   (API)     │──│  (Business) │──│   (Data Access)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              LLM Integration Layer                   │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │    │
│  │  │ DeepSeek │ │  Ollama  │ │ONNX NPU  │ │OpenVINO│  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   SQLite    │  │  Snapshots  │  │     Audit Log       │  │
│  │  (Nodes &   │  │  (Versioned │  │  (Immutable History)│  │
│  │ Connections)│  │   Graphs)   │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Project Structure

```
thinking_graph/
├── backend/                    # Business logic layer
│   ├── services/               # Core services
│   │   ├── graph_service.py    # Graph CRUD operations
│   │   └── llm_service.py      # LLM integration
│   └── repository.py           # Data access layer
├── config/                     # Configuration files
├── core/                       # Domain core
│   ├── graph.py                # Graph models and algorithms
│   └── visualization.py        # Visualization rendering
├── data/                       # User data storage
├── datamodels/                 # Data model definitions
├── docs/                       # Documentation
├── models/                     # LLM model storage
├── static/                     # Frontend static assets
├── templates/                  # HTML templates
├── tests/                      # Test suite 🚧
├── utils/                      # Utility modules
│   ├── databaseman/            # Database management
│   ├── llm_fetcher/            # LLM client
│   └── llm_npu_module/         # NPU inference acceleration
├── web/                        # Web routes and controllers
├── app_config_example.toml     # Example application configuration
└── main.py                     # Entry point
```

---

## 🛣️ Roadmap

- [x] Core graph operations (CRUD)
- [x] Multi-backend LLM support
- [x] Audit logging system
- [x] Graph snapshot save/load
- [ ] Collaborative editing (WebSocket)
- [ ] Import/Export (Markdown, JSON, GraphML)
- [ ] Template library (argumentation framework presets)
- [ ] Mobile responsiveness
- [ ] Plugin system

---

## 🤝 Contributing

We welcome contributions of all kinds!

1. **Fork** this repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a **Pull Request**

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

[MIT](LICENSE) © 2026 月と猫 - LunaNeko

---

<div align="center">

**[⬆ Back to Top](#thinking-graph)**

Made with ❤️ and ☕ by [L月と猫 - LunaNekoo](https://github.com/LunaticLegacy)

</div>
