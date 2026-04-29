
## Question

I've developed the following methods to find the optimal nodes and edges variable mappings between two valid cypher queries:

```
    # WARNING: Worst case complexity is O(n!) when both sets are of equal size.
    @staticmethod
    def _generate_injective_mappings(
        source_variables: list[str],
        target_variables: list[str],
    ) -> Iterator[dict[str, str]]:
        """
        The number of mappings generated is:
            P(n, k) = n! / (n-k)! where n = len(larger_set), k = len(smaller_set)
        
        The worst-case complexity is O(n!) when both sets are of equal size.
        """
        if not source_variables and not target_variables:
            yield {}
            return

        if not source_variables or not target_variables:
            yield {}
            return

        source_is_smaller = len(source_variables) <= len(target_variables)

        if source_is_smaller:
            smaller_set = source_variables
            larger_set = target_variables
        else:
            smaller_set = target_variables
            larger_set = source_variables

        for permutation in itertools.permutations(larger_set, len(smaller_set)):
            if source_is_smaller:
                yield dict(zip(smaller_set, permutation))
            else:
                yield {large: small for small, large in zip(smaller_set, permutation)}

    # TODO: Add support for subgraph mappings
    def find_optimal_mapping(
        self,
        other: GraphPattern,
        score_fn: Callable[[GraphPattern, GraphPattern], float],
        minimize: bool = False,
    ) -> tuple[float, GraphPattern.Mapping]:
        """Find the optimal variable mapping between this pattern and another.

        Exhaustively searches all possible combinations of node and edge variable
        mappings to find the one that optimizes the given metric. This enables
        variable-agnostic pattern comparison by finding the best alignment.

        Parameters
        ----------
        other : GraphPattern
            The target GraphPattern to map to.
        score_fn : Callable[[GraphPattern, GraphPattern], float]
            A callable that takes two GraphPatterns and returns a float score.
            Signature: metric(mapped_self, other) -> float.
            The first argument will be this pattern with variables remapped,
            the second is the target pattern (unchanged).
        minimize : bool, default=False
            If True, find mapping that minimizes the metric (e.g., for distance).
            If False, find mapping that maximizes it (e.g., for similarity).

        Returns
        -------
        tuple[float, GraphPattern.Mapping]
            A tuple of (best_score, best_mapping) where:
            - best_score: The optimal metric value achieved
            - best_mapping: A GraphPattern.Mapping containing the optimal node
              and edge variable mappings that produced the best score
        
        Notes
        -----
        Complexity: O(P(n, k) * P(m, l) * metric_cost) where:
            - P(n, k) = n!/(n-k)! is the number of node mappings
            - P(m, l) = m!/(m-l)! is the number of edge mappings
            - metric_cost is the cost of evaluating the similarity metric

        The worst-case complexity is O(N_nodes! x N_edges!) when both sets are of equal size.
        
        For large patterns, this exhaustive search can be expensive. Consider
        using heuristic approaches for very large patterns.
        
        Special case: If both patterns are completely empty (no nodes and no edges),
        returns (metric_score, empty_mapping).
        
        Examples
        --------
        >>> pattern1 = GraphPattern()  # (a:Person)-[r:KNOWS]->(b:Person)
        >>> pattern2 = GraphPattern()  # (x:Person)-[s:KNOWS]->(y:Person)
        >>> score, mapping = pattern1.find_optimal_mapping(
        ...     pattern2,
        ...     score_fn=lambda p1, p2: p1.jaccard(p2),
        ...     minimize=False
        ... )
        >>> # mapping.nodes_map might be {'a': 'x', 'b': 'y'}
        >>> # mapping.edges_map might be {'r': 's'}
        """
        source_node_variables = list(self.nodes.keys())
        target_node_variables = list(other.nodes.keys())
        source_edge_variables = list(self.edges.keys())
        target_edge_variables = list(other.edges.keys())

        is_empty = (
            not source_node_variables
            and not target_node_variables
            and not source_edge_variables
            and not target_edge_variables
        )
        if is_empty:
            return score_fn(self, other), GraphPattern.Mapping()

        best_mapping = GraphPattern.Mapping()

        if minimize:
            best_score = float('inf')
            is_better = lambda new, old: new < old
        else:
            best_score = float('-inf')
            is_better = lambda new, old: new > old

        node_mapping_candidates = list(
            self._generate_injective_mappings(
                source_node_variables, target_node_variables
            )
        )
        edge_mapping_candidates = list(
            self._generate_injective_mappings(
                source_edge_variables, target_edge_variables
            )
        )

        for node_map in node_mapping_candidates:
            for edge_map in edge_mapping_candidates:
                candidate_mapping = GraphPattern.Mapping(
                    nodes_map=node_map,
                    edges_map=edge_map,
                )

                aligned_pattern = self.apply_mapping(candidate_mapping)
                score = score_fn(aligned_pattern, other)

                if is_better(score, best_score):
                    best_score = score
                    best_mapping = candidate_mapping

        return best_score, best_mapping

```

These methods are crucial to assess the similarity between two `GraphPattern`s assuming the following class implementation:

```
class GraphPattern:
    """Represents the extracted graph structure from a Cypher query.

    This class stores nodes and edges extracted from MATCH clauses in Cypher
    queries, providing methods for comparison, mapping, and similarity computation.
    It supports variable-agnostic comparison through optimal mapping search and
    provides Jaccard similarity metrics for graph pattern matching.

    Attributes
    ----------
    nodes : dict[str, GraphPattern.Node]
        Dictionary mapping variable names to Node instances. Each key is a
        variable name (or anonymous variable) and each value contains the
        node's labels and properties.
    edges : dict[str, GraphPattern.Edge]
        Dictionary mapping variable names to Edge instances. Each key is a
        relationship variable name (or anonymous variable) and each value
        contains the edge's source, target, labels, and properties.
    sub_graphs : dict[str, GraphPattern.SubGraph]
        Dictionary mapping variable names to SubGraph instances for named
        path patterns.
    where : CypherExpression
        CypherExpression representing the WHERE clause. Default is an empty
        WHERE expression node.

    Methods
    -------
    add_node(labels, properties, variable=None) -> str
        Add a node to the graph pattern or merge with existing node.
    add_edge(from_node, to_node, labels, properties, edge_variable=None, range_literal=None) -> str
        Add an edge to the graph pattern or merge with existing edge.
    add_subgraph(variable) -> GraphPattern.SubGraph
        Add a subgraph to the graph pattern.
    apply_mapping(mapping) -> GraphPattern
        Create a new GraphPattern with variables renamed according to the mapping.
    jaccard(other) -> float
        Calculate Jaccard similarity between this GraphPattern and another.
    find_optimal_mapping(other, score_fn, minimize=False) -> tuple[float, GraphPattern.Mapping]
        Find the optimal variable mapping between this pattern and another.

    Notes
    -----
    Nested Classes:
        Node: Represents a graph node with labels and properties.
        Edge: Represents a relationship/edge between nodes.
        Mapping: Represents variable mappings between two patterns.
        SubGraph: Represents a named path pattern.

    Examples
    --------
    >>> pattern = GraphPattern()
    >>> var = pattern.add_node(labels={'Person'}, properties={'name': 'Alice'})
    >>> print(pattern.nodes[var].labels)
    {'Person'}
    >>> 
    >>> # Add an edge between two nodes
    >>> n1 = pattern.add_node(labels={'Person'}, variable='a')
    >>> n2 = pattern.add_node(labels={'Person'}, variable='b')
    >>> e = pattern.add_edge(n1, n2, labels={'KNOWS'}, properties={})
    """

    @dataclass
    class Node:
        """Represents a node in the graph pattern with labels and properties.

        Parameters
        ----------
        labels : set[str], default=empty set
            Set of node labels (e.g., {'Person', 'Employee'}). A node can have
            zero or more labels. Labels are used to categorize nodes in the graph.
        properties : dict[str, CypherExpression], default=empty dict
            Dictionary of property key-value pairs where keys are property names
            and values are CypherExpression objects representing the property values.
            Properties can be literals, parameters, or more complex expressions.
        
        Attributes
        ----------
        labels : set[str]
            Set of node labels.
        properties : dict[str, CypherExpression]
            Dictionary of property key-value pairs.
        
        Examples
        --------
        >>> node = GraphPattern.Node(
        ...     labels={'Person', 'Employee'},
        ...     properties={'name': CypherExpression(node_type=ExpressionNodeType.LITERAL, value='Alice')}
        ... )
        """

        labels: set[str] = field(default_factory=set)
        properties: dict[str, CypherExpression] = field(default_factory=dict)

    @dataclass
    class Edge:
        """Represents a relationship/edge in the graph pattern.

        Parameters
        ----------
        from_node : str
            Variable name of the source node in the relationship.
        to_node : str
            Variable name of the target node in the relationship.
        labels : set[str], default=empty set
            Set of relationship types/labels (e.g., {'KNOWS', 'FRIENDS'}).
            In Cypher, multiple types can be specified with the | operator.
            An edge can have multiple relationship types.
        properties : dict[str, CypherExpression], default=empty dict
            Dictionary of property key-value pairs where keys are property names
            and values are CypherExpression objects representing the property values.
        variable : Optional[str], default=None
            Optional variable name for the relationship itself. If None, the
            relationship is anonymous.
        range_literal : Optional[str], default=None
            Optional range literal for variable-length relationships (e.g., '*1..5').
            Used for path patterns with variable-length relationships.
        
        Attributes
        ----------
        from_node : str
            Variable name of the source node.
        to_node : str
            Variable name of the target node.
        labels : set[str]
            Set of relationship types.
        properties : dict[str, CypherExpression]
            Dictionary of properties.
        variable : Optional[str]
            Variable name for the relationship.
        range_literal : Optional[str]
            Range specification for variable-length relationships.
        
        Methods
        -------
        __eq__(other: Any) -> bool
            Check equality between two Edge instances.
        
        Examples
        --------
        >>> edge = GraphPattern.Edge(
        ...     from_node='a',
        ...     to_node='b',
        ...     labels={'KNOWS'},
        ...     properties={},
        ...     variable='r'
        ... )
        """

        from_node: str
        to_node: str
        labels: set[str] = field(default_factory=set)
        properties: dict[str, CypherExpression] = field(default_factory=dict)
        variable: Optional[str] = None
        range_literal: Optional[str] = None

        def __eq__(self, other: Any) -> bool:
            """Check equality between two Edge instances.

            Edges are considered equal if they connect the same nodes
            regardless of their variable names, properties or labels.
            This is used for structural comparison during pattern matching.

            Parameters
            ----------
            other : Any
                The other object to compare against.
            
            Returns
            -------
            bool
                True if both edges connect the same source and target nodes,
                False otherwise.
            NotImplemented
                If other is not a GraphPattern.Edge instance.
            """
            if not isinstance(other, GraphPattern.Edge):
                return NotImplemented
            return (
                self.from_node == other.from_node
                and self.to_node == other.to_node
            )

    @dataclass
    class Mapping:
        """Represents a mapping of variables between two graph patterns.

        Used for aligning variable names when comparing graph patterns that
        may use different variable names for semantically equivalent structures.
        This is essential for variable-agnostic pattern comparison.

        Parameters
        ----------
        nodes_map : dict[str, str], default=empty dict
            Dictionary mapping source node variable names to target node variable
            names. Keys are variable names from the source pattern, values are
            corresponding variable names in the target pattern.
        edges_map : dict[str, str], default=empty dict
            Dictionary mapping source edge variable names to target edge variable
            names. Keys are variable names from the source pattern, values are
            corresponding variable names in the target pattern.
        
        Attributes
        ----------
        nodes_map : dict[str, str]
            Node variable mapping from source to target.
        edges_map : dict[str, str]
            Edge variable mapping from source to target.
        
        Examples
        --------
        >>> mapping = GraphPattern.Mapping(
        ...     nodes_map={'a': 'x', 'b': 'y'},
        ...     edges_map={'r': 's'}
        ... )
        >>> # This maps pattern (a)-[r]->(b) to pattern (x)-[s]->(y)
        """

        nodes_map: dict[str, str] = field(default_factory=dict)
        edges_map: dict[str, str] = field(default_factory=dict)

    @dataclass
    class SubGraph:
        nodes_vars: set[str] = field(default_factory=set)
        edges_vars: set[str] = field(default_factory=set)

    def __init__(self) -> None:
        """Initialize an empty GraphPattern.
        
        Creates a new GraphPattern with empty dictionaries for nodes, edges,
        and subgraphs, an empty WHERE expression, and initializes the anonymous
        variable counter to 0.
        
        Notes
        -----
        The anonymous counter is used to generate unique variable names for
        nodes and edges that don't have explicit variables in the Cypher query.
        """
        self.nodes: dict[str, GraphPattern.Node] = {}
        self.edges: dict[str, GraphPattern.Edge] = {}
        self.sub_graphs: dict[str, GraphPattern.SubGraph] = {}
        self.where: CypherExpression = CypherExpression(
            node_type=ExpressionNodeType.WHERE
        )
        self._anonymous_counter: int = 0
```

I noticed that the worst case complexities of both methods are infeasible. Knowing that distributions of number of nodes and edges in my dataset is the following:

```
Node counts statistics (successful extractions):
n_nodes
2.0    14048
1.0    10848
3.0     4006
4.0      519
5.0      125
6.0       30
7.0        7
9.0        2
8.0        1
Name: count, dtype: int64
Edge counts statistics (successful extractions):
n_edges
1.0    12978
0.0    12272
2.0     3675
3.0      485
4.0      132
5.0       32
6.0        8
8.0        2
7.0        1
9.0        1
Name: count, dtype: int64
```

Is it feasible to use them anyway?

## LLM Response

Excellent question. You've correctly identified the critical bottleneck in your approach and provided the exact data needed to analyze it.

Here is a detailed breakdown of the feasibility of your current methods and a clear strategy to fix the complexity problem.

### Part 1: Feasibility Analysis (Is it usable as-is?)

**The Short Answer:** **Yes, for about 99% of your dataset.** However, the remaining 1% of queries with 5 or more nodes will cause significant performance bottlenecks and may render the system unusable for those specific cases.

Let's break down why, using your data. The total number of mapping combinations is `P(N_nodes, k_nodes) * P(N_edges, l_edges)`.

Let's create a "Pain Matrix" assuming you're comparing two queries of the same size (`k=n`, so `P(n,n) = n!`).

| Nodes (n) | Edges (m) | Node Permutations (n!) | Edge Permutations (m!) | Total Operations (n! * m!) | Feasibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2 | 1 | 2 | 1 | 2 | **Excellent** |
| 3 | 2 | 6 | 2 | 12 | **Excellent** |
| 4 | 3 | 24 | 6 | 144 | **Good** |
| 5 | 4 | 120 | 24 | 2,880 | **Acceptable** |
| 6 | 5 | 720 | 120 | 86,400 | **Slow** |
| 7 | 6 | 5,040 | 720 | 3,628,800 | **Very Slow** |
| 8 | 7 | 40,320 | 5,040 | 203,212,800 | **Infeasible** |
| 9 | 8 | 362,880 | 40,320 | ~1.46 x 10¹⁰ | **Infeasible** |

**Conclusion:**
*   **The "Safe Zone"**: The vast majority of your queries (1-4 nodes) will be processed instantly.
*   **The "Slow Zone"**: The 125 queries with 5 nodes and 30 queries with 6 nodes will start to feel sluggish. A comparison might take a few hundred milliseconds to a few seconds.
*   **The "Danger Zone"**: The handful of queries with 7+ nodes will likely time out or lock up a processing thread for an unacceptable amount of time.

You can use this approach, but you **must** implement a timeout or a node/edge count limit to prevent the "danger zone" queries from crippling your application.

---

###  Useful insights

#### On relationships

The fundamental flaw in the current logic is that it treats node mappings and edge mappings as **independent problems**. They are not. **An edge mapping is entirely constrained by its corresponding node mapping.**

If you map source node `a` to target node `x` and `b` to `y`, then the source edge `(a)-[r]->(b)` can *only* map to a target edge `(x)-[s]->(y)`. You don't need to try mapping `r` to any other edge in the target graph.

This insight allows us to eliminate the `* N_edges!` complexity entirely.

### Part 3: Further Heuristic Optimizations (If `O(N_nodes!)` is still too slow)

You can add heuristics to prune the search space even further.

1.  **Filter by Node Properties:** Modify `_generate_injective_mappings` to be smarter. A source node `(n:Person)` should **never** be mapped to a target node `(m:Movie)`. You can pre-filter the `target_variables` list for each `source_variable` based on matching labels.
2.  **Filter by Node Degree:** A source node with 3 relationships connected to it cannot be mapped to a target node with only 1 relationship. You can calculate the degree of each node and use it as another strict filter.
3.  **Greedy Search:** Instead of an exhaustive search, use a greedy algorithm.
    *   Start by mapping the most "unique" or constrained node pair (e.g., nodes with rare labels or high degrees).
    *   Expand the mapping outwards from there, always choosing the next best local match.
    *   This is not guaranteed to be optimal but is much faster. It's an excellent fallback for when `len(nodes) > 7`.