# ONNXRuntime/OpenVINO 模型资源

该目录用于存放 NPU 后端使用的本地模型资源。

推荐目录结构：

- `models/<model_name>/` 用于 ONNXRuntime GenAI 模型包
- `models/<model_name>/` 用于 OpenVINO IR / GenAI 模型包
- 将 `tokenizer / config` 等文件与对应模型目录放在一起

示例：
- `models/Qwen2.5-3B-Instruct-onnx/`
- `models/Qwen2.5-3B-Instruct-openvino/`

通过环境变量配置后端：
- `LLM_BACKEND=openai|onnxruntime|openvino`
- `LLM_MODEL=<model_name>`
- `LLM_MODEL_DIR=<absolute_or_relative_models_dir>`
- `LLM_NPU_DEVICE=NPU`
- `LLM_REQUIRE_NPU=true`
- `LLM_ONNX_PROVIDER=QNNExecutionProvider`（可选）

## 转换脚本使用说明

将`huggingface`的模型转化为可被 OpenVino 或 Onnxruntime 使用的模型格式。