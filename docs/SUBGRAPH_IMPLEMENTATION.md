# Subgraph Mechanism Implementation

## Overview

This implementation adds a "subgraph query" capability to the Thinking Graph project, allowing LLM chat and graph queries to work with relevant portions of the graph instead of always processing the entire graph.

## Modified Files

### 1. `datamodels/graph_models.py`

**Added:**
- `SubgraphQueryPayload` dataclass with fields:
  - `query`: Optional text query for matching
  - `seed_node_ids`: List of explicit seed node IDs
  - `tags`: List of tags to match
  - `evidence_keywords`: List of keywords to match in evidence
  - `conn_types`: List of allowed connection types (filtered for validity)
  - `max_nodes`: Maximum nodes to return (clamped to [1, 50])
  - `max_connections`: Maximum connections to return (clamped to [0, 100])
  - `max_hops`: Maximum BFS expansion hops (clamped to [0, 4])
  - `min_confidence`: Minimum node confidence (clamped to [0, 1])
  - `include_visualization`: Whether to include visualization data
  - `include_orphans`: Whether to include orphan nodes
  - `reason`: Optional reason for the query

- `SubgraphResult` dataclass with fields:
  - `query`: The original query payload
  - `snapshot`: GraphSnapshot containing selected nodes/connections
  - `total_nodes_in_graph`: Total nodes in full graph
  - `total_connections_in_graph`: Total connections in full graph
  - `selected_node_count`: Number of nodes in subgraph
  - `selected_connection_count`: Number of connections in subgraph
  - `seed_node_count`: Number of seed nodes included
  - `message`: Human-readable summary

**Features:**
- `from_mapping()` method with robust validation
- Automatic clamping of numeric parameters
- Filtering of invalid connection types

### 2. `datamodels/ai_llm_models.py`

**Extended `LLMChatRequest`:**
- Added `graph_scope: str = "full"` (values: "full" | "subgraph")
- Added `subgraph: SubgraphQueryPayload | None = None`

**Features:**
- Backward compatible: old requests without these fields default to full graph
- Invalid `graph_scope` automatically falls back to "full"
- If `graph_scope="subgraph"` but subgraph parsing fails, falls back to "full"

### 3. `backend/services/graph_service.py`

**Added public method:**
```python
def query_subgraph(self, owner_id: str, payload: SubgraphQueryPayload) -> SubgraphResult
```

**Implementation details:**

#### Scoring Algorithm (`_score_node_for_subgraph`)

Each node receives a score based on:

1. **Query lexical matching** (lightweight, no external dependencies):
   - English: Token-based overlap (split on non-alphanumeric)
     - Content match: +2.0 per token
     - Summary match: +1.5 per token
   - Chinese/general: Substring matching
     - Full query in content: +5.0
     - Full query in summary: +3.0

2. **Seed node bonus**: +50.0 (high weight to ensure seeds are prioritized)

3. **Tag matching**: +10.0 per exact tag match

4. **Evidence keyword matching**: +8.0 per keyword match in evidence

5. **Confidence bonus**: +2.0 * node.confidence (light weight, doesn't dominate)

6. **Recency bonus**: +min(version * 0.1, 1.0) (very light weight proxy for recency)

#### Selection Process

1. **Score all nodes** in the active graph
2. **Select initial seeds**:
   - Sort by score descending (tiebreakers: created_at, id for stability)
   - Filter out zero-score nodes unless they're explicit seeds
   - If no criteria provided (empty query/seeds/tags/evidence), return recent nodes
3. **Expand neighborhood** via BFS:
   - Build bidirectional adjacency list
   - Expand up to `max_hops` from seed nodes
   - Prioritize high-priority edge types: supports/opposes/leads_to > derives_from > relates
   - Filter by `conn_types` if specified
4. **Filter by confidence**:
   - Remove nodes below `min_confidence` threshold
   - **Exception**: Seed nodes are kept even if below threshold (documented in code)
5. **Trim to limits**:
   - Priority order: seeds > high-score nodes > closer nodes
   - Respect `max_nodes` limit
6. **Select connections**:
   - Only connections between selected nodes
   - Filter by `conn_types` if specified
   - Prioritize by edge type priority, then strength
   - Respect `max_connections` limit
7. **Remove orphans** (if `include_orphans=False`):
   - Remove nodes not connected to any selected connection
   - Exception: Keep seed nodes even if orphaned

**Helper methods:**
- `_normalize_query_text()`: Normalize query for matching
- `_tokenize_query()`: Split query into tokens
- `_score_node_for_subgraph()`: Calculate node relevance score
- `_select_initial_seeds()`: Select starting nodes
- `_build_active_adjacency()`: Build adjacency list
- `_expand_subgraph_nodes()`: BFS expansion
- `_is_high_priority_edge()`: Check edge priority
- `_select_subgraph_connections()`: Select and prioritize edges
- `_trim_subgraph_nodes()`: Trim to max_nodes limit

**Key properties:**
- **Deterministic**: Same input → same output (stable sorting with tiebreakers)
- **Explainable**: Clear scoring formula, no black-box ML
- **Lightweight**: No external NLP libraries or vector databases
- **Compatible**: Returns standard GraphSnapshot for reuse with existing code

### 4. `web/routes.py`

**Modified endpoint:**
- `POST /api/llm/chat`
  - Now checks `graph_scope` parameter
  - If `graph_scope="subgraph"` and `subgraph` is provided:
    - Calls `graph_service().query_subgraph()`
    - Passes subgraph snapshot to LLM
  - Otherwise (default):
    - Uses full graph (backward compatible)

**New endpoint:**
- `POST /api/graph/subgraph`
  - Accepts SubgraphQueryPayload
  - Returns SubgraphResult
  - Error handling: 400 for invalid payload, 500 for server errors

## API Examples

### Query Subgraph

**Request:**
```json
POST /api/graph/subgraph
{
  "query": "多模态 agent 里的冲突观点",
  "tags": ["agent", "conflict"],
  "max_nodes": 10,
  "max_connections": 16,
  "max_hops": 2,
  "min_confidence": 0.2,
  "include_visualization": true
}
```

**Response:**
```json
{
  "query": { ... },
  "snapshot": {
    "nodes": [...],
    "connections": [...],
    "visualization": {...}
  },
  "total_nodes_in_graph": 50,
  "total_connections_in_graph": 80,
  "selected_node_count": 8,
  "selected_connection_count": 12,
  "seed_node_count": 2,
  "message": "Selected 8 nodes and 12 connections"
}
```

### LLM Chat with Subgraph

**Request:**
```json
POST /api/llm/chat
{
  "prompt": "请基于当前相关子图回答：有哪些核心冲突？",
  "language": "zh",
  "graph_scope": "subgraph",
  "subgraph": {
    "query": "核心冲突 证据",
    "max_nodes": 12,
    "max_connections": 20,
    "max_hops": 2,
    "min_confidence": 0.2
  }
}
```

**Response:** (same as before, but LLM only sees subgraph)
```json
{
  "enabled": true,
  "model": "gpt-4o-mini",
  "response": "..."
}
```

### Backward Compatibility

**Old request (still works):**
```json
POST /api/llm/chat
{
  "prompt": "What are the main ideas?",
  "language": "en"
}
```
→ Uses full graph (default behavior preserved)

## Scoring Formula Explanation

The node scoring formula balances multiple factors:

```
score = query_score + seed_bonus + tag_bonus + evidence_bonus + confidence_bonus + recency_bonus
```

**Weights rationale:**
- **Seed bonus (+50)**: Highest weight to ensure explicitly requested nodes are included
- **Tag match (+10 each)**: Strong signal for topical relevance
- **Evidence match (+8 each)**: Good indicator of substantiated claims
- **Query match (2-5 per match)**: Moderate weight for textual relevance
- **Confidence (+0 to +2)**: Light influence; shouldn't override explicit criteria
- **Recency (+0 to +1)**: Very light; just a tiebreaker

**Why this works:**
- Explicit signals (seeds, tags) dominate over implicit ones (text matching)
- Text matching still matters for discovery
- Confidence and recency provide gentle nudges without dominating
- Deterministic: no randomness, stable results

## Testing

Created comprehensive test suite in `tests/test_subgraph.py` covering:

1. ✅ Empty graph queries (no exceptions)
2. ✅ Query-only searches (no seed nodes)
3. ✅ Seed-only searches (no query text)
4. ✅ Non-existent seed nodes (graceful handling)
5. ✅ max_hops=0 (no expansion)
6. ✅ Connection type filtering
7. ✅ LLM chat with graph_scope=subgraph
8. ✅ Backward compatibility (old requests work)
9. ✅ Parameter validation and clamping
10. ✅ Deterministic output (same input → same output)
11. ✅ Confidence filtering

## Future Enhancements (Top 3 Recommendations)

1. **Advanced Text Matching**:
   - Add TF-IDF or BM25 scoring for better relevance
   - Implement simple character bigram overlap for Chinese
   - Consider integrating lightweight embeddings (e.g., sentence-transformers) if performance allows
   - **Entry point**: Replace `_score_node_for_subgraph()` text matching logic

2. **Caching and Performance Optimization**:
   - Cache frequently queried subgraphs
   - Add database-level indexes for common query patterns
   - Implement lazy loading for large graphs
   - **Entry point**: Add cache layer in `query_subgraph()` method

3. **Query Persistence and Analytics**:
   - Save successful subgraph queries as templates
   - Track which queries produce useful results
   - Allow users to bookmark/favorite subgraphs
   - **Entry point**: New table `subgraph_templates` and analytics endpoints

## Constraints Satisfied

✅ No new external dependencies  
✅ No vector database integration  
✅ No major frontend changes  
✅ Reuses existing dataclass style and service layer  
✅ Doesn't break CRUD/save/load/review/audit behavior  
✅ Deterministic and explainable subgraph selection  
✅ Lightweight implementation  
✅ Supports basic Chinese/English matching  
✅ Backward compatible  

## Code Quality

- Follows existing code style (dataclasses, service layer pattern)
- Comprehensive inline documentation
- Modular design with clear separation of concerns
- Proper error handling and validation
- Stable sorting for deterministic results
- No TODOs or incomplete implementations
