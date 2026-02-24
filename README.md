# Thinking Graph 思维图

Thinking Graph 是一个基于大语言模型（LLM）的思维可视化工具，通过图形化方式展现复杂思维过程和逻辑关系。该项目支持多种 LLM 后端，包括远程 API、本地 API 以及 NPU 加速推理。

## 功能特性

- **可视化思维图**: 以图形化方式展示复杂的思维流程和逻辑关系
- **多后端支持**: 支持远程 API（如 OpenAI）、本地 API（Ollama、LM Studio）及 NPU 加速推理
- **灵活配置**: 通过 TOML 配置文件轻松切换后端和参数
- **Web 界面**: 提供直观的用户界面进行交互

## 技术架构

- **前端**: HTML, CSS, JavaScript
- **后端**: Python Flask 框架
- **数据库**: SQLite（或其他兼容数据库）
- **LLM 集成**: OpenAI API, Ollama, 以及其他本地推理引擎
- **NPU 支持**: ONNXRuntime 和 OpenVINO NPU 加速推理

## 安装步骤

1. 克隆项目到本地：
   ```bash
   git clone https://github.com/LunaticLegacy/thinking_graph.git
   cd thinking_graph
   ```

2. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # 或
   .venv\Scripts\activate     # Windows
   
   pip install -r requirements.txt
   ```

3. 配置应用参数：
   ```bash
   cp app_config_example.toml app_config.toml
   # 编辑 app_config.toml 以适应你的环境
   ```

## 配置说明

项目使用 `app_config.toml` 进行配置，主要包含以下几个部分：

- **[server]**: 服务器主机地址、端口、调试模式等
- **[paths]**: 模板目录、静态文件目录、数据目录等
- **[database]**: 数据库连接配置
- **[llm]**: 大语言模型后端配置，支持多种后端类型

LLM 后端支持以下选项：
- `remote_api`: 远程 API 调用（如 OpenAI）
- `local_api`: 本地 API 服务（如 Ollama、LM Studio）
- `onnxruntime`: 使用 NPU 加速的 ONNXRuntime
- `openvino`: 使用 NPU 加速的 OpenVINO

## 使用方法

1. 启动应用：
   ```bash
   python main.py
   ```

2. 在浏览器中打开 `http://localhost:5000` 访问应用

## 目录结构

```
thinking_graph/
├── backend/          # 后端服务代码
│   ├── services/     # 各种服务模块
│   └── repository.py # 数据访问层
├── config/           # 配置文件
├── core/             # 核心功能模块
│   ├── graph.py      # 图形处理逻辑
│   └── visualization.py # 可视化模块
├── datamodels/       # 数据模型定义
├── models/           # 模型相关说明
├── static/           # 静态资源
├── templates/        # 前端模板
├── utils/            # 工具类和辅助函数
│   ├── databaseman/  # 数据库管理
│   ├── llm_fetcher/  # LLM 获取器
│   └── llm_npu_module/ # NPU 模块
├── web/              # Web 路由和控制器
├── app_config.toml   # 应用配置文件
└── main.py           # 主启动文件
```

## NPU 后端配置

如需使用 NPU 加速推理，请参考 [models](./models) 目录中的说明配置模型资源。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进此项目！

## 许可证

请参阅 LICENSE 文件获取更多信息（如未提供，则为 MIT 许可证）。