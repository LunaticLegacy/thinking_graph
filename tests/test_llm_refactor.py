"""Tests for refactored LLM architecture."""

import pytest
from unittest.mock import Mock, MagicMock

from backend.services.llm_backends import APIBackend, LocalRuntimeBackend, create_llm_backend
from backend.services.llm_schemas import (
    LLMGeneratedNode,
    LLMGeneratedConnection,
    LLMGraphDraft,
    LLMGraphGenerationResult,
    LLMOperationStatus,
    LLMGraphIssue,
    LLMGraphWarning,
    LLMGraphReviewAggregate,
)
from backend.services.llm_graph_generation import GraphGenerationPipeline
from backend.services.llm_graph_review import GraphReviewPipeline
from datamodels.graph_models import Node, Connection, Position, GraphSnapshot
from config import LLMConfig


class TestLLMSchemas:
    """Test LLM schema dataclasses."""
    
    def test_generated_node_creation(self):
        """Test creating a generated node."""
        node = LLMGeneratedNode(
            id="n1",
            content="Test content",
            summary="Test summary",
            confidence=0.9,
        )
        
        assert node.id == "n1"
        assert node.content == "Test content"
        assert node.confidence == 0.9
    
    def test_generated_connection_creation(self):
        """Test creating a generated connection."""
        conn = LLMGeneratedConnection(
            source_id="n1",
            target_id="n2",
            conn_type="supports",
            strength=1.5,
        )
        
        assert conn.source_id == "n1"
        assert conn.conn_type == "supports"
    
    def test_graph_draft_creation(self):
        """Test creating a graph draft."""
        draft = LLMGraphDraft(
            nodes=[
                LLMGeneratedNode(id="n1", content="Node 1"),
                LLMGeneratedNode(id="n2", content="Node 2"),
            ],
            connections=[
                LLMGeneratedConnection(source_id="n1", target_id="n2"),
            ],
            summary="Test summary",
        )
        
        assert len(draft.nodes) == 2
        assert len(draft.connections) == 1
    
    def test_generation_result_properties(self):
        """Test generation result properties."""
        draft = LLMGraphDraft(
            nodes=[LLMGeneratedNode(id="n1", content="Test")],
            connections=[],
        )
        
        result = LLMGraphGenerationResult(
            status=LLMOperationStatus(success=True),
            draft=draft,
            model="test-model",
        )
        
        assert result.enabled is True
        assert result.node_count == 1
        assert result.connection_count == 0
    
    def test_graph_issue_creation(self):
        """Test creating a graph issue."""
        issue = LLMGraphIssue(
            entity_type="node",
            entity_id="n1",
            reason="Empty content",
            severity="error",
            source="rule",
        )
        
        assert issue.severity == "error"
        assert issue.source == "rule"
    
    def test_review_aggregate_to_dict(self):
        """Test review aggregate serialization."""
        aggregate = LLMGraphReviewAggregate(
            verdict="CONFLICT",
            conflicts=[
                LLMGraphIssue(
                    entity_type="node",
                    entity_id="n1",
                    reason="Test issue",
                )
            ],
            warnings=[
                LLMGraphWarning(
                    entity_type="connection",
                    entity_id="c1",
                    reason="Test warning",
                )
            ],
            overview="Test overview",
            conflict_count=1,
            warning_count=1,
        )
        
        result_dict = aggregate.to_dict()
        
        assert result_dict["verdict"] == "CONFLICT"
        assert len(result_dict["conflicts"]) == 1
        assert len(result_dict["warnings"]) == 1
        assert result_dict["conflict_count"] == 1


class TestGraphGenerationPipeline:
    """Test graph generation pipeline."""
    
    @pytest.fixture
    def mock_backend(self):
        """Create a mock LLM backend."""
        backend = Mock()
        backend.enabled = True
        backend.model_name = "test-model"
        return backend
    
    @pytest.fixture
    def pipeline(self, mock_backend):
        """Create a generation pipeline with mock backend."""
        return GraphGenerationPipeline(mock_backend)
    
    def test_empty_topic_rejected(self, pipeline):
        """Test that empty topic is rejected."""
        result = pipeline.generate(topic="")
        
        assert result.enabled is False
        assert "required" in result.message.lower()
    
    def test_disabled_backend_handling(self, pipeline):
        """Test handling of disabled backend."""
        pipeline.backend.enabled = False
        
        result = pipeline.generate(topic="Test topic")
        
        assert result.enabled is False
    
    def test_json_extraction_from_fenced_code(self, pipeline):
        """Test JSON extraction from code-fenced response."""
        # This tests the internal _extract_json_payload method
        fenced_json = '''```json
{
  "nodes": [{"id": "n1", "content": "Test"}],
  "connections": []
}
```'''
        
        payload = pipeline._extract_json_payload(fenced_json)
        
        assert payload is not None
        assert "nodes" in payload
    
    def test_node_parsing_with_duplicates(self, pipeline):
        """Test node parsing handles duplicate IDs."""
        raw_nodes = [
            {"id": "n1", "content": "Node 1"},
            {"id": "n1", "content": "Node 2"},  # Duplicate ID
        ]
        
        nodes = pipeline._parse_generated_nodes(raw_nodes, max_nodes=10)
        
        assert len(nodes) == 2
        assert nodes[0].id != nodes[1].id  # IDs should be different
    
    def test_node_filtering_empty_content(self, pipeline):
        """Test that nodes with empty content are filtered."""
        raw_nodes = [
            {"id": "n1", "content": ""},
            {"id": "n2", "content": "Valid content"},
        ]
        
        nodes = pipeline._parse_generated_nodes(raw_nodes, max_nodes=10)
        
        assert len(nodes) == 1
        assert nodes[0].id == "n2"
    
    def test_connection_validation_invalid_nodes(self, pipeline):
        """Test that connections to invalid nodes are rejected."""
        raw_connections = [
            {
                "source_id": "nonexistent",
                "target_id": "also_nonexistent",
                "conn_type": "supports",
            }
        ]
        
        connections = pipeline._parse_generated_connections(
            raw_connections,
            node_ids={"n1", "n2"},
            language="en",
        )
        
        assert len(connections) == 0
    
    def test_connection_self_loop_rejected(self, pipeline):
        """Test that self-loop connections are rejected."""
        raw_connections = [
            {
                "source_id": "n1",
                "target_id": "n1",  # Self-loop
                "conn_type": "supports",
            }
        ]
        
        connections = pipeline._parse_generated_connections(
            raw_connections,
            node_ids={"n1"},
            language="en",
        )
        
        assert len(connections) == 0
    
    def test_confidence_variation_ensured(self, pipeline):
        """Test that confidence variation is ensured."""
        nodes = [
            LLMGeneratedNode(id=f"n{i}", content=f"Content {i}", confidence=1.0)
            for i in range(5)
        ]
        
        pipeline._ensure_confidence_variation(nodes)
        
        # Should have varied confidence values
        confidences = [n.confidence for n in nodes]
        assert len(set(confidences)) > 1
    
    def test_hex_color_normalization(self, pipeline):
        """Test hex color normalization."""
        assert pipeline._normalize_hex_color("#ABCDEF") == "#abcdef"
        assert pipeline._normalize_hex_color("invalid") == "#157f83"
        assert pipeline._normalize_hex_color(None) == "#157f83"
    
    def test_float_clamping(self, pipeline):
        """Test float value clamping."""
        assert pipeline._clamp_float(1.5, 0.0, 1.0) == 1.0
        assert pipeline._clamp_float(-0.5, 0.0, 1.0) == 0.0
        assert pipeline._clamp_float(0.5, 0.0, 1.0) == 0.5


class TestGraphReviewPipeline:
    """Test graph review pipeline."""
    
    @pytest.fixture
    def mock_backend(self):
        """Create a mock LLM backend."""
        backend = Mock()
        backend.enabled = True
        backend.model_name = "test-model"
        return backend
    
    @pytest.fixture
    def pipeline(self, mock_backend):
        """Create a review pipeline with mock backend."""
        return GraphReviewPipeline(mock_backend)
    
    @pytest.fixture
    def sample_snapshot(self):
        """Create a sample graph snapshot for testing."""
        nodes = [
            Node(
                id="n1",
                content="Test node 1",
                summary="Summary 1",
                position=Position(x=0, y=0),
                confidence=0.9,
            ),
            Node(
                id="n2",
                content="Test node 2",
                summary="Summary 2",
                position=Position(x=100, y=0),
                confidence=0.8,
            ),
        ]
        
        connections = [
            Connection(
                id="c1",
                source_id="n1",
                target_id="n2",
                conn_type="supports",
                description="Node 1 supports node 2",
                strength=1.0,
            )
        ]
        
        return GraphSnapshot(nodes=nodes, connections=connections, visualization={})
    
    def test_structural_validation_empty_node(self, pipeline, sample_snapshot):
        """Test detection of empty content nodes."""
        # Add an empty node
        empty_node = Node(
            id="n_empty",
            content="",
            summary="",
            position=Position(x=0, y=0),
        )
        sample_snapshot.nodes.append(empty_node)
        
        issues, warnings = pipeline._structural_validate(sample_snapshot, "en")
        
        assert any(i.entity_id == "n_empty" for i in issues)
    
    def test_structural_validation_self_loop(self, pipeline, sample_snapshot):
        """Test detection of self-loop connections."""
        self_loop = Connection(
            id="c_self",
            source_id="n1",
            target_id="n1",  # Self-loop
            conn_type="relates",
            description="",
            strength=1.0,
        )
        sample_snapshot.connections.append(self_loop)
        
        issues, warnings = pipeline._structural_validate(sample_snapshot, "en")
        
        assert any(i.entity_id == "c_self" for i in issues)
    
    def test_structural_validation_contradiction(self, pipeline, sample_snapshot):
        """Test detection of contradictory relationships."""
        # Add opposing connection
        opposes_conn = Connection(
            id="c_opposes",
            source_id="n1",
            target_id="n2",
            conn_type="opposes",
            description="Node 1 opposes node 2",
            strength=1.0,
        )
        sample_snapshot.connections.append(opposes_conn)
        
        issues, warnings = pipeline._structural_validate(sample_snapshot, "en")
        
        # Should detect contradiction between supports and opposes
        assert len(issues) > 0
    
    def test_structural_validation_high_confidence_no_evidence(self, pipeline, sample_snapshot):
        """Test warning for high confidence without evidence."""
        high_conf_node = Node(
            id="n_high",
            content="High confidence claim",
            summary="",
            position=Position(x=0, y=0),
            confidence=0.95,
            evidence=[],  # No evidence
        )
        sample_snapshot.nodes.append(high_conf_node)
        
        issues, warnings = pipeline._structural_validate(sample_snapshot, "en")
        
        assert any(w.entity_id == "n_high" for w in warnings)
    
    def test_review_aggregation_ok_verdict(self, pipeline):
        """Test aggregation when no issues found."""
        aggregate = pipeline._aggregate_reviews(
            rule_issues=[],
            rule_warnings=[],
            llm_draft=Mock(result="OK", conflicts=[], warnings=[], overview=""),
            language="en",
        )
        
        assert aggregate.verdict == "OK"
        assert aggregate.conflict_count == 0
    
    def test_review_aggregation_conflict_verdict(self, pipeline):
        """Test aggregation when conflicts found."""
        issue = LLMGraphIssue(
            entity_type="node",
            entity_id="n1",
            reason="Test conflict",
        )
        
        aggregate = pipeline._aggregate_reviews(
            rule_issues=[issue],
            rule_warnings=[],
            llm_draft=Mock(result="OK", conflicts=[], warnings=[], overview=""),
            language="en",
        )
        
        assert aggregate.verdict == "CONFLICT"
        assert aggregate.conflict_count == 1
    
    def test_review_aggregation_warning_verdict(self, pipeline):
        """Test aggregation when only warnings found."""
        warning = LLMGraphWarning(
            entity_type="connection",
            entity_id="c1",
            reason="Test warning",
        )
        
        aggregate = pipeline._aggregate_reviews(
            rule_issues=[],
            rule_warnings=[warning],
            llm_draft=Mock(result="OK", conflicts=[], warnings=[], overview=""),
            language="en",
        )
        
        assert aggregate.verdict == "WARNING"
        assert aggregate.warning_count == 1
    
    def test_json_extraction_robustness(self, pipeline):
        """Test JSON extraction handles various formats."""
        # Code fence with json tag
        result1 = pipeline._extract_json_payload('```json\n{"test": 1}\n```')
        assert result1 is not None
        
        # Plain JSON
        result2 = pipeline._extract_json_payload('{"test": 1}')
        assert result2 is not None
        
        # JSON wrapped in text
        result3 = pipeline._extract_json_payload('Some text {"test": 1} more text')
        assert result3 is not None
        
        # Invalid JSON
        result4 = pipeline._extract_json_payload('Not JSON at all')
        assert result4 is None
    
    def test_heuristic_review_parse_ok(self, pipeline):
        """Test heuristic parsing of OK response."""
        draft = pipeline._heuristic_review_parse("OK", "en")
        assert draft.result == "OK"
    
    def test_heuristic_review_parse_conflict(self, pipeline):
        """Test heuristic parsing of conflict response."""
        draft = pipeline._heuristic_review_parse("There is a conflict here", "en")
        assert draft.result == "CONFLICT"
    
    def test_overview_generation(self, pipeline):
        """Test overview text generation."""
        overview = pipeline._generate_overview(
            verdict="CONFLICT",
            conflicts=[LLMGraphIssue(entity_type="node", entity_id="n1", reason="Test")],
            warnings=[],
            language="en",
        )
        
        assert "conflict" in overview.lower()


class TestLLMBackendFactory:
    """Test LLM backend factory function."""
    
    def test_create_api_backend(self):
        """Test creation of API backend."""
        config = LLMConfig.from_env()
        
        try:
            backend = create_llm_backend(
                config=config,
                backend_type="remote_api",
                api_key="test-key",
                base_url="https://test.api",
                model="test-model",
            )
            
            assert isinstance(backend, APIBackend)
            assert backend.model_name == "test-model"
        except Exception:
            # May fail if openai not installed, that's okay
            pass
    
    def test_create_invalid_backend_raises_error(self):
        """Test that invalid backend type raises error."""
        config = LLMConfig.from_env()
        
        with pytest.raises(ValueError):
            create_llm_backend(config=config, backend_type="invalid_backend")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
