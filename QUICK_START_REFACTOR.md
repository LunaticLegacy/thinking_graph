# Quick Start - Post-Refactoring

## What Changed?

The LLM integration has been completely refactored for better maintainability, testability, and extensibility. **All existing APIs work exactly the same** - no breaking changes!

## Installation (Choose One)

### Option 1: Cloud LLM (Recommended for Most Users)
```bash
pip install -r requirements.txt
```
Includes Flask + OpenAI API client. Use with DeepSeek, OpenAI, Claude, etc.

### Option 2: Local LLM with NPU
```bash
pip install -r requirements-local-llm.txt
```
Includes ONNX Runtime / OpenVINO for local inference.

### Option 3: Development Environment
```bash
pip install -r requirements-dev.txt
```
Adds pytest, httpx for testing.

### Option 4: Everything
```bash
pip install -r requirements/all.txt
```

## Running Tests

```bash
python -m pytest tests/test_llm_refactor.py -v
```

This runs 30+ tests covering:
- Schema validation
- Generation pipeline
- Review pipeline
- Backend adapters

## Using the New Architecture (Optional)

### Old Way (Still Works!)
```python
from backend.services.llm_service import LLMService

service = LLMService()
result = service.generate_graph_from_topic("AI ethics")
# Returns dict with nodes, connections, etc.
```

### New Way (Recommended for New Code)
```python
from config import LLMConfig
from backend.services.llm_backends import create_llm_backend
from backend.services.llm_graph_generation import GraphGenerationPipeline

# Create backend
config = LLMConfig.from_env()
backend = create_llm_backend(
    config=config,
    backend_type="remote_api",
    api_key="your-api-key",
)

# Create pipeline
pipeline = GraphGenerationPipeline(backend)

# Generate graph
result = pipeline.generate(
    topic="AI ethics",
    max_nodes=15,
    language="en"
)

# Access structured data
if result.enabled and result.draft:
    for node in result.draft.nodes:
        print(f"{node.id}: {node.content}")
    
    for conn in result.draft.connections:
        print(f"{conn.source_id} -> {conn.target_id} ({conn.conn_type})")
```

### Benefits of New Approach
- ✅ Type-safe access to nodes/connections
- ✅ Better error handling
- ✅ Direct access to validation results
- ✅ Easier to debug and test

## API Endpoints (Unchanged)

All endpoints work exactly as before:

### POST /api/llm/chat
```json
{
  "prompt": "What are the main arguments?",
  "language": "en"
}
```

### POST /api/llm/generate-graph
```json
{
  "topic": "Climate change solutions",
  "language": "en",
  "max_nodes": 12
}
```

### POST /api/llm/review-graph
```json
{
  "language": "en"
}
```

## Documentation

- **Full Refactoring Details**: `docs/LLM_REFACTORING.md`
- **Summary of Changes**: `REFACTORING_SUMMARY.md`
- **Architecture Overview**: See diagrams in docs

## Need Help?

1. Check `docs/LLM_REFACTORING.md` for detailed architecture
2. Read `tests/test_llm_refactor.py` for usage examples
3. All modules have docstrings explaining their purpose

## What's Next?

Consider these enhancements:
1. Add caching for frequent queries
2. Enable advanced critique in generation pipeline
3. Add monitoring for pipeline stages
4. Implement plugin system for custom backends

See `docs/LLM_REFACTORING.md` section "Future Enhancements" for details.
