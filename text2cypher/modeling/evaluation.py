"""
Cypher Query Evaluation Module.

This module provides tools for extracting graph patterns from Cypher queries
and computing semantic similarity metrics between them. It uses tree-sitter
for parsing and supports variable-agnostic comparison through optimal mapping.

WARNING: This module is currently based on the openCypher 9 (roughly equivalent to 
Neo4j 3.5) grammar for tree-sitter, which may not cover all features of modern Neo4j's
Cypher dialect.

Typical usage example:
    >>> score, mapping = compute_graph_pattern_similarity(
    ...     generated_query="MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a",
    ...     ground_truth_query="MATCH (x:Person)-[:KNOWS]->(y:Person) RETURN x"
    ... )
    >>> print(f"Similarity: {score:.4f}")
"""

# TODO: Handle also all other Cypher clauses
# in queries that are different from MATCH clauses
# e.g., WHERE, RETURN, etc.

# TODO: Add Data augmentation techniques for 
# graph queries e.g. permutations of 
# clauses and graph patterns.

# TODO: Add the fix for shortestPath and 
# allShortestPaths patterns.

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional

import tree_sitter_cypher
from tree_sitter import Language, Node, Parser, Tree, TreeCursor


_ANONYMOUS_NODE_PREFIX: str = "__anon_node_"
_ANONYMOUS_EDGE_PREFIX: str = "__anon_edge_"

_LITERAL_NODE_TYPES: frozenset[str] = frozenset({
    "string_literal",
    "integer_literal",
    "decimal_integer",
    "double_literal",
    "boolean_literal",
    "hex_integer",
    "octal_integer",
})

# Tree-sitter node type constants for better maintainability
_NODE_TYPE_MATCH: str = "match"
_NODE_TYPE_PATTERN: str = "pattern"
_NODE_TYPE_PATTERN_PART: str = "pattern_part"
_NODE_TYPE_ANONYMOUS_PATTERN_PART: str = "anonymous_pattern_part"
_NODE_TYPE_PATTERN_ELEMENT: str = "pattern_element"
_NODE_TYPE_PATTERN_ELEMENT_CHAIN: str = "pattern_element_chain"
_NODE_TYPE_NODE_PATTERN: str = "node_pattern"
_NODE_TYPE_RELATIONSHIP_PATTERN: str = "relationship_pattern"
_NODE_TYPE_RELATIONSHIP_DETAIL: str = "relationship_detail"
_NODE_TYPE_RELATIONSHIP_TYPES: str = "relationship_types"
_NODE_TYPE_VARIABLE: str = "variable"
_NODE_TYPE_NODE_LABELS: str = "node_labels"
_NODE_TYPE_NODE_LABEL: str = "node_label"
_NODE_TYPE_LABEL_NAME: str = "label_name"
_NODE_TYPE_PROPERTIES: str = "properties"
_NODE_TYPE_MAP_LITERAL: str = "map_literal"
_NODE_TYPE_PROPERTY_KEY_NAME: str = "property_key_name"
_NODE_TYPE_EXPRESSION: str = "expression"
_NODE_TYPE_SYMBOLIC_NAME: str = "symbolic_name"
_NODE_TYPE_RESERVED_WORD: str = "reserved_word"
_NODE_TYPE_REL_TYPE_NAME: str = "rel_type_name"

_CYPHER_LANGUAGE: Language = Language(tree_sitter_cypher.language())
_default_parser: Parser = Parser(_CYPHER_LANGUAGE)

class GraphPattern:
    """Represents the extracted graph structure from a Cypher query.

    This class stores nodes and edges extracted from MATCH clauses in Cypher
    queries, providing methods for comparison, mapping, and similarity computation.

    Nested Classes:
        Node: Represents a graph node with labels and properties.
        Edge: Represents a relationship/edge between nodes.
        Mapping: Represents variable mappings between two patterns.

    Attributes:
        nodes: Dictionary mapping variable names to Node instances.
        edges: Dictionary mapping variable names to Edge instances.

    Example:
        >>> pattern = GraphPattern()
        >>> var = pattern.add_node(labels={'Person'}, properties={'name': 'Alice'})
        >>> print(pattern.nodes[var].labels)
        {'Person'}
    """

    @dataclass
    class Node:
        """Represents a node in the graph pattern with labels and properties.

        Attributes:
            labels: Set of node labels (e.g., {'Person', 'Employee'}).
            properties: Dictionary of property key-value pairs.
        """

        labels: set[str] = field(default_factory=set)
        properties: dict[str, Any] = field(default_factory=dict)

    @dataclass
    class Edge:
        """Represents a relationship/edge in the graph pattern.

        Attributes:
            from_node: Variable name of the source node.
            to_node: Variable name of the target node.
            labels: Set of relationship types/labels (e.g., {'KNOWS', 'FRIENDS'}).
                    In Cypher, multiple types can be specified with | operator.
            properties: Dictionary of property key-value pairs.
            variable: Optional variable name for the relationship itself.
        """

        from_node: str
        to_node: str
        labels: set[str] = field(default_factory=set)
        properties: dict[str, Any] = field(default_factory=dict)
        variable: Optional[str] = None

        def __eq__(self, other: Any) -> bool:
            """Check equality between two Edge instances.

            Edges are considered equal if they connect the same nodes
            regardless of their variable names, properties or labels.

            Args:
                other: The other object to compare against.
            Returns:
                True if equal, False otherwise.
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

        Attributes:
            nodes_map: Mapping from source node variables to target.
            edges_map: Mapping from source edge variables to target.
        """

        nodes_map: dict[str, str] = field(default_factory=dict)
        edges_map: dict[str, str] = field(default_factory=dict)

    def __init__(self) -> None:
        """Initialize an empty GraphPattern."""
        self.nodes: dict[str, GraphPattern.Node] = {}
        self.edges: dict[str, GraphPattern.Edge] = {}
        self._anonymous_counter: int = 0

    def add_node(
        self,
        labels: set[str],
        properties: dict[str, Any],
        variable: Optional[str] = None,
    ) -> str:
        """Add a node to the graph pattern or merge with existing node.

        If a node with the given variable already exists, the labels and
        properties are merged. If no variable is provided, an anonymous
        variable is generated.

        Args:
            labels: Set of labels to assign to the node.
            properties: Dictionary of properties for the node.
            variable: Optional variable name. If None, generates anonymous variable.

        Returns:
            The variable name assigned to the node (either provided or generated).
        """
        if variable is None:
            variable = f"{_ANONYMOUS_NODE_PREFIX}{self._anonymous_counter}"
            self._anonymous_counter += 1

        if variable not in self.nodes:
            self.nodes[variable] = GraphPattern.Node(labels=set(), properties={})

        self.nodes[variable].labels.update(labels)
        self.nodes[variable].properties.update(properties)
        return variable

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        labels: set[str],
        properties: dict[str, Any],
        edge_variable: Optional[str] = None,
    ) -> str:
        """Add an edge to the graph pattern or merge with existing edge.

        If an edge with the given variable already exists, labels and properties
        are merged. If no variable is provided, an anonymous variable is generated.

        Args:
            from_node: Variable name of the source node.
            to_node: Variable name of the target node.
            labels: Set of relationship types (e.g., {'KNOWS', 'FRIENDS'}).
            properties: Dictionary of properties for the edge.
            edge_variable: Optional variable name. If None, generates anonymous variable.

        Returns:
            The variable name assigned to the edge (either provided or generated).
        """
        if edge_variable is None:
            edge_variable = f"{_ANONYMOUS_EDGE_PREFIX}{self._anonymous_counter}"
            self._anonymous_counter += 1

        if edge_variable not in self.edges:
            self.edges[edge_variable] = GraphPattern.Edge(
                from_node=from_node,
                to_node=to_node,
                labels=set(),
                properties={},
                variable=edge_variable,
            )

        self.edges[edge_variable].labels.update(labels)
        self.edges[edge_variable].properties.update(properties)
        return edge_variable

    def apply_mapping(self, mapping: GraphPattern.Mapping) -> GraphPattern:
        """Create a new GraphPattern with variables renamed according to the mapping.

        Variables not present in the mapping are kept unchanged. This is useful
        for aligning two patterns before comparison.

        Args:
            mapping: A GraphPattern.Mapping containing node and edge variable mappings.

        Returns:
            A new GraphPattern instance with remapped variable names.
        """
        new_pattern = GraphPattern()
        new_pattern._anonymous_counter = self._anonymous_counter

        for original_var, node_data in self.nodes.items():
            new_variable = mapping.nodes_map.get(
                original_var, original_var
            )
            new_pattern.nodes[new_variable] = GraphPattern.Node(
                labels=set(node_data.labels),
                properties=dict(node_data.properties),
            )

        for original_var, edge_data in self.edges.items():
            new_variable = mapping.edges_map.get(
                original_var, original_var
            )
            new_from = mapping.nodes_map.get(
                edge_data.from_node, edge_data.from_node
            )
            new_to = mapping.nodes_map.get(
                edge_data.to_node, edge_data.to_node
            )
            new_pattern.edges[new_variable] = GraphPattern.Edge(
                from_node=new_from,
                to_node=new_to,
                labels=set(edge_data.labels),
                properties=dict(edge_data.properties),
                variable=new_variable,
            )

        return new_pattern

    def _count_node_intersections(self, other: GraphPattern) -> tuple[int, int]:
        """Compute intersection counts for nodes and their properties.

        A node is considered matching if it exists in both patterns with
        identical labels. Properties are counted separately only if the
        node itself matches.

        Args:
            other: The GraphPattern to compare against.

        Returns:
            A tuple of (matching_node_count, matching_node_property_count).
        """
        matching_nodes: int = 0
        matching_node_properties: int = 0

        for variable, self_node in self.nodes.items():
            if variable in other.nodes:
                other_node = other.nodes[variable]

                matching_nodes_labels = len(
                    self_node.labels.intersection(other_node.labels)
                )

                if matching_nodes_labels > 0:
                    matching_nodes += matching_nodes_labels

                    for property_key, property_value in self_node.properties.items():
                        if other_node.properties.get(property_key) == property_value:
                            matching_node_properties += 1

        return matching_nodes, matching_node_properties

    def _count_edge_intersections(self, other: GraphPattern) -> tuple[int, int]:
        """Compute intersection counts for edges and their properties.

        An edge is considered matching if it exists in both patterns with
        identical start/end variables and relationship type. Properties are
        counted separately only if the edge itself matches.

        Args:
            other: The GraphPattern to compare against.

        Returns:
            A tuple of (matching_edge_count, matching_edge_property_count).
        """
        matching_edges: int = 0
        matching_edge_properties: int = 0

        for variable, self_edge in self.edges.items():
            if variable in other.edges:
                other_edge = other.edges[variable]

                if self_edge == other_edge:
                    matching_edges_labels = len(
                        self_edge.labels.intersection(other_edge.labels)
                    )
                    if matching_edges_labels > 0:
                        matching_edges += matching_edges_labels

                        for property_key, property_value in self_edge.properties.items():
                            if other_edge.properties.get(property_key) == property_value:
                                matching_edge_properties += 1

        return matching_edges, matching_edge_properties

    def _count_total_elements(self) -> tuple[int, int, int, int]:
        """Count total nodes, edges, and their properties in this pattern.

        Returns:
            A tuple of (node_count, edge_count, node_property_count, edge_property_count).
        """
        node_count = sum(
            len(node.labels) for node in self.nodes.values()
        )
        edge_count = sum(
            len(edge.labels) for edge in self.edges.values()
        )
        node_property_count = sum(
            len(node.properties) for node in self.nodes.values()
        )
        edge_property_count = sum(
            len(edge.properties) for edge in self.edges.values()
        )
        return node_count, edge_count, node_property_count, edge_property_count

    def jaccard(self, other: GraphPattern) -> float:
        """Calculate Jaccard similarity between this GraphPattern and another.

        The similarity is computed as:
            J = |Intersection| / |Union|

        Where intersection and union consider nodes, edges, and all their properties.
        Uses the inclusion-exclusion principle: |Union| = |A| + |B| - |Intersection|.

        Note:
            Variables must be aligned before calling this method. Use
            `find_optimal_mapping()` to find the best alignment first.

        Args:
            other: The GraphPattern to compare against.

        Returns:
            Jaccard similarity score in range [0.0, 1.0].
        """
        node_intersection, node_prop_intersection = self._count_node_intersections(
            other
        )
        edge_intersection, edge_prop_intersection = self._count_edge_intersections(
            other
        )

        self_counts = self._count_total_elements()
        other_counts = other._count_total_elements()

        total_intersection = (
            node_intersection
            + edge_intersection
            + node_prop_intersection
            + edge_prop_intersection
        )

        self_total = sum(self_counts)
        other_total = sum(other_counts)
        total_union = self_total + other_total - total_intersection

        if total_union == 0:
            return 0.0

        return total_intersection / total_union

    @staticmethod
    def _generate_injective_mappings(
        source_variables: list[str],
        target_variables: list[str],
    ) -> Iterator[dict[str, str]]:
        """Generate all possible injective mappings from source to target variables.

        Handles asymmetric cases where the number of source and target variables
        differ by mapping the smaller set to subsets of the larger set.

        Args:
            source_variables: List of variable names from the source pattern.
            target_variables: List of variable names from the target pattern.

        Yields:
            Dictionaries mapping source_variable -> target_variable.
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

    def find_optimal_mapping(
        self,
        other: GraphPattern,
        similarity_metric: Callable[[GraphPattern, GraphPattern], float],
        minimize: bool = False,
    ) -> tuple[float, GraphPattern.Mapping]:
        """Find the optimal variable mapping between this pattern and another.

        Exhaustively searches all possible combinations of node and edge variable
        mappings to find the one that optimizes the given metric.

        Args:
            other: The target GraphPattern to map to.
            similarity_metric: A callable that takes two GraphPatterns and returns
                a float score. Signature: metric(mapped_self, other) -> float.
            minimize: If True, find mapping that minimizes the metric.
                If False (default), find mapping that maximizes it.

        Returns:
            A tuple of (best_score, best_mapping) where best_mapping is a
            GraphPattern.Mapping containing the optimal node and edge variable mappings.
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
            return similarity_metric(self, other), GraphPattern.Mapping()

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
                score = similarity_metric(aligned_pattern, other)

                if is_better(score, best_score):
                    best_score = score
                    best_mapping = candidate_mapping

        return best_score, best_mapping

    def __repr__(self) -> str:
        """Return a string representation of the GraphPattern."""
        return f"GraphPattern(nodes={self.nodes!r}, edges={self.edges!r})"

class CypherPatternExtractor:
    """Parses Cypher queries and extracts GraphPattern representations.

    Uses tree-sitter for parsing with efficient non-recursive tree traversal
    via TreeCursor. The extractor follows the Cypher grammar structure to
    identify and process MATCH clauses.

    Attributes:
        parser: The tree-sitter Parser instance configured for Cypher.

    Example:
        >>> extractor = CypherPatternExtractor()
        >>> pattern = extractor.extract_pattern("MATCH (n:Person) RETURN n")
        >>> print(pattern.nodes)
    """

    def __init__(self, parser: Optional[Parser] = None) -> None:
        """Initialize the CypherPatternExtractor.

        Args:
            parser: Optional tree-sitter Parser. If None, uses the default parser.
        """
        self._parser: Parser = parser if parser is not None else _default_parser

    @staticmethod
    def _get_node_text(tree_node: Node) -> str:
        """Extract the source text from a tree-sitter node.

        Args:
            tree_node: The tree-sitter Node to extract text from.

        Returns:
            The decoded UTF-8 text content of the node.
        """
        return tree_node.text.decode("utf-8")

    def extract_pattern(self, cypher_query: str) -> GraphPattern:
        """Extract a GraphPattern from a Cypher query string.

        Parses the query and traverses the syntax tree to find all MATCH
        clauses, extracting nodes, relationships, and their properties.

        Args:
            cypher_query: A valid Cypher query string.

        Returns:
            A GraphPattern containing all nodes and edges from MATCH clauses.
        """
        parse_tree: Tree = self._parser.parse(bytes(cypher_query, "utf-8"))
        extracted_pattern = GraphPattern()

        tree_cursor: TreeCursor = parse_tree.walk()
        self._traverse_and_extract_matches(tree_cursor, extracted_pattern)

        return extracted_pattern

    # TODO: Handle also OPTIONAL MATCH clauses even if
    # with the current state of the code they are partially handled
    # in the sense that they are added as normal MATCH clauses.
    def _traverse_and_extract_matches(
        self,
        cursor: TreeCursor,
        pattern_container: GraphPattern,
    ) -> None:
        """Traverse the syntax tree to find and process all MATCH clauses.

        Uses iterative depth-first traversal with the TreeCursor for efficiency.

        Args:
            cursor: TreeCursor positioned at the root of the tree.
            pattern_container: GraphPattern to populate with extracted data.
        """
        should_descend: bool = True
        traversal_active: bool = True

        while traversal_active:
            if should_descend:
                if cursor.node.type == _NODE_TYPE_MATCH:
                    self._process_match_clause(cursor.node, pattern_container)
                    should_descend = False
                elif not cursor.goto_first_child():
                    should_descend = False
            else:
                if cursor.goto_next_sibling():
                    should_descend = True
                elif cursor.goto_parent():
                    should_descend = False
                else:
                    traversal_active = False

    def _process_match_clause(
        self,
        match_node: Node,
        pattern_container: GraphPattern,
    ) -> None:
        """Process a MATCH clause node to extract pattern information.

        Tree-Sitter JavaScript Grammar:
        ```
            match: ($) => seq(
                optional(word('optional')), 
                word('match'), 
                $.pattern, 
                optional($.where)
            )
        ```

        Args:
            match_node: The tree-sitter Node representing a MATCH clause.
            pattern_container: GraphPattern to populate with extracted data.
        """
        for child in match_node.children:
            if child.type == _NODE_TYPE_PATTERN:
                self._process_pattern(child, pattern_container)
                return

    def _process_pattern(
        self,
        pattern_node: Node,
        pattern_container: GraphPattern,
    ) -> None:
        """Process a pattern node containing one or more pattern parts.

        Tree-Sitter JavaScript Grammar:
        ```
            pattern: ($) => seq(
                $.pattern_part, 
                repeat(seq(',', $.pattern_part))
            )
        ```

        Args:
            pattern_node: The tree-sitter Node representing the pattern.
            pattern_container: GraphPattern to populate with extracted data.
        """
        for child in pattern_node.children:
            if child.type == _NODE_TYPE_PATTERN_PART:
                self._process_pattern_part(child, pattern_container)

    def _process_pattern_part(
        self,
        part_node: Node,
        pattern_container: GraphPattern,
    ) -> None:
        """Process a pattern_part node.

        Tree-Sitter JavaScript Grammar:
        ```
            pattern_part: ($) => choice(
                seq($.variable, '=', $.anonymous_pattern_part), 
                $.anonymous_pattern_part
            )
        ```

        Args:
            part_node: The tree-sitter Node representing the pattern part.
            pattern_container: GraphPattern to populate with extracted data.
        """
        for child in part_node.children:
            if child.type == _NODE_TYPE_ANONYMOUS_PATTERN_PART:
                self._process_anonymous_pattern_part(child, pattern_container)
                return

    def _process_anonymous_pattern_part(
        self,
        anonymous_node: Node,
        pattern_container: GraphPattern,
    ) -> None:
        """Process an anonymous_pattern_part node.

        Tree-Sitter JavaScript Grammar:
        ```
            anonymous_pattern_part: ($) => $.pattern_element,
        ```

        Args:
            anonymous_node: The tree-sitter Node for the anonymous pattern part.
            pattern_container: GraphPattern to populate with extracted data.
        """
        if anonymous_node.child_count > 0:
            first_child = anonymous_node.children[0]
            if first_child.type == _NODE_TYPE_PATTERN_ELEMENT:
                self._process_pattern_element(first_child, pattern_container)

    def _process_pattern_element(
        self,
        element_node: Node,
        pattern_container: GraphPattern,
    ) -> None:
        """Process a pattern_element node containing nodes and relationships.

        Tree-Sitter JavaScript Grammar:
        ```
            pattern_element: ($) => choice(
                seq($.node_pattern, repeat($.pattern_element_chain)), 
                seq('(', $.pattern_element, ')')
            )
        ```

        Args:
            element_node: The tree-sitter Node representing the pattern element.
            pattern_container: GraphPattern to populate with extracted data.
        """
        current_node_variable: Optional[str] = None

        for child in element_node.children:
            child_type = child.type

            if child_type == _NODE_TYPE_PATTERN_ELEMENT:
                # Handle parenthesized pattern recursively
                self._process_pattern_element(child, pattern_container)
                return

            elif child_type == _NODE_TYPE_NODE_PATTERN:
                current_node_variable = self._extract_node_from_pattern(
                    child, pattern_container
                )

            elif child_type == _NODE_TYPE_PATTERN_ELEMENT_CHAIN:
                relationship_node: Optional[Node] = None
                next_node_pattern: Optional[Node] = None

                for chain_child in child.children:
                    if chain_child.type == _NODE_TYPE_RELATIONSHIP_PATTERN:
                        relationship_node = chain_child
                    elif chain_child.type == _NODE_TYPE_NODE_PATTERN:
                        next_node_pattern = chain_child

                if relationship_node is not None and next_node_pattern is not None:
                    next_node_variable = self._extract_node_from_pattern(
                        next_node_pattern, pattern_container
                    )
                    self._extract_relationship(
                        relationship_node,
                        current_node_variable,
                        next_node_variable,
                        pattern_container,
                    )
                    current_node_variable = next_node_variable

    def _extract_node_from_pattern(
        self,
        node_pattern: Node,
        pattern_container: GraphPattern,
    ) -> str:
        """Extract node information from a node_pattern and add to container.

        Tree-Sitter JavaScript Grammar:
        ```
            node_pattern: ($) => prec(1,
                choice(
                    $.variable_in_parens,
                    seq('(', 
                        optional($.variable), 
                        optional($.node_labels), 
                        optional($.properties), 
                    ')')
                )
            )
        ```

        Args:
            node_pattern: The tree-sitter Node representing a node pattern.
            pattern_container: GraphPattern to add the extracted node to.

        Returns:
            The variable name assigned to the extracted node.
        """
        variable: Optional[str] = None
        labels: set[str] = set()
        properties: dict[str, Any] = {}

        for child in node_pattern.children:
            child_type = child.type

            if child_type == _NODE_TYPE_VARIABLE:
                variable = self._extract_variable_name(child)

            elif child_type == _NODE_TYPE_NODE_LABELS:
                for label_child in child.children:
                    if label_child.type == _NODE_TYPE_NODE_LABEL:
                        label_name = self._extract_label_from_node_label(label_child)
                        if label_name:
                            labels.add(label_name)

            elif child_type == _NODE_TYPE_PROPERTIES:
                properties = self._extract_properties_from_node(child)

        return pattern_container.add_node(labels, properties, variable)

    def _extract_variable_name(self, variable_node: Node) -> Optional[str]:
        """Extract the variable name from a variable node.

        Tree-Sitter JavaScript Grammar:
        ```
            variable: ($) => $.symbolic_name
        ```

        Args:
            variable_node: The tree-sitter Node representing a variable.

        Returns:
            The extracted variable name string, or None if extraction fails.
        """
        if variable_node.child_count > 0:
            symbolic_name_node = variable_node.children[0]
            if symbolic_name_node.child_count > 0:
                return self._get_node_text(symbolic_name_node.children[0])
            return self._get_node_text(symbolic_name_node)
        return self._get_node_text(variable_node)

    def _extract_label_from_node_label(self, node_label: Node) -> str:
        """Extract the label string from a node_label node.

        Tree-Sitter JavaScript Grammar:
        ```
            node_label: ($) => seq(':', $.label_name)
        ```

        Args:
            node_label: The tree-sitter Node representing a node label.

        Returns:
            The extracted label string, or empty string if not found.
        """
        for child in node_label.children:
            if child.type == _NODE_TYPE_LABEL_NAME:
                return self._extract_name_from_label_name(child)
        return ""

    def _extract_name_from_label_name(self, label_name_node: Node) -> str:
        """Extract the name from a label_name node.

        Tree-Sitter JavaScript Grammar:
        ```
            label_name: ($) => $.schema_name
        ```

        Args:
            label_name_node: The tree-sitter Node representing a label name.

        Returns:
            The extracted label name string.
        """
        if label_name_node.child_count > 0:
            return self._extract_name_from_schema_name(label_name_node.children[0])
        return self._get_node_text(label_name_node)

    def _extract_name_from_schema_name(self, schema_name_node: Node) -> str:
        """Extract the name from a schema_name node.

        Tree-Sitter JavaScript Grammar:
        ```
            schema_name: ($) => choice($.symbolic_name, $.reserved_word),
            symbolic_name: ($) => prec.left(
                choice(
                    $.unescaped_symbolic_name, 
                    $.escaped_symbolic_name, 
                    word('count'), 
                    word('filter'), 
                    word('extract'), 
                    word('any'), 
                    word('none'), 
                    word('single')
                )
            )
        ```

        Args:
            schema_name_node: The tree-sitter Node representing a schema name.

        Returns:
            The extracted name string.
        """
        if schema_name_node.child_count > 0:
            child = schema_name_node.children[0]
            if child.type == _NODE_TYPE_SYMBOLIC_NAME:
                if child.child_count > 0:
                    return self._get_node_text(child.children[0])
            elif child.type == _NODE_TYPE_RESERVED_WORD:
                return self._get_node_text(child)
        return self._get_node_text(schema_name_node)

    def _extract_properties_from_node(
        self, properties_node: Node
    ) -> dict[str, Any]:
        """Extract properties from a properties node.

        Tree-Sitter JavaScript Grammar:
        ```
            properties: ($) => prec(1, choice($.map_literal, $.parameter))
        ```

        Args:
            properties_node: The tree-sitter Node representing properties.

        Returns:
            Dictionary of property key-value pairs.
        """
        for child in properties_node.children:
            if child.type == _NODE_TYPE_MAP_LITERAL:
                return self._parse_map_literal_node(child)
        return {}

    def _parse_map_literal_node(self, map_node: Node) -> dict[str, Any]:
        """Parse a map_literal node into a dictionary.

        Tree-Sitter JavaScript Grammar:
        ```
            map_literal: ($) => seq('{', 
                optional(
                    seq(
                        $.property_key_name, ':', 
                        $.expression, 
                        repeat(seq(',', $.property_key_name, ':', $.expression))
                    )
                ), 
            '}')
        ```

        Args:
            map_node: The tree-sitter Node representing a map literal.

        Returns:
            Dictionary of property key-value pairs.
        """
        properties: dict[str, Any] = {}
        current_key: Optional[str] = None

        for child in map_node.children:
            child_type = child.type

            if child_type == _NODE_TYPE_PROPERTY_KEY_NAME:
                current_key = self._extract_property_key_name(child)

            elif child_type == _NODE_TYPE_EXPRESSION and current_key is not None:
                value = self._extract_literal_value_from_expression(child)
                if value is not None:
                    properties[current_key] = value
                current_key = None

        return properties

    def _extract_property_key_name(self, key_node: Node) -> str:
        """Extract the property key name from a property_key_name node.

        Tree-Sitter JavaScript Grammar:
        ```
        property_key_name: ($) => $.schema_name,
        ```

        Args:
            key_node: The tree-sitter Node representing a property key name.

        Returns:
            The extracted property key string.
        """
        if key_node.child_count > 0:
            return self._extract_name_from_schema_name(key_node.children[0])
        return self._get_node_text(key_node)

    def _extract_literal_value_from_expression(
        self, expression_node: Node
    ) -> Optional[str]:
        """Extract a literal value from an expression node.

        Traverses the expression tree to find literal value nodes such as
        string_literal, integer_literal, etc.

        Args:
            expression_node: The tree-sitter Node representing an expression.

        Returns:
            The extracted literal value as string, or None if not found.
        """
        cursor: TreeCursor = expression_node.walk()
        should_descend: bool = True
        traversal_active: bool = True
        literal = None

        while traversal_active:
            if cursor.node.type in _LITERAL_NODE_TYPES:
                literal = self._get_node_text(cursor.node)
                traversal_active = False

            if should_descend:
                if not cursor.goto_first_child():
                    should_descend = False
            else:
                if cursor.goto_next_sibling():
                    should_descend = True
                elif cursor.goto_parent():
                    should_descend = False
                    if cursor.node == expression_node:
                        traversal_active = False
                else:
                    traversal_active = False

        return literal

    def _extract_relationship(
        self,
        relationship_pattern: Node,
        start_variable: Optional[str],
        end_variable: Optional[str],
        pattern_container: GraphPattern,
    ) -> None:
        """Extract relationship information from a relationship_pattern node.

        Tree-Sitter Javascript Grammar:
        ```
            relationship_pattern: ($) => seq(
                optional($.left_arrow_head), 
                $.dash, 
                optional($.relationship_detail), 
                $.dash, 
                optional($.right_arrow_head)
            ),
            relationship_detail: ($) => seq('[',
                optional($.variable), 
                optional($.relationship_types), 
                optional($.range_literal), 
                optional($.properties),
            ']'),
        ```

        Args:
            relationship_pattern: The tree-sitter Node representing a relationship pattern.
            start_variable: Variable name of the source node.
            end_variable: Variable name of the target node.
            pattern_container: GraphPattern to add the extracted relationship to.
        """
        edge_variable: Optional[str] = None
        labels: set[str] = set()
        properties: dict[str, Any] = {}

        for child in relationship_pattern.children:
            if child.type == _NODE_TYPE_RELATIONSHIP_DETAIL:
                for detail_child in child.children:
                    detail_type = detail_child.type

                    if detail_type == _NODE_TYPE_VARIABLE:
                        edge_variable = self._extract_variable_name(detail_child)

                    elif detail_type == _NODE_TYPE_RELATIONSHIP_TYPES:
                        # Extract all relationship types (handles [:TYPE1|TYPE2|TYPE3])
                        for type_child in detail_child.children:
                            if type_child.type == _NODE_TYPE_REL_TYPE_NAME:
                                label = self._extract_relationship_type_name(
                                    type_child
                                )
                                labels.add(label)

                    elif detail_type == _NODE_TYPE_PROPERTIES:
                        properties = self._extract_properties_from_node(detail_child)

                break  # Only one relationship_detail expected

        pattern_container.add_edge(
            start_variable, end_variable, labels, properties, edge_variable
        )

    def _extract_relationship_type_name(self, rel_type_node: Node) -> str:
        """Extract the relationship type name from a rel_type_name node.

        Grammar:
            rel_type_name: schema_name

        Args:
            rel_type_node: The tree-sitter Node representing a relationship type name.

        Returns:
            The extracted relationship type string.
        """
        if rel_type_node.child_count > 0:
            return self._extract_name_from_schema_name(rel_type_node.children[0])
        return self._get_node_text(rel_type_node)


def compute_graph_pattern_similarity(
    generated_query: str,
    ground_truth_query: str,
    verbose: bool = False,
) -> tuple[float, GraphPattern.Mapping]:
    """Compute the semantic similarity between two Cypher queries.

    Extracts graph patterns from both queries and finds the optimal variable
    mapping that maximizes Jaccard similarity.

    Args:
        generated_query: The generated/predicted Cypher query to evaluate.
        ground_truth_query: The reference/expected Cypher query.
        verbose: If True, print detailed comparison information.

    Returns:
        A tuple of (similarity_score, optimal_mapping) where:
            - similarity_score: Jaccard similarity in range [0.0, 1.0]
            - optimal_mapping: GraphPattern.Mapping for best alignment
    """
    extractor = CypherPatternExtractor()

    generated_pattern: GraphPattern = extractor.extract_pattern(generated_query)
    ground_truth_pattern: GraphPattern = extractor.extract_pattern(ground_truth_query)

    if verbose:
        print(f"Ground Truth Pattern: {ground_truth_pattern}")
        print(f"Generated Pattern: {generated_pattern}")

    similarity_score, optimal_mapping = generated_pattern.find_optimal_mapping(
        other=ground_truth_pattern,
        similarity_metric=GraphPattern.jaccard,
        minimize=False,
    )

    if verbose:
        print(f"Similarity Score: {similarity_score:.4f}")
        print(f"Optimal Mapping: {optimal_mapping}")

    return similarity_score, optimal_mapping


# =============================================================================
# Test Script
# =============================================================================

if __name__ == "__main__":

    # Test Case 1: Semantically equivalent queries with different variable names
    ground_truth_query_1 = (
        "MATCH (p:Person)-[:ACTED_IN {role: 'Neo'}]->(m:Movie) RETURN p.name"
    )
    generated_query_1 = (
        "MATCH (actor:Person)-[:ACTED_IN {role: 'Neo'}]->(film:Movie) RETURN actor.name"
    )

    print("=" * 60)
    print("Test 1: Semantically Equivalent Queries")
    print("=" * 60)
    score_1, mapping_1 = compute_graph_pattern_similarity(
        generated_query_1, ground_truth_query_1, verbose=True
    )
    print()

    # Test Case 2: Missing property in generated query
    ground_truth_query_2 = (
        "MATCH (p:Person {name: 'Tom'})-[:KNOWS]->(f:Person) RETURN f"
    )
    generated_query_2 = "MATCH (p:Person)-[:KNOWS]->(f:Person) RETURN f"

    print("=" * 60)
    print("Test 2: Missing Property")
    print("=" * 60)
    score_2, mapping_2 = compute_graph_pattern_similarity(
        generated_query_2, ground_truth_query_2, verbose=True
    )
    print(
        "Explanation: Ground truth has extra property 'name', "
        "expected similarity ~ 0.75"
    )
    print()

    # Test Case 3: Completely wrong labels
    ground_truth_query_3 = "MATCH (a:Person) RETURN a"
    generated_query_3 = "MATCH (m:Movie) RETURN m"

    print("=" * 60)
    print("Test 3: Wrong Labels")
    print("=" * 60)
    score_3, mapping_3 = compute_graph_pattern_similarity(
        generated_query_3, ground_truth_query_3, verbose=True
    )
    print()

    # Test Case 4: Complex pattern with anonymous nodes
    ground_truth_query_4 = (
        "MATCH (u:User)-[:PURCHASED]->(:Product {id: 123})<-[:CREATED]-(:Creator)"
    )
    generated_query_4 = (
        "MATCH (x:User)-[f:PURCHASED]->(y:Product {id: 123})<-[:CREATED]-(z:Creator)"
    )

    print("=" * 60)
    print("Test 4: Complex Pattern with Anonymous vs Named Variables")
    print("=" * 60)
    score_4, mapping_4 = compute_graph_pattern_similarity(
        generated_query_4, ground_truth_query_4, verbose=True
    )
    print()

    # Test Case 5: Multiple relationship labels (using | operator)
    ground_truth_query_5 = (
        "MATCH (p:Person)-[:KNOWS|FRIENDS|COLLEAGUES]->(q:Person) RETURN p, q"
    )
    generated_query_5 = (
        "MATCH (a:Person)-[:KNOWS|FRIENDS|COLLEAGUES]->(b:Person) RETURN a, b"
    )

    print("=" * 60)
    print("Test 5: Multiple Relationship Labels (Exact Match)")
    print("=" * 60)
    score_5, mapping_5 = compute_graph_pattern_similarity(
        generated_query_5, ground_truth_query_5, verbose=True
    )
    print("Explanation: Both queries have identical multi-label relationships, expected similarity = 1.0")
    print()

    # Test Case 6: Partial match in multiple relationship labels
    ground_truth_query_6 = (
        "MATCH (p:Person)-[:KNOWS|FRIENDS]->(q:Person) RETURN p, q"
    )
    generated_query_6 = (
        "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a, b"
    )

    print("=" * 60)
    print("Test 6: Multiple Relationship Labels (Partial Match)")
    print("=" * 60)
    score_6, mapping_6 = compute_graph_pattern_similarity(
        generated_query_6, ground_truth_query_6, verbose=True
    )
    print("Explanation: Ground truth has {KNOWS, FRIENDS}, generated has only {KNOWS}, edges won't match")
