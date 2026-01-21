"""
Test script for WHERE clause extraction and comparison.
"""

from text2cypher.evaluation.static import (
    CypherExtractor,
)

extractor = CypherExtractor()

def exec_experiment(query1: str, query2: str):
    # Extract patterns
    cypher_query1 = extractor.extract_query(query1)
    cypher_query2 = extractor.extract_query(query2)

    pattern1 = cypher_query1.union_queries[0].match_pattern
    pattern2 = cypher_query2.union_queries[0].match_pattern
    
    print(f"\nQuery 1: {query1}")
    print(cypher_query1.union_queries[0])
    
    print(f"\nQuery 2: {query2}")
    print(cypher_query2.union_queries[0])
    
    # Compute similarity
    if pattern1.where and pattern2.where:
        similarity = pattern1.where.similarity_score(pattern2.where)
        print(f"\nWHERE clause similarity: {similarity:.4f}")
    
    print()

def test_simple_where_clause():
    """Test extraction of simple WHERE clause."""
    print("=" * 80)
    print("Test 1: Simple WHERE clause extraction")
    print("=" * 80)
    
    query1 = "MATCH (a:Person)-[:KNOWS]->(b:Person) WHERE a.age > f + b + c RETURN a"
    query2 = "MATCH (x:Person)-[:KNOWS]->(y:Person) WHERE x.age > c - f + b RETURN x"
    
    exec_experiment(query1, query2)
    
def test_complex_where_clause():
    """Test extraction of complex WHERE clause with AND/OR."""
    print("=" * 80)
    print("Test 2: Complex WHERE clause with AND/OR")
    print("=" * 80)
    
    query1 = "MATCH (a:Person) WHERE a.age > 30 AND a.name = 'Alice' RETURN a"
    query2 = "MATCH (x:Person) WHERE x.name = 'Alice' AND x.age > 30 RETURN x"
    
    exec_experiment(query1, query2)

def test_different_where_clauses():
    """Test comparison of different WHERE clauses."""
    print("=" * 80)
    print("Test 3: Different WHERE clauses")
    print("=" * 80)
    
    query1 = "MATCH (a:Person) WHERE a.age > 30 RETURN a"
    query2 = "MATCH (x:Person) WHERE x.age < 25 RETURN x"
    
    exec_experiment(query1, query2)

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("WHERE CLAUSE EXTRACTION AND COMPARISON TESTS")
    print("=" * 80 + "\n")
    
    import traceback

    try:
        test_simple_where_clause()
    except Exception as e:
        print(f"Test 1 failed: {e}\n")
        traceback.print_exc()
    
    # try:
    #     test_complex_where_clause()
    # except Exception as e:
    #     print(f"Test 2 failed: {e}\n")
    
    # try:
    #     test_different_where_clauses()
    # except Exception as e:
    #     print(f"Test 3 failed: {e}\n")
    
    print("=" * 80)
    print("TESTS COMPLETED")
    print("=" * 80)
