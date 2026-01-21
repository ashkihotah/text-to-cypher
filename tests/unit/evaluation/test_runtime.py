"""
Test script for runtime evaluation functions: jaccard and provenance_subgraph_jaccard_similarity.
"""

import pytest
from unittest.mock import Mock, MagicMock

from text2cypher.evaluation.runtime import (
    jaccard,
    df_sim,
    rowsim,
    make_hashable,
    make_alignment,
)
from text2cypher.evaluation.psj_similarity import (
    provenance_subgraph_jaccard_similarity,
    get_ps_cypher,
    split_by_union,
    extract_match_cypher,
    add_variables,
    extract_node_variables,
    extract_relationship_variables,
)


# =============================================================================
# Test fixtures and helpers
# =============================================================================

@pytest.fixture
def mock_neo4j():
    """Create a mock Neo4jGraph object."""
    return Mock()


def create_mock_neo4j_with_responses(responses: dict):
    """
    Create a mock Neo4jGraph that returns specific responses for specific queries.
    
    Args:
        responses: Dict mapping query strings to their expected return values.
    """
    mock = Mock()
    
    def query_side_effect(query):
        # Check for exact match first
        if query in responses:
            return responses[query]
        # Check for partial match (for generated PS queries)
        for key, value in responses.items():
            if key in query:
                return value
        return []
    
    mock.query = Mock(side_effect=query_side_effect)
    return mock


# =============================================================================
# Tests for helper functions
# =============================================================================

class TestRowSim:
    """Tests for rowsim function."""
    
    def test_identical_sets(self):
        """Identical sets should have similarity of 1.0."""
        set_a = {1, 2, 3}
        set_b = {1, 2, 3}
        assert rowsim(set_a, set_b) == 1.0
    
    def test_disjoint_sets(self):
        """Disjoint sets should have similarity of 0.0."""
        set_a = {1, 2, 3}
        set_b = {4, 5, 6}
        assert rowsim(set_a, set_b) == 0.0
    
    def test_partial_overlap(self):
        """Partially overlapping sets should have intermediate similarity."""
        set_a = {1, 2, 3}
        set_b = {2, 3, 4}
        # Intersection: {2, 3} = 2 elements
        # Union: {1, 2, 3, 4} = 4 elements
        assert rowsim(set_a, set_b) == 0.5
    
    def test_subset_relationship(self):
        """When one set is subset of another."""
        set_a = {1, 2}
        set_b = {1, 2, 3, 4}
        # Intersection: {1, 2} = 2 elements
        # Union: {1, 2, 3, 4} = 4 elements
        assert rowsim(set_a, set_b) == 0.5


class TestMakeHashable:
    """Tests for make_hashable function."""
    
    def test_string_passthrough(self):
        """Strings should pass through unchanged."""
        assert make_hashable("hello") == "hello"
    
    def test_integer_to_float(self):
        """Integers should be converted to floats."""
        assert make_hashable(42) == 42.0
    
    def test_list_converted_to_string(self):
        """Lists should be converted to string representation."""
        result = make_hashable([1, 2, 3])
        assert isinstance(result, str)
    
    def test_dict_converted_to_string(self):
        """Dicts should be converted to string representation."""
        result = make_hashable({"a": 1})
        assert isinstance(result, str)


class TestDfSim:
    """Tests for df_sim function."""
    
    def test_identical_results(self):
        """Identical result sets should have similarity of 1.0."""
        dict_l = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        dict_r = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        assert df_sim(dict_l, dict_r, list_view=False) == 1.0
    
    def test_empty_results(self):
        """Empty result sets should have similarity of 1.0."""
        assert df_sim([], [], list_view=False) == 1.0
    
    def test_completely_different_results(self):
        """Completely different results should have similarity of 0.0."""
        dict_l = [{"name": "Alice"}]
        dict_r = [{"name": "Bob"}]
        assert df_sim(dict_l, dict_r, list_view=False) == 0.0
    
    def test_partial_overlap_unordered(self):
        """Partially overlapping results without order consideration."""
        # When lists have same length, alignment reorders to maximize overlap
        # Bob is in position 0 in L, but position 0 in R is also Bob -> aligned
        dict_l = [{"name": "Bob"}, {"name": "Alice"}]
        dict_r = [{"name": "Bob"}, {"name": "Charlie"}]
        # After alignment: Bob-Bob (row 0), Alice-Charlie (row 1)
        # Total: {(0, Bob), (1, Alice)} vs {(0, Bob), (1, Charlie)}
        # Intersection = {(0, Bob)}, Union = {(0, Bob), (1, Alice), (1, Charlie)}
        sim = df_sim(dict_l, dict_r, list_view=False)
        # Expected: 1/3 ≈ 0.333
        assert sim == pytest.approx(1/3, rel=0.01)
    
    def test_same_data_different_order_unordered(self):
        """Same data in different order should have similarity of 1.0 when unordered."""
        dict_l = [{"name": "Alice"}, {"name": "Bob"}]
        dict_r = [{"name": "Bob"}, {"name": "Alice"}]
        assert df_sim(dict_l, dict_r, list_view=False) == 1.0
    
    def test_same_data_different_order_ordered(self):
        """Same data in different order should have lower similarity when ordered."""
        dict_l = [{"name": "Alice"}, {"name": "Bob"}]
        dict_r = [{"name": "Bob"}, {"name": "Alice"}]
        # When list_view=True, order matters
        sim = df_sim(dict_l, dict_r, list_view=True)
        assert sim < 1.0


# =============================================================================
# Tests for jaccard function
# =============================================================================

class TestJaccard:
    """Tests for the jaccard function."""
    
    def test_identical_queries_same_results(self, mock_neo4j):
        """Identical query results should return similarity of 1.0."""
        query = "MATCH (p:Person) RETURN p.name"
        results = [{"p.name": "Alice"}, {"p.name": "Bob"}]
        mock_neo4j.query = Mock(return_value=results)
        
        # Note: jaccard has an erroneous 'self' parameter
        similarity = jaccard(None, query, query, mock_neo4j)
        assert similarity == 1.0
    
    def test_completely_different_results(self, mock_neo4j):
        """Completely different results should return similarity of 0.0."""
        query_l = "MATCH (p:Person) WHERE p.name = 'Alice' RETURN p.name"
        query_r = "MATCH (p:Person) WHERE p.name = 'Bob' RETURN p.name"
        
        mock_neo4j.query = Mock(side_effect=[
            [{"p.name": "Alice"}],
            [{"p.name": "Bob"}]
        ])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        assert similarity == 0.0
    
    def test_partial_overlap_results(self, mock_neo4j):
        """Partially overlapping results should return intermediate similarity."""
        query_l = "MATCH (p:Person) RETURN p.name"
        query_r = "MATCH (p:Person) WHERE p.age > 25 RETURN p.name"
        
        # Results with partial overlap - alignment will pair rows to maximize similarity
        # Bob appears first in both, so it aligns properly
        mock_neo4j.query = Mock(side_effect=[
            [{"p.name": "Bob"}, {"p.name": "Alice"}],
            [{"p.name": "Bob"}, {"p.name": "Charlie"}]
        ])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        # After alignment: Bob-Bob (row 0), Alice-Charlie (row 1)
        # Intersection = {(0, Bob)}, Union = {(0, Bob), (1, Alice), (1, Charlie)}
        # Similarity = 1/3
        assert similarity == pytest.approx(1/3, rel=0.01)
    
    def test_empty_results_both(self, mock_neo4j):
        """Both queries returning empty results should return 1.0."""
        query_l = "MATCH (p:Person) WHERE p.age > 100 RETURN p.name"
        query_r = "MATCH (p:Person) WHERE p.age > 200 RETURN p.name"
        
        mock_neo4j.query = Mock(return_value=[])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        assert similarity == 1.0
    
    def test_order_by_affects_comparison(self, mock_neo4j):
        """Queries with ORDER BY should use ordered comparison."""
        query_l = "MATCH (p:Person) RETURN p.name ORDER BY p.name"
        query_r = "MATCH (p:Person) RETURN p.name ORDER BY p.name DESC"
        
        mock_neo4j.query = Mock(side_effect=[
            [{"p.name": "Alice"}, {"p.name": "Bob"}],
            [{"p.name": "Bob"}, {"p.name": "Alice"}]
        ])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        # With order consideration, different ordering should affect similarity
        assert similarity < 1.0
    
    def test_numeric_values_comparison(self, mock_neo4j):
        """Numeric values should be properly compared."""
        query_l = "MATCH (p:Person) RETURN p.age"
        query_r = "MATCH (p:Person) RETURN p.age"
        
        mock_neo4j.query = Mock(side_effect=[
            [{"p.age": 30}, {"p.age": 25}],
            [{"p.age": 30}, {"p.age": 25}]
        ])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        assert similarity == 1.0
    
    def test_mixed_types_comparison(self, mock_neo4j):
        """Mixed types in results should be handled properly."""
        query_l = "MATCH (p:Person) RETURN p.name, p.age"
        query_r = "MATCH (p:Person) RETURN p.name, p.age"
        
        mock_neo4j.query = Mock(side_effect=[
            [{"p.name": "Alice", "p.age": 30}],
            [{"p.name": "Alice", "p.age": 30}]
        ])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        assert similarity == 1.0


# =============================================================================
# Tests for PSJ helper functions
# =============================================================================

class TestSplitByUnion:
    """Tests for split_by_union function."""
    
    def test_simple_query_no_union(self):
        """Query without UNION should return single element list."""
        cypher = "MATCH (p:Person) RETURN p"
        result = split_by_union(cypher)
        assert len(result) == 1
        assert result[0] == cypher
    
    def test_query_with_union(self):
        """Query with UNION should be split correctly."""
        cypher = "MATCH (p:Person) RETURN p UNION MATCH (t:Team) RETURN t"
        result = split_by_union(cypher)
        assert len(result) == 2
        assert "MATCH (p:Person)" in result[0]
        assert "MATCH (t:Team)" in result[1]


class TestExtractMatchCypher:
    """Tests for extract_match_cypher function."""
    
    def test_simple_match_query(self):
        """Simple MATCH query extraction."""
        cypher = "MATCH (p:Person) RETURN p"
        result = extract_match_cypher(cypher)
        assert result == "MATCH (p:Person)"
    
    def test_match_with_where(self):
        """MATCH with WHERE clause extraction."""
        cypher = "MATCH (p:Person) WHERE p.age > 30 RETURN p"
        result = extract_match_cypher(cypher)
        assert "MATCH (p:Person)" in result
        assert "WHERE p.age > 30" in result
    
    def test_non_match_query(self):
        """Non-MATCH query should return None."""
        cypher = "CREATE (p:Person {name: 'Alice'})"
        result = extract_match_cypher(cypher)
        assert result is None


class TestAddVariables:
    """Tests for add_variables function."""
    
    def test_add_node_variables(self):
        """Should add temporary variables to anonymous nodes."""
        cypher = "MATCH (:Person)-[:KNOWS]->(:Person)"
        result = add_variables(cypher)
        assert "ntmp" in result
    
    def test_add_relationship_variables(self):
        """Should add temporary variables to anonymous relationships."""
        cypher = "MATCH (p:Person)-[:KNOWS]->(q:Person)"
        result = add_variables(cypher)
        assert "rtmp" in result


class TestExtractNodeVariables:
    """Tests for extract_node_variables function."""
    
    def test_extract_named_nodes(self):
        """Should extract named node variables."""
        cypher = "MATCH (p:Person)-[:KNOWS]->(q:Person)"
        result = extract_node_variables(cypher)
        assert "p" in result
        assert "q" in result
    
    def test_extract_with_properties(self):
        """Should extract variables from nodes with properties."""
        cypher = "MATCH (p:Person {name: 'Alice'})"
        result = extract_node_variables(cypher)
        assert "p" in result


class TestExtractRelationshipVariables:
    """Tests for extract_relationship_variables function."""
    
    def test_extract_named_relationships(self):
        """Should extract named relationship variables."""
        cypher = "MATCH (p:Person)-[r:KNOWS]->(q:Person)"
        result = extract_relationship_variables(cypher)
        assert "r" in result


# =============================================================================
# Tests for provenance_subgraph_jaccard_similarity function
# =============================================================================

class TestProvenanceSubgraphJaccardSimilarity:
    """Tests for provenance_subgraph_jaccard_similarity function."""
    
    def test_identical_queries(self, mock_neo4j):
        """Identical queries should return similarity of 1.0."""
        cypher = "MATCH (p:Person) RETURN p.name"
        
        similarity = provenance_subgraph_jaccard_similarity(cypher, cypher, mock_neo4j)
        assert similarity == 1.0
        # Should not call neo4j.query for identical queries
        mock_neo4j.query.assert_not_called()
    
    def test_same_provenance_subgraph(self, mock_neo4j):
        """Different queries with same provenance should return 1.0."""
        pred_cypher = "MATCH (p:Person) RETURN p.name"
        target_cypher = "MATCH (p:Person) RETURN p.age"
        
        # Both queries should return the same node element IDs
        mock_neo4j.query = Mock(return_value=[
            {"elemId1": "node1"}, {"elemId1": "node2"}
        ])
        
        # Override for second query
        def query_side_effect(query):
            if "elemId1" in query:
                return [{"elemId1": "node1"}, {"elemId1": "node2"}]
            if "elemId2" in query:
                return [{"elemId2": "node1"}, {"elemId2": "node2"}]
            return []
        
        mock_neo4j.query = Mock(side_effect=query_side_effect)
        
        similarity = provenance_subgraph_jaccard_similarity(pred_cypher, target_cypher, mock_neo4j)
        assert similarity == 1.0
    
    def test_completely_different_provenance(self, mock_neo4j):
        """Queries with disjoint provenance should return 0.0."""
        pred_cypher = "MATCH (p:Person) WHERE p.name = 'Alice' RETURN p"
        target_cypher = "MATCH (t:Team) WHERE t.name = 'Bulls' RETURN t"
        
        def query_side_effect(query):
            if "elemId1" in query:
                return [{"elemId1": "node1"}, {"elemId1": "node2"}]
            if "elemId2" in query:
                return [{"elemId2": "node3"}, {"elemId2": "node4"}]
            return []
        
        mock_neo4j.query = Mock(side_effect=query_side_effect)
        
        similarity = provenance_subgraph_jaccard_similarity(pred_cypher, target_cypher, mock_neo4j)
        assert similarity == 0.0
    
    def test_partial_provenance_overlap(self, mock_neo4j):
        """Queries with partial provenance overlap should return intermediate value."""
        pred_cypher = "MATCH (p:Person) RETURN p"
        target_cypher = "MATCH (p:Person)-[:KNOWS]->(q:Person) RETURN p, q"
        
        def query_side_effect(query):
            if "elemId1" in query:
                return [{"elemId1": "node1"}, {"elemId1": "node2"}, {"elemId1": "node3"}]
            if "elemId2" in query:
                return [{"elemId2": "node1"}, {"elemId2": "node4"}]
            return []
        
        mock_neo4j.query = Mock(side_effect=query_side_effect)
        
        similarity = provenance_subgraph_jaccard_similarity(pred_cypher, target_cypher, mock_neo4j)
        # Intersection: {node1} = 1, Union: {node1, node2, node3, node4} = 4
        assert similarity == 0.25
    
    def test_empty_provenance_both(self, mock_neo4j):
        """Both queries with empty provenance should return 0.0."""
        pred_cypher = "MATCH (p:Person) WHERE p.name = 'NonExistent' RETURN p"
        target_cypher = "MATCH (t:Team) WHERE t.name = 'NonExistent' RETURN t"
        
        mock_neo4j.query = Mock(return_value=[])
        
        similarity = provenance_subgraph_jaccard_similarity(pred_cypher, target_cypher, mock_neo4j)
        assert similarity == 0.0
    
    def test_exception_handling(self, mock_neo4j):
        """Should return 0.0 when Neo4j query fails."""
        pred_cypher = "MATCH (p:Person) RETURN p"
        target_cypher = "MATCH (t:Team) RETURN t"
        
        mock_neo4j.query = Mock(side_effect=Exception("Connection failed"))
        
        similarity = provenance_subgraph_jaccard_similarity(pred_cypher, target_cypher, mock_neo4j)
        assert similarity == 0.0
    
    def test_complex_match_pattern(self, mock_neo4j):
        """Test with complex MATCH patterns."""
        pred_cypher = "MATCH (p:Player)-[:playsFor]->(t:Team) WHERE t.name = 'Bulls' RETURN p.name"
        target_cypher = "MATCH (p:Player)-[:playsFor]->(t:Team) WHERE t.name = 'Bulls' RETURN p.name, t.name"
        
        def query_side_effect(query):
            if "elemId1" in query:
                return [{"elemId1": "player1"}, {"elemId1": "team1"}]
            if "elemId2" in query:
                return [{"elemId2": "player1"}, {"elemId2": "team1"}]
            return []
        
        mock_neo4j.query = Mock(side_effect=query_side_effect)
        
        similarity = provenance_subgraph_jaccard_similarity(pred_cypher, target_cypher, mock_neo4j)
        assert similarity == 1.0
    
    def test_query_with_optional_match(self, mock_neo4j):
        """Test queries with OPTIONAL MATCH."""
        pred_cypher = "MATCH (p:Person) OPTIONAL MATCH (p)-[:KNOWS]->(q) RETURN p, q"
        target_cypher = "MATCH (p:Person) RETURN p"
        
        def query_side_effect(query):
            if "elemId1" in query:
                return [{"elemId1": "person1"}]
            if "elemId2" in query:
                return [{"elemId2": "person1"}, {"elemId2": "person2"}]
            return []
        
        mock_neo4j.query = Mock(side_effect=query_side_effect)
        
        similarity = provenance_subgraph_jaccard_similarity(pred_cypher, target_cypher, mock_neo4j)
        # Intersection: {person1} = 1, Union: {person1, person2} = 2
        assert similarity == 0.5


# =============================================================================
# Integration-style tests with realistic query samples
# =============================================================================

class TestRealisticQuerySamples:
    """Tests using realistic Cypher query samples."""
    
    def test_player_team_queries(self, mock_neo4j):
        """Test NBA-style player/team queries."""
        # Predicted query - finds all players
        pred = "MATCH (p:Player) RETURN p.name"
        # Target query - finds players on a specific team
        target = "MATCH (p:Player)-[:playsFor]->(t:Team {name: 'Lakers'}) RETURN p.name"
        
        def query_side_effect(query):
            if "elemId1" in query:
                # Target returns only Lakers players
                return [{"elemId1": "lebron"}, {"elemId1": "lakers_team"}]
            if "elemId2" in query:
                # Predicted returns all players
                return [{"elemId2": "lebron"}, {"elemId2": "curry"}, {"elemId2": "durant"}]
            return []
        
        mock_neo4j.query = Mock(side_effect=query_side_effect)
        
        similarity = provenance_subgraph_jaccard_similarity(pred, target, mock_neo4j)
        # Intersection: {lebron} = 1, Union: {lebron, lakers_team, curry, durant} = 4
        assert similarity == 0.25
    
    def test_movie_actor_queries_jaccard(self, mock_neo4j):
        """Test movie/actor database queries with jaccard."""
        query_l = "MATCH (m:Movie)<-[:ACTED_IN]-(a:Actor) WHERE m.year > 2000 RETURN a.name"
        query_r = "MATCH (m:Movie)<-[:ACTED_IN]-(a:Actor) WHERE m.year > 2000 RETURN a.name ORDER BY a.name"
        
        mock_neo4j.query = Mock(side_effect=[
            [{"a.name": "Tom Hanks"}, {"a.name": "Leonardo DiCaprio"}],
            [{"a.name": "Leonardo DiCaprio"}, {"a.name": "Tom Hanks"}]
        ])
        
        # ORDER BY in query_r means ordered comparison
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        # Order differs, so similarity should be less than 1.0
        assert similarity < 1.0
    
    def test_count_aggregation_queries(self, mock_neo4j):
        """Test queries with COUNT aggregation."""
        query_l = "MATCH (p:Person) RETURN count(p) as total"
        query_r = "MATCH (p:Person) RETURN count(p) as cnt"
        
        mock_neo4j.query = Mock(side_effect=[
            [{"total": 100}],
            [{"cnt": 100}]
        ])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        # Same count value, different column name - values should match
        assert similarity == 1.0


# =============================================================================
# Edge cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_single_row_results(self, mock_neo4j):
        """Test with single row results."""
        query_l = "MATCH (p:Person {name: 'Alice'}) RETURN p.name"
        query_r = "MATCH (p:Person {name: 'Alice'}) RETURN p.name"
        
        mock_neo4j.query = Mock(return_value=[{"p.name": "Alice"}])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        assert similarity == 1.0
    
    def test_large_result_sets(self, mock_neo4j):
        """Test with larger result sets."""
        query_l = "MATCH (p:Person) RETURN p.name"
        query_r = "MATCH (p:Person) RETURN p.name"
        
        # Generate large result sets
        results = [{"p.name": f"Person_{i}"} for i in range(1000)]
        mock_neo4j.query = Mock(return_value=results)
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        assert similarity == 1.0
    
    def test_null_values_in_results(self, mock_neo4j):
        """Test handling of NULL values in results."""
        query_l = "MATCH (p:Person) RETURN p.nickname"
        query_r = "MATCH (p:Person) RETURN p.nickname"
        
        mock_neo4j.query = Mock(return_value=[
            {"p.nickname": None},
            {"p.nickname": "Bob"}
        ])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        assert similarity == 1.0
    
    def test_special_characters_in_values(self, mock_neo4j):
        """Test handling of special characters in values."""
        query_l = "MATCH (p:Person) RETURN p.name"
        query_r = "MATCH (p:Person) RETURN p.name"
        
        mock_neo4j.query = Mock(return_value=[
            {"p.name": "O'Brien"},
            {"p.name": "José García"},
            {"p.name": "李明"}
        ])
        
        similarity = jaccard(None, query_l, query_r, mock_neo4j)
        assert similarity == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
