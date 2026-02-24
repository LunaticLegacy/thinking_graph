# Thinking Graph

Thinking Graph is a visualization tool for cognitive processes based on Large Language Models (LLM), displaying complex thinking processes and logical relationships in a graphical manner. The project supports multiple LLM backends, including remote APIs, local APIs, and NPU-accelerated inference.

## Features

- **Visual Thinking Maps**: Display complex thought processes and logical relationships in a graphical format
- **Multiple Backend Support**: Supports remote APIs (e.g., OpenAI), local APIs (Ollama, LM Studio), and NPU-accelerated inference
- **Flexible Configuration**: Easily switch backends and parameters via TOML configuration files
- **Web Interface**: Provides intuitive user interface for interaction

## Technical Architecture

- **Frontend**: HTML, CSS, JavaScript
- **Backend**: Python Flask Framework
- **Database**: SQLite (or other compatible databases)
- **LLM Integration**: OpenAI API, Ollama, and other local inference engines
- **NPU Support**: ONNXRuntime and OpenVINO NPU-accelerated inference

## Installation

1. Clone the project:
   ```bash
   git clone <repository-url>
   cd thinking_graph
   ```

2. Create virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate     # Windows
   
   pip install -r requirements.txt
   ```

3. Configure application parameters:
   ```bash
   cp app_config.toml app_config_example.toml
   # Edit app_config.toml to adapt to your environment
   ```

## Configuration

The project uses `app_config.toml` for configuration, mainly including the following sections:

- **[server]**: Server host address, port, debug mode, etc.
- **[paths]**: Template directory, static files directory, data directory, etc.
- **[database]**: Database connection configuration
- **[llm]**: Large language model backend configuration, supporting multiple backend types

LLM backend supports the following options:
- `remote_api`: Remote API calls (e.g., OpenAI)
- `local_api`: Local API service (e.g., Ollama, LM Studio)
- `onnxruntime`: Using NPU-accelerated ONNXRuntime
- `openvino`: Using NPU-accelerated OpenVINO

## Usage

1. Start the application:
   ```bash
   python main.py
   ```

2. Open `http://localhost:5000` in your browser to access the application

## Directory Structure

```
thinking_graph/
├── backend/          # Backend service code
│   ├── services/     # Various service modules
│   └── repository.py # Data access layer
├── config/           # Configuration files
├── core/             # Core functionality modules
│   ├── graph.py      # Graph processing logic
│   └── visualization.py # Visualization module
├── datamodels/       # Data model definitions
├── models/           # Model-related documentation
├── static/           # Static resources
├── templates/        # Frontend templates
├── utils/            # Utility classes and helper functions
│   ├── databaseman/  # Database management
│   ├── llm_fetcher/  # LLM fetcher
│   └── llm_npu_module/ # NPU module
├── web/              # Web routing and controllers
├── app_config.toml   # Application configuration file
└── main.py           # Main entry point
```

## NPU Backend Configuration

To use NPU-accelerated inference, please refer to the instructions in the [models](../models) directory to configure model resources.

## Contributing

Feel free to submit Issues and Pull Requests to improve this project!

## License

See the LICENSE file for more information (if not provided, it defaults to MIT License).