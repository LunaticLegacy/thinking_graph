# ONNXRuntime/OpenVINO Model Assets

This directory is reserved for local model assets used by NPU backends.

Recommended layout:

- `models/<model_name>/` for ONNXRuntime GenAI model package
- `models/<model_name>/` for OpenVINO IR/GenAI model package
- Keep tokenizer/config files together with each model folder

Example:

- `models/Qwen2.5-3B-Instruct-onnx/`
- `models/Qwen2.5-3B-Instruct-openvino/`

Configure backend with environment variables:

- `LLM_BACKEND=openai|onnxruntime|openvino`
- `LLM_MODEL=<model_name>`
- `LLM_MODEL_DIR=<absolute_or_relative_models_dir>`
- `LLM_NPU_DEVICE=NPU`
- `LLM_REQUIRE_NPU=true`
- `LLM_ONNX_PROVIDER=QNNExecutionProvider` (optional)
