"""Tests for subgraph query functionality."""

import pytest
from datamodels.graph_models import (
    Node,
    Connection,
    SubgraphQueryPayload,
    GraphSnapshot,
)
from backend.services.graph_service import GraphService
from backend.repository import SQLiteRepository
import tempfile
import os


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def repository(temp_db):
    """Create a repository with temporary database."""
    return SQLiteRepository(db_path=temp_db)


@pytest.fixture
def graph_service(repository):
    """Create a graph service instance."""
    return GraphService(repository)


@pytest.fixture
def sample_graph(graph_service):
    """Create a sample graph for testing."""
    owner_id = "test-owner"
    actor = "test-actor"
    
    # Create nodes using proper payload objects
    from datamodels.graph_models import NodeCreatePayload, Position
    
    node1_payload = NodeCreatePayload(
        content='Multi-modal agents use vision and language',
        summary='Multi-modal agent overview',
        position=Position(x=0, y=0),
        color='#157f83',
        size=1.0,
        tags=['agent', 'multimodal'],
        confidence=0.9,
        evidence=['research paper A']
    )
    node1 = graph_service.create_node(owner_id=owner_id, payload=node1_payload, actor=actor)
    
    node2_payload = NodeCreatePayload(
        content='Conflict arises when agents disagree on interpretation',
        summary='Agent conflict resolution',
        position=Position(x=100, y=0),
        color='#2d936c',
        size=1.0,
        tags=['conflict', 'agent'],
        confidence=0.8,
        evidence=['case study B']
    )
    node2 = graph_service.create_node(owner_id=owner_id, payload=node2_payload, actor=actor)
    
    node3_payload = NodeCreatePayload(
        content='Vision models process images',
        summary='Vision processing',
        position=Position(x=0, y=100),
        color='#3f88c5',
        size=1.0,
        tags=['vision'],
        confidence=0.7,
        evidence=[]
    )
    node3 = graph_service.create_node(owner_id=owner_id, payload=node3_payload, actor=actor)
    
    node4_payload = NodeCreatePayload(
        content='Language models handle text understanding',
        summary='Language processing',
        position=Position(x=100, y=100),
        color='#f4a259',
        size=1.0,
        tags=['language'],
        confidence=0.75,
        evidence=[]
    )
    node4 = graph_service.create_node(owner_id=owner_id, payload=node4_payload, actor=actor)
    
    # Create connections
    from datamodels.graph_models import ConnectionCreatePayload
    
    conn1_payload = ConnectionCreatePayload(
        source_id=node1.id,
        target_id=node2.id,
        conn_type='opposes',
        description='Agents may conflict',
        strength=0.8
    )
    graph_service.create_connection(owner_id=owner_id, payload=conn1_payload, actor=actor)
    
    conn2_payload = ConnectionCreatePayload(
        source_id=node1.id,
        target_id=node3.id,
        conn_type='supports',
        description='Uses vision',
        strength=0.9
    )
    graph_service.create_connection(owner_id=owner_id, payload=conn2_payload, actor=actor)
    
    conn3_payload = ConnectionCreatePayload(
        source_id=node1.id,
        target_id=node4.id,
        conn_type='supports',
        description='Uses language',
        strength=0.9
    )
    graph_service.create_connection(owner_id=owner_id, payload=conn3_payload, actor=actor)
    
    return owner_id


class TestSubgraphQueryPayload:
    """Test SubgraphQueryPayload validation and parsing."""
    
    def test_from_mapping_basic(self):
        """Test basic payload parsing."""
        data = {
            "query": "test query",
            "max_nodes": 10,
            "max_connections": 20,
            "max_hops": 2,
            "min_confidence": 0.5
        }
        payload = SubgraphQueryPayload.from_mapping(data)
        
        assert payload.query == "test query"
        assert payload.max_nodes == 10
        assert payload.max_connections == 20
        assert payload.max_hops == 2
        assert payload.min_confidence == 0.5
    
    def test_max_nodes_clamping(self):
        """Test max_nodes is clamped to [1, 50]."""
        # Too small
        payload = SubgraphQueryPayload.from_mapping({"max_nodes": 0})
        assert payload.max_nodes == 1
        
        # Too large
        payload = SubgraphQueryPayload.from_mapping({"max_nodes": 100})
        assert payload.max_nodes == 50
        
        # Valid
        payload = SubgraphQueryPayload.from_mapping({"max_nodes": 25})
        assert payload.max_nodes == 25
    
    def test_max_connections_clamping(self):
        """Test max_connections is clamped to [0, 100]."""
        # Negative
        payload = SubgraphQueryPayload.from_mapping({"max_connections": -5})
        assert payload.max_connections == 0
        
        # Too large
        payload = SubgraphQueryPayload.from_mapping({"max_connections": 150})
        assert payload.max_connections == 100
    
    def test_max_hops_clamping(self):
        """Test max_hops is clamped to [0, 4]."""
        # Negative
        payload = SubgraphQueryPayload.from_mapping({"max_hops": -1})
        assert payload.max_hops == 0
        
        # Too large
        payload = SubgraphQueryPayload.from_mapping({"max_hops": 10})
        assert payload.max_hops == 4
    
    def test_min_confidence_clamping(self):
        """Test min_confidence is clamped to [0, 1]."""
        # Below range
        payload = SubgraphQueryPayload.from_mapping({"min_confidence": -0.5})
        assert payload.min_confidence == 0.0
        
        # Above range
        payload = SubgraphQueryPayload.from_mapping({"min_confidence": 1.5})
        assert payload.min_confidence == 1.0
    
    def test_invalid_conn_types_filtered(self):
        """Test that invalid connection types are filtered out."""
        data = {
            "conn_types": ["supports", "invalid_type", "opposes", "another_bad"]
        }
        payload = SubgraphQueryPayload.from_mapping(data)
        
        assert "supports" in payload.conn_types
        assert "opposes" in payload.conn_types
        assert "invalid_type" not in payload.conn_types
        assert "another_bad" not in payload.conn_types


class TestSubgraphQueryEmptyGraph:
    """Test subgraph queries on empty graphs."""
    
    def test_empty_graph_query(self, graph_service):
        """Query subgraph on empty graph should not raise exception."""
        owner_id = "test-owner"
        payload = SubgraphQueryPayload.from_mapping({
            "query": "test"
        })
        
        result = graph_service.query_subgraph(owner_id, payload)
        
        assert result.selected_node_count == 0
        assert result.selected_connection_count == 0
        assert result.total_nodes_in_graph == 0
        assert result.snapshot.visualization is not None


class TestSubgraphQueryWithQuery:
    """Test subgraph queries using text query."""
    
    def test_query_matching(self, graph_service, sample_graph):
        """Test that query matching works."""
        payload = SubgraphQueryPayload.from_mapping({
            "query": "multi-modal agent",
            "max_nodes": 10
        })
        
        result = graph_service.query_subgraph(sample_graph, payload)
        
        # Should find at least the multi-modal agent node
        assert result.selected_node_count >= 1
        assert any("multi-modal" in n.content.lower() or "multi-modal" in n.summary.lower() 
                   for n in result.snapshot.nodes)
    
    def test_query_with_no_matches(self, graph_service, sample_graph):
        """Test query with no matches returns reasonable result."""
        payload = SubgraphQueryPayload.from_mapping({
            "query": "xyz_nonexistent_topic_12345"
        })
        
        result = graph_service.query_subgraph(sample_graph, payload)
        
        # May return some nodes based on other criteria or be empty
        assert result.selected_node_count >= 0


class TestSubgraphQueryWithSeeds:
    """Test subgraph queries using seed nodes."""
    
    def test_seed_nodes_only(self, graph_service, sample_graph):
        """Test query with only seed node IDs."""
        # Get all nodes first
        snapshot = graph_service.graph_snapshot(sample_graph)
        seed_id = snapshot.nodes[0].id
        
        payload = SubgraphQueryPayload.from_mapping({
            "seed_node_ids": [seed_id],
            "max_hops": 0  # No expansion
        })
        
        result = graph_service.query_subgraph(sample_graph, payload)
        
        # Should include the seed node
        assert result.selected_node_count >= 1
        assert any(n.id == seed_id for n in result.snapshot.nodes)
    
    def test_nonexistent_seed_nodes(self, graph_service, sample_graph):
        """Test query with non-existent seed nodes doesn't crash."""
        payload = SubgraphQueryPayload.from_mapping({
            "seed_node_ids": ["nonexistent-id-12345"],
            "max_hops": 0
        })
        
        result = graph_service.query_subgraph(sample_graph, payload)
        
        # Should not crash, may return empty or fallback nodes
        assert result is not None


class TestSubgraphQueryMaxHops:
    """Test subgraph queries with different hop counts."""
    
    def test_max_hops_zero(self, graph_service, sample_graph):
        """Test max_hops=0 returns only seed/high-score nodes."""
        payload = SubgraphQueryPayload.from_mapping({
            "query": "agent",
            "max_hops": 0
        })
        
        result = graph_service.query_subgraph(sample_graph, payload)
        
        # Should have nodes but limited expansion
        assert result.selected_node_count >= 1
    
    def test_max_hops_expansion(self, graph_service, sample_graph):
        """Test that higher max_hops includes more nodes."""
        snapshot = graph_service.graph_snapshot(sample_graph)
        seed_id = snapshot.nodes[0].id
        
        payload_hops_0 = SubgraphQueryPayload.from_mapping({
            "seed_node_ids": [seed_id],
            "max_hops": 0
        })
        
        payload_hops_2 = SubgraphQueryPayload.from_mapping({
            "seed_node_ids": [seed_id],
            "max_hops": 2
        })
        
        result_0 = graph_service.query_subgraph(sample_graph, payload_hops_0)
        result_2 = graph_service.query_subgraph(sample_graph, payload_hops_2)
        
        # Hops=2 should potentially include more nodes
        assert result_2.selected_node_count >= result_0.selected_node_count


class TestSubgraphQueryConnTypes:
    """Test subgraph queries with connection type filtering."""
    
    def test_conn_types_filtering(self, graph_service, sample_graph):
        """Test that conn_types filtering works."""
        payload = SubgraphQueryPayload.from_mapping({
            "query": "agent",
            "conn_types": ["supports"],
            "max_hops": 2
        })
        
        result = graph_service.query_subgraph(sample_graph, payload)
        
        # All connections should be of type 'supports'
        for conn in result.snapshot.connections:
            assert conn.conn_type == "supports"


class TestLLMChatWithSubgraph:
    """Test LLM chat endpoint with subgraph scope."""
    
    def test_chat_with_full_graph_default(self):
        """Test that default behavior uses full graph (backward compatibility)."""
        from datamodels.ai_llm_models import LLMChatRequest
        
        # Old-style request without graph_scope
        payload = {
            "prompt": "test prompt",
            "language": "en"
        }
        
        request = LLMChatRequest.from_mapping(payload)
        
        assert request.graph_scope == "full"
        assert request.subgraph is None
    
    def test_chat_with_subgraph_scope(self):
        """Test parsing of subgraph scope."""
        from datamodels.ai_llm_models import LLMChatRequest
        
        payload = {
            "prompt": "test prompt",
            "language": "en",
            "graph_scope": "subgraph",
            "subgraph": {
                "query": "test query",
                "max_nodes": 10
            }
        }
        
        request = LLMChatRequest.from_mapping(payload)
        
        assert request.graph_scope == "subgraph"
        assert request.subgraph is not None
        assert request.subgraph.query == "test query"
    
    def test_invalid_graph_scope_fallback(self):
        """Test that invalid graph_scope falls back to 'full'."""
        from datamodels.ai_llm_models import LLMChatRequest
        
        payload = {
            "prompt": "test",
            "graph_scope": "invalid_value"
        }
        
        request = LLMChatRequest.from_mapping(payload)
        
        assert request.graph_scope == "full"
    
    def test_subgraph_parse_failure_fallback(self):
        """Test that subgraph parse failure falls back to full graph."""
        from datamodels.ai_llm_models import LLMChatRequest
        
        payload = {
            "prompt": "test",
            "graph_scope": "subgraph",
            "subgraph": "not_a_valid_object"  # Invalid subgraph
        }
        
        request = LLMChatRequest.from_mapping(payload)
        
        # Should fall back to full
        assert request.graph_scope == "full"
        assert request.subgraph is None


class TestSubgraphDeterminism:
    """Test that subgraph queries are deterministic."""
    
    def test_same_input_same_output(self, graph_service, sample_graph):
        """Test that same query produces same results."""
        payload = SubgraphQueryPayload.from_mapping({
            "query": "agent",
            "max_nodes": 10
        })
        
        result1 = graph_service.query_subgraph(sample_graph, payload)
        result2 = graph_service.query_subgraph(sample_graph, payload)
        
        # Same number of nodes and connections
        assert result1.selected_node_count == result2.selected_node_count
        assert result1.selected_connection_count == result2.selected_connection_count
        
        # Same node IDs in same order
        nodes1 = [n.id for n in result1.snapshot.nodes]
        nodes2 = [n.id for n in result2.snapshot.nodes]
        assert nodes1 == nodes2


class TestSubgraphConfidenceFilter:
    """Test confidence-based filtering."""
    
    def test_min_confidence_filter(self, graph_service, sample_graph):
        """Test that low-confidence nodes are filtered."""
        payload = SubgraphQueryPayload.from_mapping({
            "query": "agent",
            "min_confidence": 0.85,
            "max_nodes": 10
        })
        
        result = graph_service.query_subgraph(sample_graph, payload)
        
        # All returned nodes should meet confidence threshold (except seeds)
        for node in result.snapshot.nodes:
            # Note: seeds might be kept even below threshold per spec
            assert node.confidence >= 0.85 or node.id in payload.seed_node_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
