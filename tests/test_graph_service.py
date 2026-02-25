"""Tests for GraphService business logic."""

from __future__ import annotations

import pytest

from backend.services import GraphService
from datamodels.graph_models import (
    NodeCreatePayload,
    Position,
    ConnectionCreatePayload,
    ConnectionType,
)


class TestGraphServiceNodes:
    """Test suite for node operations."""

    def test_create_node_success(self, graph_service: GraphService, sample_node_payload: NodeCreatePayload):
        """Should create a node successfully."""
        node = graph_service.create_node(sample_node_payload, actor="test-user")
        
        assert node.content == "Test node content"
        assert node.summary == "Test summary"
        assert node.position.x == 100.0
        assert node.position.y == 200.0
        assert node.color == "#ff0000"
        assert node.size == 1.5
        assert node.tags == ["test", "sample"]
        assert node.confidence == 0.8
        assert node.evidence == ["source1"]
        assert node.is_deleted is False
        assert node.version == 1

    def test_create_node_empty_content_raises(self, graph_service: GraphService):
        """Should raise ValueError for empty content."""
        payload = NodeCreatePayload(
            content="   ",  # whitespace only
            summary="",
            position=Position(x=0.0, y=0.0),
            color="",
            size=1.0,
            tags=[],
            confidence=1.0,
            evidence=[],
        )
        
        with pytest.raises(ValueError, match="content"):
            graph_service.create_node(payload, actor="test-user")

    def test_create_node_strips_whitespace(self, graph_service: GraphService):
        """Should strip whitespace from content and summary."""
        payload = NodeCreatePayload(
            content="  Content with spaces  ",
            summary="  Summary with spaces  ",
            position=Position(x=0.0, y=0.0),
            color="",
            size=1.0,
            tags=[],
            confidence=1.0,
            evidence=[],
        )
        
        node = graph_service.create_node(payload, actor="test-user")
        assert node.content == "Content with spaces"
        assert node.summary == "Summary with spaces"

    def test_list_nodes_empty(self, graph_service: GraphService):
        """Should return empty list when no nodes."""
        nodes = graph_service.list_nodes()
        assert nodes == []

    def test_list_nodes_excludes_deleted_by_default(self, graph_service: GraphService):
        """Should exclude deleted nodes by default."""
        # Create a node
        payload = NodeCreatePayload(
            content="Test node",
            summary="",
            position=Position(x=0.0, y=0.0),
            color="",
            size=1.0,
            tags=[],
            confidence=1.0,
            evidence=[],
        )
        node = graph_service.create_node(payload, actor="test-user")
        
        # Soft delete it
        graph_service.delete_node(node.id, actor="test-user")
        
        # Should not appear in default list
        nodes = graph_service.list_nodes()
        assert len(nodes) == 0
        
        # Should appear when include_deleted=True
        nodes = graph_service.list_nodes(include_deleted=True)
        assert len(nodes) == 1

    def test_get_node_not_found(self, graph_service: GraphService):
        """Should return None for non-existent node."""
        result = graph_service.get_node("non-existent-id")
        assert result is None


class TestGraphServiceConnections:
    """Test suite for connection operations."""

    def test_create_connection_success(
        self, 
        graph_service: GraphService, 
        sample_node_payload: NodeCreatePayload,
        sample_connection_payload: ConnectionCreatePayload,
    ):
        """Should create a connection between two nodes."""
        # Create two nodes first
        node1 = graph_service.create_node(sample_node_payload, actor="test-user")
        node2_payload = NodeCreatePayload(
            content="Second node",
            summary="",
            position=Position(x=10.0, y=10.0),
            color="",
            size=1.0,
            tags=[],
            confidence=1.0,
            evidence=[],
        )
        node2 = graph_service.create_node(node2_payload, actor="test-user")
        
        # Update payload with actual node IDs
        from datamodels.graph_models import ConnectionCreatePayload
        conn_payload = ConnectionCreatePayload(
            source_id=node1.id,
            target_id=node2.id,
            conn_type=ConnectionType.SUPPORTS,
            description="Test connection",
            strength=0.9,
        )
        
        conn = graph_service.create_connection(conn_payload, actor="test-user")
        
        assert conn.source_id == node1.id
        assert conn.target_id == node2.id
        assert conn.conn_type == ConnectionType.SUPPORTS
        assert conn.description == "Test connection"
        assert conn.strength == 0.9
        assert conn.is_deleted is False

    def test_create_connection_self_loop_raises(
        self, 
        graph_service: GraphService, 
        sample_node_payload: NodeCreatePayload,
    ):
        """Should raise ValueError for self-loop connections."""
        node = graph_service.create_node(sample_node_payload, actor="test-user")
        
        from datamodels.graph_models import ConnectionCreatePayload
        payload = ConnectionCreatePayload(
            source_id=node.id,
            target_id=node.id,
            conn_type=ConnectionType.RELATES,
            description="",
            strength=1.0,
        )
        
        with pytest.raises(ValueError, match="Self-loop"):
            graph_service.create_connection(payload, actor="test-user")

    def test_create_connection_nonexistent_source_raises(
        self, 
        graph_service: GraphService, 
        sample_node_payload: NodeCreatePayload,
    ):
        """Should raise ValueError for non-existent source node."""
        node = graph_service.create_node(sample_node_payload, actor="test-user")
        
        from datamodels.graph_models import ConnectionCreatePayload
        payload = ConnectionCreatePayload(
            source_id="non-existent",
            target_id=node.id,
            conn_type=ConnectionType.SUPPORTS,
            description="",
            strength=1.0,
        )
        
        with pytest.raises(ValueError, match="Source/target node"):
            graph_service.create_connection(payload, actor="test-user")
