"""Cypher Query Evaluation Module.

This module provides tools for extracting graph patterns from Cypher queries
and computing semantic similarity metrics between them. It uses tree-sitter
for parsing and supports variable-agnostic comparison through optimal mapping.

The module contains the following key components:
    - ExpressionNodeType: Enum for different types of expression nodes in Cypher AST
    - CypherExpression: Represents a Cypher expression as an Abstract Syntax Tree
    - GraphPattern: Represents the extracted graph structure from a Cypher query
    - SingleCypherQuery: Represents a single Cypher query with MATCH and RETURN
    - CypherQuery: Represents a potentially multi-part Cypher query with UNION
    - CypherExtractor: Parses Cypher queries and extracts GraphPattern representations

Warning
-------
This module is currently based on the openCypher 9 (roughly equivalent to 
Neo4j 3.5) grammar for tree-sitter, which may not cover all features of modern Neo4j's
Cypher dialect.

Examples
--------
>>> score, mapping = compute_graph_pattern_similarity(
...     generated_query="MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a",
...     ground_truth_query="MATCH (x:Person)-[:KNOWS]->(y:Person) RETURN x"
... )
>>> print(f"Similarity: {score:.4f}")
"""

# TODO: Add Data augmentation techniques for 
# graph queries e.g. permutations of 
# clauses and graph patterns.

# TODO: Add the fix for shortestPath and 
# allShortestPaths patterns.

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator, List, Optional

import tree_sitter_cypher
from tree_sitter import Language, Node, Parser, Tree, TreeCursor
from zss import simple_distance, Node as ZssNode


_ANONYMOUS_NODE_PREFIX: str = "__anon_node_"
_ANONYMOUS_EDGE_PREFIX: str = "__anon_edge_"

# Tree-sitter node type constants for better maintainability
_SINGLE_PART_QUERY_TYPE: str = "single_part_query"
_READING_CLAUSE_TYPE: str = "reading_clause"
_RETURN_TYPE: str = "return"
_MATCH_TYPE: str = "match"
_OPTIONAL_TYPE: str = "optional"
_WHERE_TYPE: str = "where"
_PATTERN_PART_TYPE: str = "pattern_part"
_ANONYMOUS_PATTERN_PART_TYPE: str = "anonymous_pattern_part"
_PATTERN_ELEMENT_CHAIN_TYPE: str = "pattern_element_chain"
_NODE_PATTERN_TYPE: str = "node_pattern"
_RELATIONSHIP_TYPES_TYPE: str = "relationship_types"
_VARIABLE_TYPE: str = "variable"
_NODE_LABELS_TYPE: str = "node_labels"
_PROPERTIES_TYPE: str = "properties"
_MAP_LITERAL_TYPE: str = "map_literal"
_PROPERTY_KEY_NAME_TYPE: str = "property_key_name"
_EXPRESSION_TYPE: str = "expression"
_REL_TYPE_NAME_TYPE: str = "rel_type_name"
_RANGE_LITERAL_TYPE: str = "range_literal"
_LEFT_ARROW_HEAD_TYPE: str = "left_arrow_head"
_RIGHT_ARROW_HEAD_TYPE: str = "right_arrow_head"

_CYPHER_LANGUAGE: Language = Language(tree_sitter_cypher.language())
_default_parser: Parser = Parser(_CYPHER_LANGUAGE)


class ExpressionNodeType(Enum):
    """Enum for different types of expression nodes in Cypher AST.
    
    This enumeration defines all possible node types that can appear in a
    Cypher expression abstract syntax tree. It includes logical operators,
    comparison operators, arithmetic operators, string predicates, list
    operations, property access, functions, case expressions, quantifiers,
    literals, comprehensions, and pattern-related expressions.
    
    Attributes
    ----------
    OR : str
        Logical OR operator
    XOR : str
        Logical XOR operator
    AND : str
        Logical AND operator
    NOT : str
        Logical NOT operator
    EQ : str
        Equality comparison operator (=)
    NEQ : str
        Not equal comparison operator (<>)
    LT : str
        Less than comparison operator (<)
    GT : str
        Greater than comparison operator (>)
    LTE : str
        Less than or equal comparison operator (<=)
    GTE : str
        Greater than or equal comparison operator (>=)
    ADD : str
        Addition arithmetic operator (+)
    SUB : str
        Subtraction arithmetic operator (-)
    MUL : str
        Multiplication arithmetic operator (*)
    DIV : str
        Division arithmetic operator (/)
    MOD : str
        Modulo arithmetic operator (%)
    POW : str
        Power arithmetic operator (^)
    UNARY_PLUS : str
        Unary plus operator
    UNARY_MINUS : str
        Unary minus operator
    STARTS_WITH : str
        String predicate for checking if a string starts with a substring
    ENDS_WITH : str
        String predicate for checking if a string ends with a substring
    CONTAINS : str
        String predicate for checking if a string contains a substring
    IN : str
        List membership predicate
    IS_NULL : str
        Null check predicate
    IS_NOT_NULL : str
        Not null check predicate
    LIST_INDEX : str
        List indexing operation
    LIST_SLICE : str
        List slicing operation
    PROPERTY : str
        Property access operation
    FUNCTION : str
        Function invocation
    CASE : str
        CASE expression
    CASE_WHEN : str
        WHEN clause in CASE expression
    CASE_ELSE : str
        ELSE clause in CASE expression
    ALL : str
        ALL quantifier
    ANY : str
        ANY quantifier
    NONE : str
        NONE quantifier
    SINGLE : str
        SINGLE quantifier
    LITERAL : str
        Literal value (number, string, boolean, null)
    VARIABLE : str
        Variable reference
    PARAMETER : str
        Query parameter reference ($param)
    LIST_LITERAL : str
        List literal expression
    MAP_LITERAL : str
        Map literal expression
    LIST_COMPREHENSION : str
        List comprehension expression
    PATTERN_COMPREHENSION : str
        Pattern comprehension expression
    PATTERN_PREDICATE : str
        Pattern predicate expression
    EXISTENTIAL_SUBQUERY : str
        Existential subquery expression
    WHERE : str
        WHERE clause
    RETURN : str
        RETURN clause
    """
    
    # Logical operators
    OR = "or"
    XOR = "xor"
    AND = "and"
    NOT = "not"
    
    # Comparison operators
    EQ = "="
    NEQ = "<>"
    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="
    
    # Arithmetic operators
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    MOD = "%"
    POW = "^"
    
    # Unary operators
    UNARY_PLUS = "unary_+"
    UNARY_MINUS = "unary_-"
    
    # String predicates
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    CONTAINS = "contains"
    
    # List/Null predicates
    IN = "in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    
    # List operators
    LIST_INDEX = "list_index"
    LIST_SLICE = "list_slice"
    
    # Property access
    PROPERTY = "property"
    
    # Function call
    FUNCTION = "function"
    
    # Case expression
    CASE = "case"
    CASE_WHEN = "when"
    CASE_ELSE = "else"
    
    # Quantifiers
    ALL = "all"
    ANY = "any"
    NONE = "none"
    SINGLE = "single"
    
    # Literals and variables
    LITERAL = "literal"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    LIST_LITERAL = "list_literal"
    MAP_LITERAL = "map_literal"
    
    # Comprehensions
    LIST_COMPREHENSION = "list_comprehension"
    PATTERN_COMPREHENSION = "pattern_comprehension"
    
    # Patterns
    PATTERN_PREDICATE = "pattern_predicate"
    EXISTENTIAL_SUBQUERY = "existential_subquery"

    WHERE = "where"
    RETURN = "return"


@dataclass
class CypherExpression:
    """Represents a Cypher expression as an Abstract Syntax Tree (AST).
    
    This class provides a structured representation of Cypher expressions
    that can be used for semantic comparison, canonicalization, and tree
    edit distance computation. It supports recursive tree structures for
    representing complex nested expressions.
    
    Parameters
    ----------
    node_type : ExpressionNodeType
        The type of this expression node (operator, literal, variable, etc.).
        Determines how the expression should be interpreted and compared.
    value : Optional[Any], default=None
        The value for literal nodes or operator symbol. For literals, this
        contains the actual value. For operators, this may contain the
        operator symbol. None for structural nodes.
    children : List[CypherExpression], default=empty list
        Child expression nodes for compound expressions. For binary operators,
        typically contains exactly two children. For unary operators, one child.
        For literals and variables, typically empty.
    metadata : dict[str, Any], default=empty dict
        Additional metadata about the expression. Examples include:
        - 'function_name' for function invocations
        - 'property_name' for property access
        - 'order' for ORDER BY direction ('ASC' or 'DESC')
        - 'as' for aliased expressions
        - 'distinct' for DISTINCT modifiers
    
    Attributes
    ----------
    node_type : ExpressionNodeType
        The type of this expression node.
    value : Optional[Any]
        The value associated with this node.
    children : List[CypherExpression]
        Child expression nodes.
    metadata : dict[str, Any]
        Additional node metadata.
    
    Methods
    -------
    to_canonical_form() -> CypherExpression
        Convert expression to canonical form for comparison.
    to_zss_tree() -> ZssNode
        Convert this expression to a zss tree for edit distance computation.
    tree_edit_distance(other: CypherExpression) -> int
        Compute tree edit distance to another expression.
    similarity_score(other: CypherExpression) -> float
        Compute normalized similarity score based on tree edit distance.
    get_tree_str(indent: int = 0) -> str
        Print the expression tree for debugging.
    
    Examples
    --------
    >>> # Represents: a.name = 'Alice' AND a.age > 30
    >>> expr = CypherExpression(
    ...     node_type=ExpressionNodeType.AND,
    ...     children=[
    ...         CypherExpression(node_type=ExpressionNodeType.EQ, children=[...]),
    ...         CypherExpression(node_type=ExpressionNodeType.GT, children=[...])
    ...     ]
    ... )
    >>> 
    >>> # Simple literal
    >>> lit = CypherExpression(node_type=ExpressionNodeType.LITERAL, value="Alice")
    >>> 
    >>> # Variable reference
    >>> var = CypherExpression(node_type=ExpressionNodeType.VARIABLE, value="a")
    """
    
    node_type: ExpressionNodeType
    value: Optional[Any] = None
    children: List[CypherExpression] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_canonical_form(self) -> CypherExpression:
        """Convert expression to canonical form for comparison.
        
        Canonicalization ensures that semantically equivalent expressions have
        the same structure, enabling accurate comparison. The transformation
        includes sorting operands of commutative operations, normalizing
        comparison operators, and recursively canonicalizing all children.
        
        Transformations applied:
            - Sorting operands of commutative operations (AND, OR, XOR, +, *, =)
            - Normalizing comparison operators (e.g., a > b becomes b < a)
            - Recursively canonicalizing all child expressions
            - Sorting function arguments where order doesn't matter
        
        Returns
        -------
        CypherExpression
            A new CypherExpression instance in canonical form. The original
            expression is not modified.
        
        Notes
        -----
        Commutative operators that are canonicalized:
            - Logical: AND, OR, XOR
            - Arithmetic: +, *
            - Comparison: = (equality)
        
        Comparison operators are normalized to prefer smaller expressions on the left:
            - GT ↔ LT (greater than ↔ less than)
            - GTE ↔ LTE (greater than or equal ↔ less than or equal)
        
        Examples
        --------
        >>> # a + b becomes b + a if b sorts before a
        >>> expr1 = CypherExpression(node_type=ExpressionNodeType.ADD, children=[...])
        >>> canonical = expr1.to_canonical_form()
        >>> 
        >>> # a > b becomes b < a
        >>> expr2 = CypherExpression(node_type=ExpressionNodeType.GT, children=[...])
        >>> canonical2 = expr2.to_canonical_form()
        """
        # Recursively canonicalize children first
        canonical_children = [child.to_canonical_form() for child in self.children]

        
        # Define commutative operators
        commutative_ops = {
            ExpressionNodeType.AND,
            ExpressionNodeType.OR,
            ExpressionNodeType.XOR,
            ExpressionNodeType.ADD,
            ExpressionNodeType.MUL,
            ExpressionNodeType.EQ,
        }
        
        # Define comparison operators that can be flipped
        comparison_flips = {
            ExpressionNodeType.GT: ExpressionNodeType.LT,
            ExpressionNodeType.LT: ExpressionNodeType.GT,
            ExpressionNodeType.GTE: ExpressionNodeType.LTE,
            ExpressionNodeType.LTE: ExpressionNodeType.GTE,
        }
        
        # Sort children for commutative operations
        if self.node_type in commutative_ops and len(canonical_children) >= 2:
            canonical_children.sort(key=lambda x: self._expression_sort_key(x))
        
        # Normalize comparisons: prefer smaller expression on left
        elif self.node_type in comparison_flips and len(canonical_children) == 2:
            left, right = canonical_children
            if self._expression_sort_key(left) > self._expression_sort_key(right):
                # Flip the comparison
                canonical_children = [right, left]
                new_type = comparison_flips[self.node_type]
                return CypherExpression(
                    node_type=new_type,
                    children=canonical_children,
                    metadata=self.metadata.copy()
                )
        
        return CypherExpression(
            node_type=self.node_type,
            value=self.value,
            children=canonical_children,
            metadata=self.metadata.copy()
        )
    
    @staticmethod
    def _expression_sort_key(expr: CypherExpression) -> tuple:
        """Generate a sort key for expression ordering.
        
        Creates a tuple that can be used for sorting expressions in a
        deterministic way. The sort key prioritizes expression types
        (literals before variables before properties, etc.) and uses
        value and structure for secondary sorting.
        
        Parameters
        ----------
        expr : CypherExpression
            The expression to generate a sort key for.
        
        Returns
        -------
        tuple
            A tuple (priority, value_str, children_count, node_type_value) that
            can be used for sorting expressions. Lower values sort first.
        
        Notes
        -----
        Type priority ordering (lower numbers sort first):
            0: LITERAL - literal values
            1: VARIABLE - variable references
            2: PARAMETER - query parameters
            3: PROPERTY - property access
            4: FUNCTION - function calls
            5: All other types (operators, etc.)
        """
        # Priority: literals < variables < properties < functions < operators
        type_priority = {
            ExpressionNodeType.LITERAL: 0,
            ExpressionNodeType.VARIABLE: 1,
            ExpressionNodeType.PARAMETER: 2,
            ExpressionNodeType.PROPERTY: 3,
            ExpressionNodeType.FUNCTION: 4,
        }
        
        priority = type_priority.get(expr.node_type, 5)
        value_str = str(expr.value) if expr.value is not None else ""
        children_count = len(expr.children)
        
        return (priority, value_str, children_count, expr.node_type.value)
    
    def to_zss_tree(self) -> ZssNode:
        """Convert this expression to a zss tree for edit distance computation.
        
        The zss library (Zhang-Shasha algorithm) is used to compute tree edit
        distance between two ASTs. Each node is labeled with its type, value,
        and metadata for accurate comparison.
        
        Returns
        -------
        ZssNode
            A ZssNode representing this expression tree, compatible with the
            zss library's tree edit distance algorithm.
        
        Notes
        -----
        Node labels are formatted as:
            - "{node_type}" for nodes without value or metadata
            - "{node_type}: {value}" for nodes with values
            - "{node_type}: {value} [{metadata}]" for nodes with metadata
        
        The tree structure is preserved through recursive conversion of children.
        
        See Also
        --------
        tree_edit_distance : Computes distance using the ZSS tree representation
        
        Examples
        --------
        >>> expr = CypherExpression(
        ...     node_type=ExpressionNodeType.ADD,
        ...     children=[...]
        ... )
        >>> zss_tree = expr.to_zss_tree()
        >>> # zss_tree can now be used with zss.simple_distance()
        """
        label =f"{self.node_type.value}"
        if self.value is not None:
            label += f": {self.value}"
        if self.metadata:
            metadata_str = ", ".join(f"{k}={v}" for k, v in self.metadata.items())
            label += f" [{metadata_str}]"
        
        # Recursively convert children
        zss_children = [child.to_zss_tree() for child in self.children]
        
        return ZssNode(label, zss_children)
    
    def tree_edit_distance(self, other: CypherExpression) -> int:
        """Compute tree edit distance to another expression.
        
        Uses the zss library to compute the minimum number of node insertions,
        deletions, and relabelings needed to transform this tree into the other.
        This implements the Zhang-Shasha tree edit distance algorithm.
        
        Both expressions should be in canonical form before calling this method
        for best results, as this ensures semantically equivalent expressions
        are compared correctly.
        
        Parameters
        ----------
        other : CypherExpression
            The expression to compare against.
        
        Returns
        -------
        int
            The tree edit distance (integer >= 0). Lower values indicate
            more similar expressions. A distance of 0 means the trees are
            structurally identical.
        
        Notes
        -----
        The tree edit distance counts the minimum number of operations needed:
            - Insert a node
            - Delete a node
            - Relabel a node (change its type or value)
        
        See Also
        --------
        similarity_score : Normalized version of tree edit distance
        to_canonical_form : Should be called before computing distance
        
        Examples
        --------
        >>> expr1 = CypherExpression(...).to_canonical_form()
        >>> expr2 = CypherExpression(...).to_canonical_form()
        >>> distance = expr1.tree_edit_distance(expr2)
        >>> print(f"Edit distance: {distance}")
        """
        self_tree = self.to_zss_tree()
        other_tree = other.to_zss_tree()
        
        return simple_distance(self_tree, other_tree)
    
    def _count_nodes(self) -> int:
        """Count the total number of nodes in this expression tree.
        
        Performs a recursive count of this node plus all descendant nodes
        in the expression tree. Used for normalizing similarity scores.
        
        Returns
        -------
        int
            Total number of nodes including this node and all descendants.
            Minimum value is 1 (for a leaf node).
        """
        return 1 + sum(child._count_nodes() for child in self.children)

    def similarity_score(self, other: CypherExpression) -> float:
        """Compute similarity score based on tree edit distance.
        
        Calculates a normalized similarity metric in the range [0, 1] based on
        the tree edit distance between this expression and another. The score
        is normalized by the maximum possible distance (sum of both tree sizes).
        
        Parameters
        ----------
        other : CypherExpression
            The expression to compare against.
        
        Returns
        -------
        float
            Normalized similarity score in the range [0, 1], where:
            - 1.0 = identical trees (distance = 0)
            - 0.0 = completely different trees (distance = max possible)
            - Values in between indicate partial similarity
        
        Notes
        -----
        The similarity is computed as:
            similarity = 1.0 - (edit_distance / max_distance)
        
        Where max_distance is the sum of both tree sizes (the distance when
        completely deleting one tree and inserting the other).
        
        Special case: If both trees are empty, returns 1.0.
        
        See Also
        --------
        tree_edit_distance : Computes the raw edit distance
        
        Examples
        --------
        >>> expr1 = CypherExpression(...)
        >>> expr2 = CypherExpression(...)
        >>> score = expr1.similarity_score(expr2)
        >>> print(f"Similarity: {score:.2%}")
        """
        distance = self.tree_edit_distance(other)
        
        # Compute tree sizes (number of nodes)
        self_size = self._count_nodes()
        other_size = other._count_nodes()
        
        # Maximum possible distance is the sum of both tree sizes
        # (delete all nodes from one tree, insert all nodes from the other)
        max_distance = self_size + other_size
        
        if max_distance == 0:
            return 1.0  # Both trees are empty
        
        # Normalize to [0, 1]: similarity = 1 - (distance / max_distance)
        return 1.0 - (distance / max_distance)
    
    def __repr__(self) -> str:
        """String representation for debugging.
        
        Returns
        -------
        str
            A human-readable string representation showing the node type,
            value (if present), or number of children.
        """
        if self.value is not None:
            return f"CypherExpression({self.node_type.value}, value={self.value})"
        elif self.children:
            return f"CypherExpression({self.node_type.value}, children={len(self.children)})"
        else:
            return f"CypherExpression({self.node_type.value})"
    
    def get_tree_str(self, indent: int = 0) -> str:
        """Print the expression tree for debugging.
        
        Creates a formatted string representation of the expression tree
        with indentation to show the hierarchical structure. Uses an iterative
        approach with a stack to avoid recursion depth limits.
        
        Parameters
        ----------
        indent : int, default=0
            The initial indentation level (number of 2-space indents) for the
            root node.
        
        Returns
        -------
        str
            A multi-line string showing the tree structure with:
            - Node type on each line
            - Value (if present) after the node type
            - Metadata (if present) in square brackets
            - Children indented by 2 spaces per level
        
        Examples
        --------
        >>> expr = CypherExpression(...)
        >>> print(expr.get_tree_str())
        AND
          EQ
            VARIABLE: a
            LITERAL: 5
          GT
            VARIABLE: b
            LITERAL: 10
        """
        output_lines = []
        # Stack holds tuples of (node, indent_level)
        stack = [(self, indent)]
        
        while stack:
            node, current_indent = stack.pop()
            
            # Format current node
            prefix = "  " * current_indent
            line = f"{prefix}{node.node_type.value}"
            if node.value is not None:
                line += f": {node.value}"
            if node.metadata:
                metadata_str = ", ".join(f"{k}={v}" for k, v in node.metadata.items())
                line += f" [{metadata_str}]"
            
            output_lines.append(line)
            
            # Add children to stack in reverse order to maintain left-to-right traversal
            for child in reversed(node.children):
                stack.append((child, current_indent + 1))
        
        return "\n".join(output_lines)

    def __str__(self) -> str:
        return self.get_tree_str()

    def __eq__(self, other: Any) -> bool:
        """Check equality between two CypherExpression instances.
        
        Compares node type, value, and metadata. Note that children are
        commented out in the comparison to avoid infinite recursion issues.
        
        Parameters
        ----------
        other : Any
            The other object to compare against.
        
        Returns
        -------
        bool
            True if node_type, value, and metadata are equal, False otherwise.
        NotImplemented
            If other is not a CypherExpression instance.
        """
        if not isinstance(other, CypherExpression):
            return NotImplemented
        return (
            self.node_type == other.node_type
            and self.value == other.value
            # This is a recursive check
            # and self.children == other.children
            and self.metadata == other.metadata
        )

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
    find_optimal_mapping(other, similarity_metric, minimize=False) -> tuple[float, GraphPattern.Mapping]
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

    def add_node(
        self,
        labels: set[str],
        properties: dict[str, CypherExpression],
        variable: Optional[str] = None,
    ) -> str:
        """Add a node to the graph pattern or merge with existing node.

        If a node with the given variable already exists, the labels and
        properties are merged with the existing node. If no variable is
        provided, an anonymous variable is generated automatically.

        Parameters
        ----------
        labels : set[str]
            Set of labels to assign to the node (e.g., {'Person', 'Employee'}).
            Will be merged with existing labels if the node already exists.
        properties : dict[str, CypherExpression]
            Dictionary of properties for the node. Keys are property names,
            values are CypherExpression objects. Will be merged with existing
            properties if the node already exists.
        variable : Optional[str], default=None
            Optional variable name for the node. If None, generates an anonymous
            variable in the format '__anon_node_N' where N is an incrementing counter.

        Returns
        -------
        str
            The variable name assigned to the node (either provided or generated).

        Raises
        ------
        ValueError
            If the variable is already used for an edge or subgraph.
            Node and edge/subgraph variables must be distinct.
        
        Examples
        --------
        >>> pattern = GraphPattern()
        >>> # Add node with explicit variable
        >>> var1 = pattern.add_node(labels={'Person'}, properties={}, variable='a')
        >>> # Add anonymous node
        >>> var2 = pattern.add_node(labels={'Company'}, properties={})
        >>> print(var2)  # '__anon_node_0'
        """
        
        if variable in self.edges:
            raise ValueError(
                f"Variable '{variable}' already used for an edge. "
                "Node and edge variables must be distinct."
            )
        
        if variable in self.sub_graphs:
            raise ValueError(
                f"Variable '{variable}' already used for a subgraph. "
                "Node and subgraph variables must be distinct."
            )
        
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
        properties: dict[str, CypherExpression],
        edge_variable: Optional[str] = None,
        range_literal: Optional[str] = None,
    ) -> str:
        """Add an edge to the graph pattern or merge with existing edge.

        If an edge with the given variable already exists, labels and properties
        are merged with the existing edge. If no variable is provided, an anonymous
        variable is generated automatically.

        Parameters
        ----------
        from_node : str
            Variable name of the source node. This node must exist or be added
            to the pattern.
        to_node : str
            Variable name of the target node. This node must exist or be added
            to the pattern.
        labels : set[str]
            Set of relationship types (e.g., {'KNOWS', 'FRIENDS'}). Multiple
            types correspond to Cypher's | operator in relationship patterns.
            Will be merged with existing labels if the edge already exists.
        properties : dict[str, CypherExpression]
            Dictionary of properties for the edge. Keys are property names,
            values are CypherExpression objects. Will be merged with existing
            properties if the edge already exists.
        edge_variable : Optional[str], default=None
            Optional variable name for the relationship. If None, generates an
            anonymous variable in the format '__anon_edge_N' where N is an
            incrementing counter.
        range_literal : Optional[str], default=None
            Optional range literal for variable-length relationships (e.g., '*1..5',
            '*', '*2..'). Used in path patterns with variable-length relationships.

        Returns
        -------
        str
            The variable name assigned to the edge (either provided or generated).

        Raises
        ------
        ValueError
            If the edge_variable is already used for a node or subgraph.
            Node and edge/subgraph variables must be distinct.
        
        Examples
        --------
        >>> pattern = GraphPattern()
        >>> n1 = pattern.add_node(labels={'Person'}, properties={}, variable='a')
        >>> n2 = pattern.add_node(labels={'Person'}, properties={}, variable='b')
        >>> # Add edge with explicit variable
        >>> e1 = pattern.add_edge(n1, n2, labels={'KNOWS'}, properties={}, edge_variable='r')
        >>> # Add anonymous edge
        >>> e2 = pattern.add_edge(n1, n2, labels={'WORKS_WITH'}, properties={})
        >>> print(e2)  # '__anon_edge_0'
        """
        
        if edge_variable in self.nodes:
            raise ValueError(
                f"Variable '{edge_variable}' already used for a node. "
                "Node and edge variables must be distinct."
            )
        
        if edge_variable in self.sub_graphs:
            raise ValueError(
                f"Variable '{edge_variable}' already used for a subgraph. "
                "Edge and subgraph variables must be distinct."
            )
        
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
                range_literal=range_literal,
            )

        self.edges[edge_variable].labels.update(labels)
        self.edges[edge_variable].properties.update(properties)
        return edge_variable

    def add_subgraph(self, variable: str) -> GraphPattern.SubGraph:
        """Add a subgraph to the graph pattern.

        Subgraphs represent named path patterns in Cypher queries, where an
        entire pattern can be assigned to a variable (e.g., 'p = (a)-[r]->(b)').

        Parameters
        ----------
        variable : str
            Variable name for the subgraph. Must not conflict with existing
            node or edge variables.

        Returns
        -------
        GraphPattern.SubGraph
            The SubGraph instance that was added or already exists for the
            given variable.

        Raises
        ------
        ValueError
            If the variable is already used for a node or edge.
            Node, edge, and subgraph variables must be distinct.
        
        Examples
        --------
        >>> pattern = GraphPattern()
        >>> subgraph = pattern.add_subgraph('p')
        >>> # The subgraph can now track nodes and edges that are part of path 'p'
        """
        
        if variable in self.nodes:
            raise ValueError(
                f"Variable '{variable}' already used for a node. "
                "Node and subgraph variables must be distinct."
            )
        
        if variable in self.edges:
            raise ValueError(
                f"Variable '{variable}' already used for an edge. "
                "Edge and subgraph variables must be distinct."
            )
        
        if variable not in self.sub_graphs:
            self.sub_graphs[variable] = GraphPattern.SubGraph()
        
        return self.sub_graphs[variable]

    # TODO: Add support for subgraph mappings
    def apply_mapping(self, mapping: GraphPattern.Mapping) -> GraphPattern:
        """Create a new GraphPattern with variables renamed according to the mapping.

        Variables not present in the mapping are kept unchanged. This is useful
        for aligning two patterns before comparison, enabling variable-agnostic
        pattern matching.

        Parameters
        ----------
        mapping : GraphPattern.Mapping
            A GraphPattern.Mapping containing node and edge variable mappings.
            The mapping specifies how to rename variables from this pattern.

        Returns
        -------
        GraphPattern
            A new GraphPattern instance with remapped variable names. The original
            pattern is not modified. The new pattern preserves:
            - Node labels and properties (with renamed variables)
            - Edge labels and properties (with renamed variables and endpoints)
            - Anonymous counter state
        
        Examples
        --------
        >>> pattern = GraphPattern()
        >>> # Pattern: (a:Person)-[r:KNOWS]->(b:Person)
        >>> mapping = GraphPattern.Mapping(
        ...     nodes_map={'a': 'x', 'b': 'y'},
        ...     edges_map={'r': 's'}
        ... )
        >>> new_pattern = pattern.apply_mapping(mapping)
        >>> # new_pattern: (x:Person)-[s:KNOWS]->(y:Person)
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

        A node is considered matching if it exists in both patterns with the
        same variable name and has overlapping labels. Properties are counted
        separately using similarity scores, only for nodes that match.

        Parameters
        ----------
        other : GraphPattern
            The GraphPattern to compare against.

        Returns
        -------
        tuple[int, int]
            A tuple of (matching_node_count, matching_node_property_count) where:
            - matching_node_count: Number of matching labels across all common nodes
            - matching_node_property_count: Sum of property similarity scores for
              matching nodes
        
        Notes
        -----
        This method assumes variables are already aligned. Use find_optimal_mapping
        to align variables before calling this method for accurate results.
        """
        matching_nodes: int = 0
        matching_node_properties: int = 0

        for variable, self_node in self.nodes.items():
            if variable in other.nodes:
                other_node = other.nodes[variable]

                matching_nodes_labels = len(
                    self_node.labels.intersection(other_node.labels)
                )

                matching_nodes += matching_nodes_labels

                for property_key, self_property_expr in self_node.properties.items():
                    other_property_expr = other_node.properties.get(property_key)
                    if other_property_expr is not None:
                        matching_node_properties += self_property_expr.similarity_score(
                            other_property_expr
                        )

        return matching_nodes, matching_node_properties

    def _count_edge_intersections(self, other: GraphPattern) -> tuple[int, int]:
        """Compute intersection counts for edges and their properties.

        An edge is considered matching if it exists in both patterns with the
        same variable name and connects the same source and target nodes
        (structurally equal). Properties and range literals are counted
        separately only for edges that match.

        Parameters
        ----------
        other : GraphPattern
            The GraphPattern to compare against.

        Returns
        -------
        tuple[int, int, int]
            A tuple of (matching_edge_count, matching_edge_property_count,
            matching_range_literals) where:
            - matching_edge_count: Number of matching relationship type labels
            - matching_edge_property_count: Sum of property similarity scores for
              matching edges
            - matching_range_literals: Number of matching range literals (for
              variable-length relationships)
        
        Notes
        -----
        This method assumes variables are already aligned. Use find_optimal_mapping
        to align variables before calling this method for accurate results.
        
        Edges are considered equal if they connect the same nodes (same from_node
        and to_node variables), regardless of labels or properties.
        """
        matching_edges: int = 0
        matching_edge_properties: int = 0
        matching_range_literals: int = 0

        for variable, self_edge in self.edges.items():
            if variable in other.edges:
                other_edge = other.edges[variable]

                if self_edge == other_edge:
                    matching_edges_labels = len(
                        self_edge.labels.intersection(other_edge.labels)
                    )
                    # if matching_edges_labels > 0:
                    matching_edges += matching_edges_labels

                    for property_key, self_property_expr in self_edge.properties.items():
                        other_property_expr = other_edge.properties.get(property_key)
                        if other_property_expr is not None:
                            matching_edge_properties += self_property_expr.similarity_score(
                                other_property_expr
                            )
                    
                    if self_edge.range_literal == other_edge.range_literal:
                        matching_range_literals += 1

        return matching_edges, matching_edge_properties, matching_range_literals

    def _count_total_elements(self) -> tuple[int, int, int, int]:
        """Count total nodes, edges, and their properties in this pattern.

        Returns
        -------
        tuple[int, int, int, int, int]
            A tuple of (node_count, edge_count, node_property_count,
            edge_property_count, range_literal_count) where:
            - node_count: Total number of node labels across all nodes
            - edge_count: Total number of relationship type labels across all edges
            - node_property_count: Total number of properties across all nodes
            - edge_property_count: Total number of properties across all edges
            - range_literal_count: Total number of edges with range literals
        
        Notes
        -----
        A node with multiple labels (e.g., :Person:Employee) contributes
        multiple counts to node_count. Similarly for edges with multiple
        relationship types.
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
        range_literal_count = sum(
            1 for edge in self.edges.values()
            if edge.range_literal is not None
        )
        return node_count, edge_count, node_property_count, edge_property_count, range_literal_count

    def jaccard(self, other: GraphPattern) -> float:
        """Calculate Jaccard similarity between this GraphPattern and another.

        The similarity is computed as:
            J = |Intersection| / |Union|

        Where intersection and union consider nodes, edges, their properties,
        range literals, and WHERE clauses. Uses the inclusion-exclusion principle:
        |Union| = |A| + |B| - |Intersection|.

        Parameters
        ----------
        other : GraphPattern
            The GraphPattern to compare against.

        Returns
        -------
        float
            Jaccard similarity score in range [0.0, 1.0] where:
            - 1.0 = patterns are identical
            - 0.0 = patterns have no elements in common
            - Values in between indicate partial overlap

        Notes
        -----
        Variables must be aligned before calling this method. Use
        find_optimal_mapping() to find the best alignment first, as this
        method assumes corresponding elements have the same variable names.
        
        The similarity metric includes:
            - Node labels
            - Edge labels (relationship types)
            - Node properties (with expression similarity)
            - Edge properties (with expression similarity)
            - Range literals for variable-length relationships
            - WHERE clause expressions (with expression similarity)
        
        See Also
        --------
        find_optimal_mapping : Find the best variable alignment between patterns
        
        Examples
        --------
        >>> pattern1 = GraphPattern()
        >>> pattern2 = GraphPattern()
        >>> # Assume patterns are already aligned
        >>> similarity = pattern1.jaccard(pattern2)
        >>> print(f"Jaccard similarity: {similarity:.2%}")
        """
        node_intersection, node_prop_intersection = self._count_node_intersections(
            other
        )
        edge_intersection, edge_prop_intersection, range_literal_intersection = self._count_edge_intersections(
            other
        )

        self_counts = self._count_total_elements()
        other_counts = other._count_total_elements()

        total_intersection = (
            node_intersection
            + edge_intersection
            + node_prop_intersection
            + edge_prop_intersection
            + range_literal_intersection
        )

        self_total = sum(self_counts)
        other_total = sum(other_counts)
        total_union = self_total + other_total - total_intersection

        where_similarity = self.where.similarity_score(other.where)
        total_intersection += where_similarity
        total_union += 1.0  # Count WHERE clause as one element in union

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
        differ by mapping the smaller set to subsets of the larger set. This
        enables finding optimal alignments even when patterns have different
        numbers of variables.

        Parameters
        ----------
        source_variables : list[str]
            List of variable names from the source pattern.
        target_variables : list[str]
            List of variable names from the target pattern.

        Yields
        ------
        dict[str, str]
            Dictionaries mapping source_variable -> target_variable. Each
            yielded mapping is a different injective function (one-to-one mapping)
            from the smaller set to a subset of the larger set.
        
        Notes
        -----
        Special cases:
            - If both lists are empty, yields one empty mapping: {}
            - If one list is empty and the other is not, yields one empty mapping: {}
            - Otherwise, generates all permutations of appropriate length
        
        The number of mappings generated is:
            P(n, k) = n! / (n-k)! where n = len(larger_set), k = len(smaller_set)
        
        Examples
        --------
        >>> mappings = list(GraphPattern._generate_injective_mappings(
        ...     ['a', 'b'],
        ...     ['x', 'y', 'z']
        ... ))
        >>> len(mappings)  # 3! / (3-2)! = 6
        6
        >>> mappings[0]  # Example: {'a': 'x', 'b': 'y'}
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
        mappings to find the one that optimizes the given metric. This enables
        variable-agnostic pattern comparison by finding the best alignment.

        Parameters
        ----------
        other : GraphPattern
            The target GraphPattern to map to.
        similarity_metric : Callable[[GraphPattern, GraphPattern], float]
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
        ...     similarity_metric=lambda p1, p2: p1.jaccard(p2),
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
        """Return a string representation of the GraphPattern.
        
        Returns
        -------
        str
            A string showing the nodes, edges, and subgraphs dictionaries.
        """
        return f"GraphPattern(nodes={self.nodes!r}, edges={self.edges!r}), sub_graphs={self.sub_graphs!r})"

@dataclass
class SingleCypherQuery:

    match_pattern: GraphPattern = field(default_factory=GraphPattern)
    optional_match_pattern: Optional[GraphPattern] = field(default_factory=GraphPattern)
    return_expr: CypherExpression = field(
        default_factory=lambda: CypherExpression(
            node_type=ExpressionNodeType.RETURN
        )
    )

    # TODO: Implement similarity scores for SingleCypherQuery

@dataclass
class CypherQuery:

    union_queries: List[SingleCypherQuery] = field(default_factory=list)

class CypherExtractor:
    """Parses CypherQuery objects and extracts GraphPattern representations.

    Uses tree-sitter for parsing with efficient non-recursive tree traversal
    via TreeCursor. The extractor follows the openCypher 9 grammar
    specification for parsing Cypher queries.

    This class provides methods to parse Cypher query strings into structured
    ASTs and extract graph patterns, expressions, and other query components.

    Attributes
    ----------
    _parser : Parser
        The tree-sitter Parser instance configured for Cypher language.

    Methods
    -------
    extract_query(cypher_query: str) -> CypherQuery
        Extract a CypherQuery from a Cypher query string.
    
    Notes
    -----
    The parser uses the openCypher 9 grammar, which corresponds roughly to
    Neo4j 3.5. Some modern Cypher features may not be fully supported.
    
    Private methods handle specific grammar rules:
        - _extract_single_query: Extracts single-part or multi-part queries
        - _process_match_clause: Processes MATCH and OPTIONAL MATCH clauses
        - _process_pattern: Processes pattern definitions
        - _extract_expression: Extracts and converts expressions to AST
        - And many more specialized extraction methods

    Examples
    --------
    >>> extractor = CypherExtractor()
    >>> query = extractor.extract_query("MATCH (n:Person) RETURN n")
    >>> pattern = query.union_queries[0].match_pattern
    >>> print(pattern.nodes)
    """

    def __init__(self, parser: Optional[Parser] = None) -> None:
        """Initialize the CypherExtractor.

        Parameters
        ----------
        parser : Optional[Parser], default=None
            Optional tree-sitter Parser instance configured for Cypher.
            If None, uses the default global parser configured with the
            Cypher language.
        """
        self._parser: Parser = parser if parser is not None else _default_parser

    # TODO: Suppress the syntax warning
    # SyntaxWarning: invalid escape sequence '\p'
    # unescaped_symbolic_name: () => (/(\p{ID_Start}|\p{Pc})(\p{ID_Continue}|\p{Sc})*/u),
    @staticmethod
    def _get_node_text(tree_node: Node) -> str:
        """Extract the source text from a tree-sitter node.

        Tree-Sitter JavaScript Grammar Rules compatible with this method:
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
            ),
            unescaped_symbolic_name: () => (/(\p{ID_Start}|\p{Pc})(\p{ID_Continue}|\p{Sc})*/u),
            escaped_symbolic_name: () => repeat1(/`[^`]*`/),
            reserved_word: () => choice(
                word('all'), 
                word('asc'), 
                word('ascending'), 
                word('by'), 
                word('create'),
                word('delete'), 
                word('desc'), 
                word('descending'), 
                word('detach'), 
                word('exists'), 
                word('limit'), 
                word('match'), 
                word('merge'), 
                word('on'), 
                word('optional'), 
                word('order'), 
                word('remove'), 
                word('return'), 
                word('set'), 
                word('skip'), 
                word('where'), 
                word('with'), 
                word('union'), 
                word('unwind'),
                word('and'), 
                word('as'), 
                word('contains'),
                word('distinct'), 
                word('ends'), 
                word('in'), 
                word('is'), 
                word('not'), 
                word('or'), 
                word('starts'), 
                word('xor'), 
                word('false'), 
                word('true'), 
                word('null'), 
                word('constraint'), 
                word('unique'), 
                word('case'), 
                word('when'), 
                word('then'), 
                word('else'), 
                word('end'), 
                word('mandatory'), 
                word('scalar'), 
                word('of'), 
                word('add'), 
                word('drop')
            ),
        ```

        Parameters
        ----------
        tree_node : Node
            The tree-sitter Node to extract text from.

        Returns
        -------
        str
            The decoded UTF-8 text content of the node.
        
        """
        return tree_node.text.decode("utf-8")

    # TODO: Handle also standalone calls?
    def extract_query(self, cypher_query: str) -> CypherQuery:
        """Extract a CypherQuery from a Cypher query string.

        Parses the input Cypher query string using tree-sitter and extracts
        a structured CypherQuery object containing all graph patterns, expressions,
        and clauses.

        Tree-Sitter JavaScript Grammar Rules:
        ```
            cypher: ($) => seq($.statement, optional(';')),
            statement: ($) => $.query,
            query: $ => choice($.regular_query, $.standalone_call),
            regular_query: ($) => seq($.single_query, repeat($.union)),
            union: ($) => seq(word('union'), optional(word('all')), $.single_query),
        ```

        Parameters
        ----------
        cypher_query : str
            A valid Cypher query string to parse.

        Returns
        -------
        CypherQuery
            A CypherQuery object containing extracted graph patterns, with
            one or more SingleCypherQuery objects in the union_queries list.
        
        Raises
        ------
        ValueError
            If the query fails to parse (syntax error in the Cypher query).
        NotImplementedError
            If the query is a standalone_call (not yet supported).
        
        Examples
        --------
        >>> extractor = CypherExtractor()
        >>> query = extractor.extract_query(
        ...     "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a"
        ... )
        >>> print(len(query.union_queries))  # 1
        >>> 
        >>> # Query with UNION
        >>> query2 = extractor.extract_query(
        ...     "MATCH (a:Person) RETURN a UNION MATCH (b:Company) RETURN b"
        ... )
        >>> print(len(query2.union_queries))  # 2
        """
        parse_tree: Tree = self._parser.parse(bytes(cypher_query, "utf-8"))
        cursor: TreeCursor = parse_tree.walk()

        if cursor.node.has_error:
            raise ValueError(
                "Failed to parse Cypher query. Please ensure the query is valid."
            )
        
        query = CypherQuery()
        
        statement_node = cursor.node.child(0)
        query_node = statement_node.child(0)
        child = query_node.child(0)
        if child.type == "regular_query":
            single_query_node = child.child(0)
            single_query = self._extract_single_query(single_query_node)
            query.union_queries.append(single_query)
            # TODO: How do we handle the 'union all' part?
            for i in range(1, child.child_count):
                union_node = child.child(i)
                union_query_node = union_node.child(union_node.child_count - 1)
                union_query = self._extract_single_query(union_query_node)
                query.union_queries.append(union_query)
        else: # standalone_call
            raise NotImplementedError(
                f"'{child.type}' queries are not supported yet."
            )
        return query
    
    # TODO: Handle also multi part queries
    def _extract_single_query(self, node: Node) -> SingleCypherQuery:
        """Extract a SingleCypherQuery from a single_query tree-sitter node.
        
        Processes a single query node which can be either a single-part query
        or a multi-part query. Currently only single-part queries are supported.
        Extracts MATCH clauses, OPTIONAL MATCH clauses, and RETURN clauses.
        
        Tree-Sitter JavaScript Grammar:
        ```
            single_query: ($) => choice($.single_part_query, $.multi_part_query),
            single_part_query: ($) => choice(
                seq(
                    repeat($.reading_clause),
                    $.return
                ), 
                seq(
                    repeat($.reading_clause), 
                    repeat1($.updating_clause), 
                    optional($.return)
                )
            ),
            multi_part_query: ($) => seq(
                repeat1(
                    seq(
                        repeat($.reading_clause), 
                        repeat($.updating_clause), 
                        $.with
                    )
                ), 
                $.single_part_query
            ),
            reading_clause: ($) => choice($.match, $.unwind, $.in_query_call),
            updating_clause: ($) => choice($.create, $.merge, $.delete, $.set, $.remove),
            with: ($) => seq(word('with'), $.projection_body, optional($.where)),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a single_query.

        Returns
        -------
        SingleCypherQuery
            A SingleCypherQuery object containing:
            - match_pattern: GraphPattern from MATCH clauses
            - optional_match_pattern: GraphPattern from OPTIONAL MATCH clauses
            - return_expr: CypherExpression from RETURN clause
        
        Raises
        ------
        NotImplementedError
            If the query is a multi-part query (not yet supported).
        
        Warnings
        --------
        Prints warnings for unsupported reading clauses (unwind, in_query_call)
        and updating clauses (create, merge, delete, set, remove).
        """

        single_query_child = node.child(0)
        if single_query_child.type == _SINGLE_PART_QUERY_TYPE:
            single_cypher_query = SingleCypherQuery()
            for child in single_query_child.children:
                if child.type == _READING_CLAUSE_TYPE:
                    reading_clause_child = child.child(0)
                    if reading_clause_child.type == _MATCH_TYPE:
                        self._process_match_clause(reading_clause_child, single_cypher_query)
                    else: # unwind, in_query_call
                        print(
                            "[WARNING]: Reading clauses of type "
                            f"'{reading_clause_child.type}' are not supported yet."
                        )
                elif child.type == _RETURN_TYPE:
                    single_cypher_query.return_expr = self._extract_expression(child)
                else:  # child.type == _UPDATING_CLAUSE_TYPE
                    print("[WARNING]: Updating clauses are not processed and supported yet.")
            return single_cypher_query                  
        else: # multi_part_query
            raise NotImplementedError(
                "[ERROR]: Multi-part queries are not supported yet."
            )

    def _process_match_clause(self, match_node: Node, single_cypher_query: SingleCypherQuery) -> None:
        """Process a MATCH clause node to extract pattern information.

        Extracts the graph pattern from a MATCH or OPTIONAL MATCH clause,
        including the WHERE clause if present. Updates the provided
        SingleCypherQuery object in-place with the extracted pattern.

        Tree-Sitter JavaScript Grammar:
        ```
            match: ($) => seq(
                optional(word('optional')), 
                word('match'), 
                $.pattern, 
                optional($.where)
            ),
            where: ($) => seq(word('where'), $.expression),
        ```

        Parameters
        ----------
        match_node : Node
            The tree-sitter Node representing a MATCH clause (with or without
            the OPTIONAL keyword).
        single_cypher_query : SingleCypherQuery
            The SingleCypherQuery object to update. Will populate either
            match_pattern or optional_match_pattern depending on whether
            OPTIONAL is present.

        Returns
        -------
        None
            Updates single_cypher_query in-place. Specifically:
            - For "MATCH": updates single_cypher_query.match_pattern
            - For "OPTIONAL MATCH": updates single_cypher_query.optional_match_pattern
            - Adds WHERE clause expression to the appropriate pattern if present
        
        Notes
        -----
        The WHERE clause expression is converted to canonical form before being
        added to the pattern for consistent comparison.
        """
        where_node = None
        
        if match_node.child(0).type == _OPTIONAL_TYPE:
            pattern_node = match_node.child(2)
            if match_node.child_count > 3 and match_node.child(3).type == _WHERE_TYPE:
                where_node = match_node.child(3)
            pattern = single_cypher_query.optional_match_pattern
        else:
            pattern_node = match_node.child(1)
            if match_node.child_count > 2 and match_node.child(2).type == _WHERE_TYPE:
                where_node = match_node.child(2)
            pattern = single_cypher_query.match_pattern
        
        self._process_pattern(pattern_node, pattern)
        
        if where_node is not None:
            where_expr = self._extract_expression(where_node)
            if where_expr:
                pattern.where = where_expr.to_canonical_form()

    def _process_pattern(
        self,
        pattern_node: Node,
        pattern_container: GraphPattern,
    ) -> None:
        """Process a pattern node containing one or more pattern parts.

        Extracts all pattern parts from a pattern node and adds them to the
        provided GraphPattern container. Handles both named paths (assigned to
        variables) and anonymous patterns.

        Tree-Sitter JavaScript Grammar:
        ```
            pattern: ($) => seq(
                $.pattern_part, 
                repeat(seq(',', $.pattern_part))
            ),
            pattern_part: ($) => choice(
                seq($.variable, '=', $.anonymous_pattern_part), 
                $.anonymous_pattern_part
            ),
            anonymous_pattern_part: ($) => $.pattern_element,
        ```

        Parameters
        ----------
        pattern_node : Node
            The tree-sitter Node representing the pattern. Contains one or more
            pattern_part children separated by commas.
        pattern_container : GraphPattern
            The GraphPattern object to populate with extracted data. Nodes,
            edges, and subgraphs are added to this container.

        Returns
        -------
        None
            Updates pattern_container in-place by adding:
            - Nodes from pattern elements
            - Edges from pattern elements
            - Subgraphs for named paths (when pattern is assigned to a variable)
        
        Notes
        -----
        Named paths (e.g., "p = (a)-[r]->(b)") create subgraphs that track which
        nodes and edges belong to that path.
        """
        for child in pattern_node.children:
            if child.type == _PATTERN_PART_TYPE:
                current_subgraph = None
                for patt_child in child.children:
                    if patt_child.type == _VARIABLE_TYPE:
                        symbolic_name_node = patt_child.child(0)
                        variable = self._get_node_text(symbolic_name_node)
                        current_subgraph = pattern_container.add_subgraph(variable)
                    elif patt_child.type == _ANONYMOUS_PATTERN_PART_TYPE:
                        patt_elem_node = patt_child.child(0)
                        self._process_pattern_element(patt_elem_node, pattern_container, current_subgraph)

    def _process_pattern_element(
        self,
        patt_elem_node: Node,
        pattern_container: GraphPattern,
        current_subgraph: Optional[GraphPattern.SubGraph] = None,
    ) -> None:
        """Process a pattern_element node containing nodes and relationships.

        Extracts a chain of nodes and relationships from a pattern element.
        Handles parenthesized patterns by unwrapping them. Processes each node
        pattern and relationship pattern in the chain, maintaining the connection
        structure.

        Tree-Sitter JavaScript Grammar:
        ```
            pattern_element: ($) => choice(
                seq($.node_pattern, repeat($.pattern_element_chain)), 
                seq('(', $.pattern_element, ')')
            ),
            pattern_element_chain: ($) => seq(
                $.relationship_pattern, 
                $.node_pattern
            ),
        ```

        Parameters
        ----------
        patt_elem_node : Node
            The tree-sitter Node representing the pattern element. This can be
            a simple node with relationship chains or a parenthesized pattern.
        pattern_container : GraphPattern
            The GraphPattern object to populate with extracted nodes and edges.
        current_subgraph : Optional[GraphPattern.SubGraph], default=None
            If provided, tracks which nodes and edges belong to this subgraph
            (for named path patterns).

        Returns
        -------
        None
            Updates pattern_container in-place by adding:
            - All nodes in the pattern element
            - All relationships connecting the nodes
            - Updates current_subgraph if provided
        
        Notes
        -----
        The method handles nested parentheses by unwrapping them recursively
        before processing the actual pattern.
        
        Pattern chains are processed left-to-right, maintaining the source node
        variable for each relationship in the chain.
        """
        left_node_variable: Optional[str] = None

        current_node = patt_elem_node
        first_child = current_node.child(0)
        while first_child.type == '(':
            current_node = current_node.child(1)
            first_child = current_node.child(0)

        for child in current_node.children:
            child_type = child.type

            if child_type == _NODE_PATTERN_TYPE:
                left_node_variable = self._extract_node_from_pattern(
                    child, pattern_container, current_subgraph
                )

            elif child_type == _PATTERN_ELEMENT_CHAIN_TYPE:
                relationship_node: Optional[Node] = None
                right_node_pattern: Optional[Node] = None

                relationship_node = child.child(0)
                right_node_pattern = child.child(1)

                right_node_variable = self._extract_node_from_pattern(
                    right_node_pattern, pattern_container, current_subgraph
                )
                self._extract_relationship(
                    relationship_node,
                    left_node_variable,
                    right_node_variable,
                    pattern_container,
                    current_subgraph
                )
                left_node_variable = right_node_variable

    def _extract_relationship(
        self,
        relationship_pattern: Node,
        left_variable: Optional[str],
        right_variable: Optional[str],
        pattern_container: GraphPattern,
        current_subgraph: Optional[GraphPattern.SubGraph] = None,
    ) -> None:
        """Extract relationship information from a relationship_pattern node.

        Parses a relationship pattern to extract its variable, relationship types,
        properties, range literal, and direction (indicated by arrow heads).
        Adds the relationship(s) to the pattern container with correct direction.

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
            relationship_types: ($) => seq(
                ':', 
                $.rel_type_name, 
                repeat(seq('|', optional(':'), $.rel_type_name))
            ),
            rel_type_name: ($) => $.schema_name,
            range_literal: ($) => seq(
                '*', 
                optional($.integer_literal), 
                optional(
                    seq(
                        '..', 
                        optional($.integer_literal)
                    )
                )
            ),
        ```

        Parameters
        ----------
        relationship_pattern : Node
            The tree-sitter Node representing a relationship pattern.
        left_variable : Optional[str]
            Variable name of the source node (left side of relationship).
        right_variable : Optional[str]
            Variable name of the target node (right side of relationship).
        pattern_container : GraphPattern
            The GraphPattern object to add the extracted relationship to.
        current_subgraph : Optional[GraphPattern.SubGraph], default=None
            If provided, adds the relationship variable to this subgraph.

        Returns
        -------
        None
            Updates pattern_container in-place by adding one or two edges:
            - If left arrow head present: adds edge from right to left
            - If right arrow head present: adds edge from left to right
            - If both present: adds edges in both directions
            - If neither present: adds edges in both directions (undirected)
        
        Notes
        -----
        The relationship can have:
            - Multiple relationship types (e.g., [:KNOWS|FRIENDS])
            - Properties (e.g., [:KNOWS {since: 2020}])
            - Variable-length range (e.g., [:KNOWS*1..5])
            - Bidirectional arrows (creates two directed edges)
        """
        edge_variable: Optional[str] = None
        labels: set[str] = set()
        properties: dict[str, Any] = {}
        range_literal: Optional[str] = None

        direction_left = True
        direction_right = True
        rel_detail_index = 1
        child_count = relationship_pattern.child_count
        if relationship_pattern.child(0).type != _LEFT_ARROW_HEAD_TYPE:
            direction_left = False
        else:
            rel_detail_index = 2
        if relationship_pattern.child(child_count - 1).type != _RIGHT_ARROW_HEAD_TYPE:
            direction_right = False

        rel_detail_node = relationship_pattern.child(rel_detail_index)

        for detail_child in rel_detail_node.children:
            detail_type = detail_child.type

            if detail_type == _VARIABLE_TYPE:
                symbolic_name_node = detail_child.child(0)
                edge_variable = self._get_node_text(symbolic_name_node)

            elif detail_type == _RELATIONSHIP_TYPES_TYPE:
                # Extract all relationship types (handles [:TYPE1|TYPE2|TYPE3])
                for type_child in detail_child.children:
                    if type_child.type == _REL_TYPE_NAME_TYPE:
                        label = self._get_node_text(type_child.children[0])
                        labels.add(label)

            elif detail_type == _RANGE_LITERAL_TYPE:
                range_literal = self._get_node_text(detail_child) # self.get_range_literal(detail_child)

            elif detail_type == _PROPERTIES_TYPE:
                properties = self._extract_properties_from_node(detail_child)

        if direction_left:
            variable = pattern_container.add_edge(
                right_variable, left_variable, 
                labels, properties, edge_variable,
                range_literal
            )
            if current_subgraph is not None:
                current_subgraph.edges_vars.add(variable)
        if direction_right:
            variable = pattern_container.add_edge(
                left_variable, right_variable,
                labels, properties, edge_variable,
                range_literal
            )
            if current_subgraph is not None:
                current_subgraph.edges_vars.add(variable)

    def _extract_node_from_pattern(
        self,
        node_pattern: Node,
        pattern_container: GraphPattern,
        current_subgraph: Optional[GraphPattern.SubGraph] = None,
    ) -> str:
        """Extract node information from a node_pattern and add to container.

        Parses a node pattern to extract its variable, labels, and properties.
        Adds the node to the pattern container and optionally to a subgraph.

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
            ),
            node_labels: ($) => prec.right(repeat1($.node_label)),
            node_label: ($) => seq(':', $.label_name),
            label_name: ($) => $.schema_name,
            variable_in_parens: ($) => seq('(', $.variable, ')'),
            variable: ($) => $.symbolic_name,
        ```

        Parameters
        ----------
        node_pattern : Node
            The tree-sitter Node representing a node pattern. Can be either a
            simple variable in parentheses or a full node with labels and properties.
        pattern_container : GraphPattern
            The GraphPattern object to add the extracted node to.
        current_subgraph : Optional[GraphPattern.SubGraph], default=None
            If provided, adds the node variable to this subgraph (for named paths).

        Returns
        -------
        str
            The variable name assigned to the extracted node. This can be either:
            - The explicit variable from the pattern (e.g., 'a' in '(a:Person)')
            - An auto-generated anonymous variable (e.g., '__anon_node_0')
        
        Notes
        -----
        A node can have:
            - Zero or more labels (e.g., () or (a) or (a:Person) or (a:Person:Employee))
            - Zero or more properties (e.g., (a {name: 'Alice', age: 30}))
            - An optional variable name
        """
        variable: Optional[str] = None
        labels: set[str] = set()
        properties: dict[str, Any] = {}

        for child in node_pattern.children:
            child_type = child.type

            if child_type == _VARIABLE_TYPE:
                symbolic_name_node = child.child(0)
                variable = self._get_node_text(symbolic_name_node)

            elif child_type == _NODE_LABELS_TYPE:
                for label_child in child.children:
                    label_name_node = label_child.child(1)
                    schema_name_node = label_name_node.child(0)
                    label_name = self._get_node_text(schema_name_node)
                    if label_name:
                        labels.add(label_name)

            elif child_type == _PROPERTIES_TYPE:
                properties = self._extract_properties_from_node(child)

        variable = pattern_container.add_node(labels, properties, variable)
        if current_subgraph is not None:
            current_subgraph.nodes_vars.add(variable)
        return variable

    # TODO: Handle parameter rule?
    def _extract_properties_from_node(
        self, properties_node: Node
    ) -> dict[str, Any]:
        """Extract properties from a properties node.

        Parses a properties node which can be either a map literal with
        explicit key-value pairs or a parameter reference. Currently only
        map literals are supported.

        Tree-Sitter JavaScript Grammar:
        ```
            properties: ($) => prec(1, choice($.map_literal, $.parameter)),
            parameter: ($) => seq('$', choice($.symbolic_name, $.decimal_integer)),
            map_literal: ($) => seq('{', 
                optional(
                    seq(
                        $.property_key_name, ':', 
                        $.expression, 
                        repeat(seq(',', $.property_key_name, ':', $.expression))
                    )
                ), 
            '}'),
            property_key_name: ($) => $.schema_name,
        ```

        Parameters
        ----------
        properties_node : Node
            The tree-sitter Node representing properties. Should contain a
            map_literal or parameter child node.

        Returns
        -------
        dict[str, CypherExpression]
            Dictionary of property key-value pairs where:
            - Keys are property names (strings)
            - Values are CypherExpression objects representing the property values

        Raises
        ------
        NotImplementedError
            If the properties node is a parameter reference (not yet supported).
        
        Examples
        --------
        For a properties node representing "{name: 'Alice', age: 30}":
        >>> props = extractor._extract_properties_from_node(properties_node)
        >>> # props == {'name': CypherExpression(...), 'age': CypherExpression(...)}
        """
        child = properties_node.child(0)
        if child.type != _MAP_LITERAL_TYPE:
            # For now do not handle parameter rules
            raise NotImplementedError(
                f"Properties of type '{child.type}' not implemented."
            )

        properties: dict[str, CypherExpression] = {}
        current_key: Optional[str] = None

        for child in child.children:
            child_type = child.type

            if child_type == _PROPERTY_KEY_NAME_TYPE:
                current_key = self._get_node_text(child.child(0))

            elif child_type == _EXPRESSION_TYPE:
                value = self._extract_expression(child)
                properties[current_key] = value
                current_key = None

        return properties


    def _extract_expression(self, expression_node: Node) -> Optional[CypherExpression]:
        """Extract a Cypher expression and convert it to CypherExpression AST.
        
        This method recursively parses tree-sitter expression nodes and converts
        them into a structured CypherExpression AST representation. It handles
        all types of Cypher expressions including logical operators, comparisons,
        arithmetic, predicates, functions, and literals.

        Tree-Sitter JavaScript Grammar Rules:
        ```
            expression: ($) => choice(
                $.or_expression, 
                $.xor_expression, 
                $.and_expression, 
                $.not_expression, 
                $.comparison_expression, 
                $.string_list_null_predicate_expression, 
                $.additive_expression, 
                $.multiplicative_expression, 
                $.exponential_expression, 
                $.unary_expression, 
                $.list_operator_expression, 
                $.property_or_labels_expression, 
                $.atom
            ),
            return: ($) => seq(word('return'), $.projection_body),
        ```
        
        Parameters
        ----------
        expression_node : Node
            The tree-sitter Node representing an expression. Can be any type of
            Cypher expression as defined in the grammar.
        
        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression AST representing the parsed expression, or None
            if the expression could not be parsed.
        
        Raises
        ------
        NotImplementedError
            If the expression type is not yet implemented.
        
        Notes
        -----
        This method dispatches to specialized extraction methods based on the
        child node type:
            - Logical: _extract_binary_expression, _extract_unary_expression
            - Comparison: _extract_comparison_expression
            - Predicates: _extract_predicate_expression
            - Arithmetic: _extract_arithmetic_expression, _extract_unary_arithmetic_expression
            - List ops: _extract_list_operator_expression
            - Property: _extract_property_expression
            - Atoms: _extract_atom_expression
            - Special: _extract_projection_body (for RETURN/WITH)
        """
        
        child = expression_node.child(0)
        child_type = child.type
        
        # Logical operators (binary)
        if child_type == "where":
            child_expr = self._extract_expression(expression_node.child(1))
            return CypherExpression(
                node_type=ExpressionNodeType.WHERE,
                children=[child_expr]
            )
        elif child_type == "return":
            child_expr = self._extract_projection_body(expression_node.child(1))
            return CypherExpression(
                node_type=ExpressionNodeType.RETURN,
                children=[child_expr]
            )
        elif child_type == "or_expression":
            return self._extract_binary_expression(child, ExpressionNodeType.OR)
        elif child_type == "xor_expression":
            return self._extract_binary_expression(child, ExpressionNodeType.XOR)
        elif child_type == "and_expression":
            return self._extract_binary_expression(child, ExpressionNodeType.AND)
        
        # Logical operators (unary)
        elif child_type == "not_expression":
            return self._extract_unary_expression(child, ExpressionNodeType.NOT)
        
        # Comparison operators
        elif child_type == "comparison_expression":
            return self._extract_comparison_expression(child)
        
        # String/List/Null predicates
        elif child_type == "string_list_null_predicate_expression":
            return self._extract_predicate_expression(child)
        
        # Arithmetic operators
        elif child_type == "additive_expression":
            return self._extract_arithmetic_expression(child)
        elif child_type == "multiplicative_expression":
            return self._extract_arithmetic_expression(child)
        elif child_type == "exponential_expression":
            return self._extract_binary_expression(child, ExpressionNodeType.POW)
        elif child_type == "unary_expression":
            return self._extract_unary_arithmetic_expression(child)
        
        # List operators
        elif child_type == "list_operator_expression":
            return self._extract_list_operator_expression(child)
        
        # Property access
        elif child_type == "property_or_labels_expression":
            return self._extract_property_expression(child)
        
        # Atoms (base cases)
        elif child_type == "atom":
            return self._extract_atom_expression(child)

        else:
            raise NotImplementedError(f"Expression type '{child_type}' not implemented.")
    
    def _extract_projection_body(self, node: Node) -> Optional[CypherExpression]:
        """Extract a projection body from RETURN or WITH clauses.
        
        Parses the projection body which includes the items to return/project,
        along with optional DISTINCT, ORDER BY, SKIP, and LIMIT clauses.
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
            projection_body: ($) => seq(
                optional(word('distinct')), 
                $.projection_items,
                optional($.order), 
                optional($.skip), 
                optional($.limit)
            ),
            skip: ($) => seq(word('skip'), $.expression),
            limit: ($) => seq(word('limit'), $.expression),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a projection_body.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with node_type=PROJECTION_BODY containing children:
            - DISTINCT expression (if present)
            - PROJECTION_ITEMS expression (always present)
            - ORDER expression (if ORDER BY present)
            - SKIP expression (if SKIP present)
            - LIMIT expression (if LIMIT present)
        """
        children: List[CypherExpression] = []
        for child in node.children:
            child_type = child.type
            if child_type == "distinct":
                children.append(
                    CypherExpression(
                        node_type=ExpressionNodeType.DISTINCT
                    )
                )
            elif child_type == "projection_items":
                proj_items_expr = self._extract_projection_items(child)
                children.append(proj_items_expr)
            elif child_type == "order":
                order_expr = self._extract_order_expression(child)
                children.append(order_expr)
            elif child_type == "skip":
                skip_expr = self._extract_expression(child.child(1))
                children.append(CypherExpression(
                    node_type=ExpressionNodeType.SKIP,
                    children=[skip_expr]
                ))
            elif child_type == "limit":
                limit_expr = self._extract_expression(child.child(1))
                children.append(
                    CypherExpression(
                        node_type=ExpressionNodeType.LIMIT,
                        children=[limit_expr]
                    )
                )

        return CypherExpression(
            node_type=ExpressionNodeType.PROJECTION_BODY,
            children=children
        )

    def _extract_order_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract ORDER BY clause expression.
        
        Parses the ORDER BY clause which contains one or more sort items,
        each with an expression and optional sort direction (ASC/DESC).
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
            order: ($) => seq(
                word('order'), 
                word('by'), 
                $.sort_item, 
                repeat(seq(',', $.sort_item))
            ),
            sort_item: ($) => seq(
                $.expression, 
                optional(
                    choice(
                        word('asc'), 
                        word('ascending'), 
                        word('desc'), 
                        word('descending')
                    )
                )
            ),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing an order clause.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with node_type=ORDER containing children expressions,
            each with optional 'order' metadata set to 'ASC' or 'DESC'.
        """
        children: List[CypherExpression] = []
        for child in node.children:
            child_type = child.type
            if child_type == "sort_item":
                sort_item_expr = self._extract_expression(child.child(0))
                if child.child_count == 2:
                    order_direction = child.child(1).type
                    if order_direction in ["asc", "ascending"]:
                        sort_item_expr.metadata['order'] = 'ASC'
                    elif order_direction in ["desc", "descending"]:
                        sort_item_expr.metadata['order'] = 'DESC'
                children.append(sort_item_expr)

        return CypherExpression(
            node_type=ExpressionNodeType.ORDER,
            children=children
        )

    def _extract_projection_items(self, node: Node) -> Optional[CypherExpression]:
        """Extract projection items from RETURN or WITH clauses.
        
        Parses the items to be returned/projected, which can be either * (all)
        or a list of specific expressions with optional aliases.
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
            projection_items: ($) => choice(
                seq(
                    '*',
                    repeat(
                        seq(',', $.projection_item)
                    )
                ), 
                seq(
                    $.projection_item, 
                    repeat(seq(',', $.projection_item))
                )
            ),
            projection_item: ($) => choice(
                $.expression, 
                seq($.expression, word('as'), $.variable)
            ),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing projection_items.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with node_type=PROJECTION_ITEMS containing children:
            - ALL_PROPERTIES expression (if * is present)
            - Individual projection expressions (with optional 'as' metadata for aliases)
        """
        children: List[CypherExpression] = []
        for child in node.children:
            child_type = child.type
            if child_type == '*':
                children.append(
                    CypherExpression(
                        node_type=ExpressionNodeType.ALL_PROPERTIES
                    )
                )
            elif child_type == 'projection_item':
                projection_item_expr = self._extract_expression(child.child(0))
                if child.child_count == 3:
                    projection_item_expr.metadata['as'] = self._get_node_text(child.child(2))
                children.append(projection_item_expr)

        return CypherExpression(
            node_type=ExpressionNodeType.PROJECTION_ITEMS,
            children=children
        )

    def _extract_binary_expression(
        self, node: Node, op_type: ExpressionNodeType
    ) -> Optional[CypherExpression]:
        """Extract a binary expression.
        
        Parses binary operators including logical (OR, XOR, AND) and arithmetic
        (POW) operators. The expression consists of a left operand, operator,
        and right operand.
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
            or_expression: ($) => prec.left(1, seq($.expression, word('or'), $.expression)),
            xor_expression: ($) => prec.left(2, seq($.expression, word('xor'), $.expression)),
            and_expression: ($) => prec.left(3, seq($.expression, word('and'), $.expression)),
            exponential_expression: ($) => prec.left(9, seq($.expression, '^', $.expression)),
        ```

        The returned tree structure is:
        ```
            op_type
                left_expr
                right_expr
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a binary expression.
        op_type : ExpressionNodeType
            The type of binary operator (e.g., OR, XOR, AND, POW).

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with the specified op_type and two children
            (left and right operands).
        """

        left_expr = self._extract_expression(node.child(0))
        right_expr = self._extract_expression(node.child(2))

        return CypherExpression(
            node_type=op_type,
            children=[left_expr, right_expr]
        )
    
    def _extract_unary_expression(
        self, node: Node, op_type: ExpressionNodeType
    ) -> Optional[CypherExpression]:
        """Extract a unary expression.
        
        Parses unary operators, primarily the NOT operator for logical negation.
        The expression consists of the operator followed by a single operand.
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
            not_expression: ($) => prec(4, seq(word('not'), $.expression)),
        ```

        The returned tree structure is:
        ```
            op_type
                operand
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a unary expression.
        op_type : ExpressionNodeType
            The type of unary operator (e.g., NOT).

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with the specified op_type and one child (operand).
        """
        operand = self._extract_expression(node.child(1))
        return CypherExpression(
            node_type=op_type,
            children=[operand]
        )
    
    def _extract_comparison_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract comparison expressions.
        
        Parses comparison operators including equality, inequality, and
        relational comparisons. Maps operator symbols to their corresponding
        ExpressionNodeType values.
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
            comparison_expression: ($) => prec.left(5,
                seq(
                    $.expression, 
                    seq(choice('=', '<>', '<', '>', '<=', '>='), 
                    $.expression)
                )
            ),
        ```

        The returned tree structure is:
        ```
            op_type
                left_expr
                right_expr
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a comparison expression.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with the appropriate comparison operator type
            (EQ, NEQ, LT, GT, LTE, or GTE) and two children (left and right operands).
        """
        
        left_expr = self._extract_expression(node.child(0))
        operator = node.child(1).type
        right_expr = self._extract_expression(node.child(2))

        op_map = {
            "=": ExpressionNodeType.EQ,
            "<>": ExpressionNodeType.NEQ,
            "<": ExpressionNodeType.LT,
            ">": ExpressionNodeType.GT,
            "<=": ExpressionNodeType.LTE,
            ">=": ExpressionNodeType.GTE,
        }

        op_type = op_map[operator]
        return CypherExpression(
            node_type=op_type,
            children=[left_expr, right_expr]
        )
    
    def _extract_predicate_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract string/list/null predicate expressions.
        
        Parses predicate expressions for string operations (STARTS WITH, ENDS WITH,
        CONTAINS), list membership (IN), and null checking (IS NULL, IS NOT NULL).
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
            string_list_null_predicate_expression: ($) => prec(6, 
                seq(
                    $.expression, 
                    choice(
                        $.list_predicate_expression, 
                        $.string_predicate_expression, 
                        $.null_predicate_expression
                    )
                )
            ),
            list_predicate_expression: ($) => prec.left(6, seq(word('in'), $.expression)),
            string_predicate_expression: ($) => prec.left(6, 
                seq(
                    choice(
                        seq(word('starts'), word('with')), 
                        seq(word('ends'), word('with')), 
                        seq(word('contains'))
                    ), 
                    $.expression
                )
            ),
            null_predicate_expression: () => prec(6, 
                seq(
                    word('is'), 
                    optional(word('not')), 
                    word('null')
                )
            ),
        ```

        The returned tree structure is:
        ```
            predicate_type
                base_expr
                predicate_expr (if applicable)
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a predicate expression.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with the appropriate predicate type:
            - IN: base_expr IN predicate_expr
            - STARTS_WITH/ENDS_WITH/CONTAINS: string predicate with two operands
            - IS_NULL/IS_NOT_NULL: null check with one operand
        """
        
        base_expr = self._extract_expression(node.child(0))
        predicate_node = node.child(1)
        if predicate_node.type == "list_predicate_expression":
            predicate_type = ExpressionNodeType.IN
            predicate_expr = self._extract_expression(predicate_node.child(1))
            return CypherExpression(
                node_type=predicate_type,
                children=[base_expr, predicate_expr]
            )
        elif predicate_node.type == "string_predicate_expression":
            text = self._get_node_text(predicate_node).lower()
            if "starts" in text:
                predicate_type = ExpressionNodeType.STARTS_WITH
            elif "ends" in text:
                predicate_type = ExpressionNodeType.ENDS_WITH
            elif "contains" in text:
                predicate_type = ExpressionNodeType.CONTAINS
            predicate_expr = self._extract_expression(predicate_node.child(1))
            return CypherExpression(
                node_type=predicate_type,
                children=[base_expr, predicate_expr]
            )
        else:  # predicate_node.type == "null_predicate_expression":
            text = self._get_node_text(predicate_node).lower()
            if "not" in text:
                predicate_type = ExpressionNodeType.IS_NOT_NULL
            else:
                predicate_type = ExpressionNodeType.IS_NULL
            return CypherExpression(
                node_type=predicate_type,
                children=[base_expr]
            )
    
    def _extract_arithmetic_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract arithmetic expressions.
        
        Parses additive (+, -) and multiplicative (*, /, %) arithmetic operators.
        Maps operator symbols to their corresponding ExpressionNodeType values.
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
            additive_expression: ($) => prec.left(7, 
                seq(
                    $.expression, 
                    choice('-', '+'), 
                    $.expression
                )
            ),
            multiplicative_expression: ($) => prec.left(8, 
                seq(
                    $.expression, 
                    choice('*', '/', '%'), 
                    $.expression
                )
            ),
        ```

        The returned tree structure is:
        ```
            op_type
                left_expr
                right_expr
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing an arithmetic expression.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with the appropriate arithmetic operator type
            (ADD, SUB, MUL, DIV, or MOD) and two children (left and right operands).
        """
        
        left_expr = self._extract_expression(node.child(0))
        operator = node.child(1).type
        right_expr = self._extract_expression(node.child(2))

        op_map = {
            "+": ExpressionNodeType.ADD,
            "-": ExpressionNodeType.SUB,
            "*": ExpressionNodeType.MUL,
            "/": ExpressionNodeType.DIV,
            "%": ExpressionNodeType.MOD,
        }

        op_type = op_map[operator]
        return CypherExpression(
            node_type=op_type,
            children=[left_expr, right_expr]
        )
    
    def _extract_unary_arithmetic_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract unary arithmetic expressions.
        
        Parses unary plus (+) and minus (-) operators, which negate or affirm
        numeric values.
        
        Tree-Sitter JavaScript Grammar Rules:
        ```
        unary_expression: ($) => prec(10, seq(choice('+', '-'), $.expression)),
        ```

        The returned tree structure is:
        ```
            op_type
                operand
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a unary arithmetic expression.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type UNARY_PLUS or UNARY_MINUS and one
            child (the operand).
        """
        
        operator = node.child(0).type
        operand = self._extract_expression(node.child(1))

        if operator == "+":
            op_type = ExpressionNodeType.UNARY_PLUS
        else:
            op_type = ExpressionNodeType.UNARY_MINUS

        return CypherExpression(
            node_type=op_type,
            children=[operand]
        )
    
    def _extract_list_operator_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract list indexing and slicing expressions.
        
        Parses list access operations including single element indexing and
        range-based slicing.
        
        Tree-Sitter JavaScript Grammar:
        ```
            list_operator_expression: ($) => prec(11, 
                seq(
                    $.expression, 
                    choice(
                        seq('[', $.expression, ']'),
                        seq('[', optional($.expression), '..', optional($.expression), ']')
                    )
                )
            ),
        ```
    
        The returned tree structure is:
        ```
            op_type
                base_expr
                index_expr / slice_start (if applicable)
                slice_end (if applicable)
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a list operator expression.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type:
            - LIST_INDEX: for single element access (base[index])
            - LIST_SLICE: for range access (base[start..end])
        
        Notes
        -----
        For slicing, start and/or end may be omitted (e.g., [..5], [3..], [..]).
        """
        
        base_expr = self._extract_expression(node.child(0))

        if len(node.children) > 4:
            # Slicing
            slice_start = self._extract_expression(node.child(2))
            slice_end = self._extract_expression(node.child(4))
            children = [base_expr]
            if slice_start:
                children.append(slice_start)
            if slice_end:
                children.append(slice_end)
            return CypherExpression(
                node_type=ExpressionNodeType.LIST_SLICE,
                children=children
            )
        else:
            # Indexing
            index_node = node.child(2)
            index_expr = self._extract_expression(index_node)
            return CypherExpression(
                node_type=ExpressionNodeType.LIST_INDEX,
                children=[base_expr, index_expr]
            )
    
    def _extract_property_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract property access expressions (e.g., a.name).
        
        Parses property lookups and label checks on expressions. Properties are
        chained together to form a property access path. Can also include label
        checks in addition to properties.
        
        Tree-Sitter JavaScript Grammar:
        ```
            property_or_labels_expression: ($) => prec.right(11, 
                seq(
                    $.expression,
                    choice(
                        seq(repeat1($.property_lookup), optional($.node_labels)),
                        seq(repeat($.property_lookup), $.node_labels)
                    )
                )
            ),
            property_lookup: ($) => seq('.', $.property_key_name),
            property_key_name: ($) => $.schema_name,
            node_labels: ($) => prec.right(repeat1($.node_label)),
            node_label: ($) => seq(':', $.label_name),
            label_name: ($) => $.schema_name,
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a property or labels expression.

        Returns
        -------
        Optional[CypherExpression]
            The base expression with PROPERTY children chained together, and
            optional LABEL children. For example, "a.name" becomes:
            ```
            VARIABLE: a
                PROPERTY: name
            ```
            And "a:Person" becomes:
            ```
            VARIABLE: a
                LABEL: Person
            ```
        """

        base_expr = None
        properties: list[str] = []
        labels: set[str] = set()
        
        for child in node.children:
            if child.type == "expression":
                base_expr = self._extract_expression(child)
            elif child.type == "property_lookup":
                prop_key_name_node = child.child(1)
                prop_name = self._get_node_text(prop_key_name_node.child(0))
                properties.append(prop_name)
            elif child.type == "node_labels":
                for label_child in child.children:
                    label_name_node = label_child.child(1)
                    schema_name_node = label_name_node.child(0)
                    label_name = self._get_node_text(schema_name_node)
                    if label_name:
                        labels.add(label_name)
        
        current_expr = base_expr
        for prop in properties:
            new_expr = CypherExpression(
                node_type=ExpressionNodeType.PROPERTY,
                value=prop,
            )
            current_expr.children.append(new_expr)
            current_expr = new_expr
        
        current_expr.children.extend([
            CypherExpression(
                node_type=ExpressionNodeType.LABEL,
                value=label,
            ) for label in labels
        ])
        
        return base_expr
    
    def _extract_atom_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract atomic expressions (literals, variables, functions, etc.).
        
        Tree-Sitter JavaScript Grammar:
        ```
            atom: ($) => choice(
                $.literal,
                $.parameter, 
                $.case_expression, 
                seq(word('count'), /\(\s*\*\s*\)/), 
                $.list_comprehension, 
                $.pattern_comprehension, 
                $.quantifier, 
                $.pattern_predicate, 
                $.parenthesized_expression, 
                $.function_invocation, 
                $.existential_subquery, 
                prec.left($.variable)
            ),
            parameter: ($) => seq('$', choice($.symbolic_name, $.decimal_integer)),
            pattern_predicate: ($) => $.relationships_pattern,
            parenthesized_expression: ($) => choice(
                $.variable_in_parens, 
                seq('(', $.expression, ')'
                )
            ),
            variable_in_parens: ($) => seq('(', $.variable, ')'),
        ```
        """
        child = node.child(0)
        child_type = child.type
        
        # Literals
        if child_type == "literal":
            return self._extract_literal(child)
        
        # Variables
        elif child_type == "variable":
            var_name = self._get_node_text(child)
            return CypherExpression(
                node_type=ExpressionNodeType.VARIABLE,
                value=var_name
            )
        
        # Parameters
        elif child_type == "parameter":
            param_text = self._get_node_text(child)
            return CypherExpression(
                node_type=ExpressionNodeType.PARAMETER,
                value=param_text
            )
        
        # Function invocations
        elif child_type == "function_invocation":
            return self._extract_function_invocation(child)
        
        # Case expressions
        elif child_type == "case_expression":
            return self._extract_case_expression(child)
        
        # Comprehensions
        elif child_type == "list_comprehension":
            return self._extract_list_comprehension(child)

        elif child_type == "pattern_comprehension":
            return self._extract_pattern_comprehension(child)
        
        # Quantifiers
        elif child_type == "quantifier":
            return self._extract_quantifier(child)
    
        # Parenthesized expression - unwrap
        elif child_type == "parenthesized_expression":
            par_expr_child = child.child(0)
            if par_expr_child.type == "variable_in_parens":
                var_node = par_expr_child.child(1)
                var_name = self._get_node_text(var_node)
                return CypherExpression(
                    node_type=ExpressionNodeType.VARIABLE,
                    value=var_name
                )
            else:
                expr_node = child.child(1)
                return self._extract_expression(expr_node)
        
        # Pattern predicates
        # TODO: Review this function DIFFICULT
        elif child_type == "pattern_predicate":
            return CypherExpression(
                node_type=ExpressionNodeType.PATTERN_PREDICATE,
                metadata={"pattern": self._get_node_text(child)}
            )
        
        # Existential subqueries
        # TODO: Review this function DIFFICULT
        elif child_type == "existential_subquery":
            return CypherExpression(
                node_type=ExpressionNodeType.EXISTENTIAL_SUBQUERY,
                metadata={"query": self._get_node_text(child)}
            )
    
    def _extract_literal(self, node: Node) -> Optional[CypherExpression]:
        """Extract literal values.
        
        Parses all types of literal values including numbers, strings, booleans,
        null, maps, and lists. Delegates to specialized extraction methods for
        complex literals.
        
        Tree-Sitter JavaScript Grammar:
        ```
            literal: ($) => choice(
                $.number_literal, 
                $.string_literal, 
                $.boolean_literal, 
                $.null_literal, 
                $.map_literal, 
                $.list_literal
            ),
            number_literal: ($) => choice($.double_literal, $.integer_literal),
            integer_literal: ($) => choice($.hex_integer, $.octal_integer, $.decimal_integer),
            hex_integer: () => /0x[0-9a-f]+/i,
            decimal_integer: () => choice('0', /[1-9][0-9]*/),
            octal_integer: () => /0o[0-7]+/,
            double_literal: ($) => choice($.exponent_decimal_real, $.regular_decimal_real),
            exponent_decimal_real: () => token(seq(choice(/[0-9]+/, seq(/[0-9]+/, '.', /[0-9]+/), seq('.', /[0-9]+/)), word('e'), optional('-'), /[0-9]+/)),
            regular_decimal_real: () => /[0-9]*\.[0-9]+/,
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a literal.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type:
            - LITERAL: for simple literals (numbers, strings, booleans, null)
            - LIST_LITERAL: for list literals (extracted via _extract_list_literal)
            - MAP_LITERAL: for map literals (extracted via _extract_map_literal)
        """
        child = node.child(0)
        child_type = child.type
        
        if child_type == "list_literal":
            return self._extract_list_literal(child)
        elif child_type == "map_literal":
            return self._extract_map_literal(child)
        else:
            value = self._get_node_text(child)
            return CypherExpression(
                node_type=ExpressionNodeType.LITERAL,
                value=value
            )
    
    def _extract_list_literal(self, node: Node) -> CypherExpression:
        """Extract list literal expressions.
        
        Parses list literals which contain zero or more comma-separated expressions.
        
        Tree-Sitter JavaScript Grammar:
        ```
            list_literal: ($) => seq(
                '[', 
                optional(
                    seq(
                        $.expression,
                        repeat(seq(',', $.expression))
                    )
                ),
                ']'
            ),
        ```

        The returned tree structure is:
        ```
            LIST_LITERAL
                expr1
                expr2
                ...
                exprN
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a list_literal.

        Returns
        -------
        CypherExpression
            A CypherExpression with type LIST_LITERAL and children containing
            the expressions in the list.
        
        Examples
        --------
        For "[1, 2, 3]" the tree contains three LITERAL children.
        For "[]" the tree has no children.
        """
        elements = []
        for child in node.children:
            if child.type == "expression":
                elem = self._extract_expression(child)
                if elem:
                    elements.append(elem)
        
        return CypherExpression(
            node_type=ExpressionNodeType.LIST_LITERAL,
            children=elements
        )
    
    def _extract_map_literal(self, node: Node) -> CypherExpression:
        """Extract map literal expressions.
        
        Parses map literals which contain zero or more key-value pairs. Each
        key-value pair is represented as a MAP_ENTRY node.
        
        Tree-Sitter JavaScript Grammar:
        ```
            map_literal: ($) => seq(
                '{',
                optional(
                    seq(
                        $.property_key_name,
                        ':',
                        $.expression,
                        repeat(seq(',', $.property_key_name, ':', $.expression))
                    )
                ),
                '}'
            ),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a map_literal.

        Returns
        -------
        CypherExpression
            A CypherExpression with type MAP_LITERAL and children containing
            MAP_ENTRY nodes, each with the key as value and the expression
            as a child.
        
        Examples
        --------
        For "{name: 'Alice', age: 30}" the tree contains two MAP_ENTRY children:
        - MAP_ENTRY (value='name', children=[LITERAL: 'Alice'])
        - MAP_ENTRY (value='age', children=[LITERAL: 30])
        """
        
        properties_keys: list[str] = []
        expressions: list[CypherExpression] = []

        for child in node.children:
            if child.type == "property_key_name":
                key_name = self._get_node_text(child.child(0))
                properties_keys.append(key_name)
            elif child.type == "expression":
                expr = self._extract_expression(child)
                if expr:
                    expressions.append(expr)
        
        map_literal_expr = CypherExpression(
            node_type=ExpressionNodeType.MAP_LITERAL,
        )

        for key, expr in zip(properties_keys, expressions):
            pair_expr = CypherExpression(
                node_type=ExpressionNodeType.MAP_ENTRY,
                value=key,
                children=[expr]
            )
            map_literal_expr.children.append(pair_expr)
        
        return map_literal_expr
    
    def _extract_function_invocation(self, node: Node) -> Optional[CypherExpression]:
        """Extract function invocation expressions.
        
        Parses function calls with optional DISTINCT modifier and zero or more
        argument expressions.
        
        Tree-Sitter JavaScript Grammar:
        ```
            function_invocation: ($) => seq(
                $.function_name, 
                '(', 
                optional(word('distinct')), 
                optional(
                    seq(
                        $.expression,
                        repeat(seq(',', $.expression))
                    )
                ),
                ')'
            ),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a function_invocation.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type FUNCTION, children containing the
            argument expressions, and metadata:
            - 'function_name': the name of the function
            - 'distinct': True if DISTINCT modifier present, False otherwise
        
        Examples
        --------
        For "count(DISTINCT n.name)":
        - node_type: FUNCTION
        - metadata: {'function_name': 'count', 'distinct': True}
        - children: [property expression for n.name]
        """
        args = []
        distinct = False
        
        for child in node.children:
            if child.type == "function_name":
                func_name = self._get_node_text(child)
            elif child.type == "expression":
                arg = self._extract_expression(child)
                if arg:
                    args.append(arg)
            elif child.type == "distinct":
                distinct = True

        return CypherExpression(
            node_type=ExpressionNodeType.FUNCTION,
            children=args,
            metadata={"distinct": distinct}
        )
    
    def _extract_case_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract CASE expressions.
        
        Parses CASE expressions which can have a base expression to evaluate
        or be condition-based. Includes WHEN/THEN alternatives and optional ELSE.
        
        Tree-Sitter JavaScript Grammar:
        ```
            case_expression: ($) => seq(
                choice(
                    seq(
                        word('case'), 
                        repeat($.case_alternatives)
                    ), 
                    seq(
                        word('case'), 
                        $.expression, 
                        repeat($.case_alternatives)
                    )
                ),
                optional(
                    seq(word('else'), $.expression)
                ), 
                word('end')
            ),
            case_alternatives: ($) => seq(
                word('when'), 
                $.expression, 
                word('then'), 
                $.expression
            ),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a case_expression.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type CASE containing:
            - Optional base expression (for value-based CASE)
            - CASE_ALTERNATIVE children (WHEN/THEN pairs)
            - Optional ELSE_CASE child (for ELSE clause)
        
        Examples
        --------
        For "CASE n.age WHEN 30 THEN 'thirty' ELSE 'other' END":
        - First child: base expression (n.age)
        - Second child: CASE_ALTERNATIVE (WHEN 30 THEN 'thirty')
        - Third child: ELSE_CASE ('other')
        """
        case_expr = CypherExpression(
            node_type=ExpressionNodeType.CASE,
        )
        case = False

        for child in node.children:
            if child.type == "case":
                case = True
            elif child.type == "expression":
                expr = self._extract_expression(child)
                if case:
                    case_expr.children.append(expr)
                    case = False
                else: # child.type == "else":
                    case_expr.children.append(
                        CypherExpression(
                            node_type=ExpressionNodeType.ELSE_CASE,
                            children=[expr]
                        )
                    )
            # elif child.type == "else":
            #     case = False
            elif child.type == "case_alternatives":
                when_expr = self._extract_expression(child.child(1))
                then_expr = self._extract_expression(child.child(3))
                case_expr.children.append(
                    CypherExpression(
                        node_type=ExpressionNodeType.CASE_ALTERNATIVE,
                        children=[when_expr, then_expr]
                    )
                )
        
    
    def _extract_list_comprehension(self, node: Node) -> Optional[CypherExpression]:
        """Extract list comprehension expressions.
        
        Parses list comprehensions which filter and optionally transform elements
        from a collection.
        
        Tree-Sitter JavaScript Grammar:
        ```
            list_comprehension: ($) => seq('[', 
                $.filter_expression, 
                optional(seq('|', $.expression)), 
                ']'
            ),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a list_comprehension.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type LIST_COMPREHENSION containing:
            - First child: FILTER_EXPRESSION (variable IN collection with optional WHERE)
            - Second child (optional): transformation expression
        
        Examples
        --------
        For "[x IN [1, 2, 3] WHERE x > 1 | x * 2]":
        - First child: FILTER_EXPRESSION (x IN [1, 2, 3] WHERE x > 1)
        - Second child: transformation (x * 2)
        """
        filter_expr = self._extract_filter_expression(node.child(1))
        list_comp_expr = CypherExpression(
            node_type=ExpressionNodeType.LIST_COMPREHENSION,
            children=[filter_expr]
        )
        if node.child_count > 3:
            expr_node = node.child(3)
            expr = self._extract_expression(expr_node)
            list_comp_expr.children.append(expr)
        
        return list_comp_expr
    
    # TODO: Review this function DIFFICULT
    def _extract_pattern_comprehension(self, node: Node) -> Optional[CypherExpression]:
        """Extract pattern comprehension expressions.
        
        Parses pattern comprehensions which evaluate an expression for each
        match of a graph pattern. Currently stores the comprehension as text
        metadata rather than fully parsing the pattern.
        
        Tree-Sitter JavaScript Grammar:
        ```
        pattern_comprehension: ($) => prec(11, 
            seq('[', 
                optional(seq($.variable, '=')), 
                $.relationships_pattern, 
                optional(seq(word('where'), $.expression)), 
                '|', $.expression, ']'
            )
        ),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a pattern_comprehension.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type PATTERN_COMPREHENSION containing the
            full comprehension text in metadata.
        
        Examples
        --------
        For "[(a)-->(b) WHERE b.age > 25 | b.name]":
        Currently stores the entire text in metadata rather than parsing components.
        """
        comp_text = self._get_node_text(node)
        return CypherExpression(
            node_type=ExpressionNodeType.PATTERN_COMPREHENSION,
            value="pattern_comprehension",
            metadata={"comprehension": comp_text}
        )
    
    def _extract_filter_expression(self, node: Node) -> Optional[CypherExpression]:
        """Extract filter expression for comprehensions and quantifiers.
        
        Parses filter expressions which specify a variable iterating over a
        collection with an optional WHERE clause for filtering.
        
        Tree-Sitter JavaScript Grammar:
        ```
            filter_expression: ($) => seq($.id_in_coll, optional($.where)),
            id_in_coll: ($) => prec(1, seq($.variable, word('in'), $.expression)),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a filter_expression.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type FILTER_EXPRESSION containing:
            - ID_IN_COLL child (variable and collection expression)
            - Optional WHERE child (filter condition)
        
        Examples
        --------
        For "x IN [1, 2, 3] WHERE x > 1":
        - First child: ID_IN_COLL with VARIABLE 'x' and LIST_LITERAL [1,2,3]
        - Second child: WHERE expression (x > 1)
        """

        id_in_coll_node = node.child(0)
        id_in_coll_variable = self._get_node_text(id_in_coll_node.child(0))
        id_in_coll_expr = self._extract_expression(id_in_coll_node.child(2))
        id_in_coll_expr = CypherExpression(
            node_type=ExpressionNodeType.ID_IN_COLL,
            children=[
                CypherExpression(
                    node_type=ExpressionNodeType.VARIABLE,
                    value=id_in_coll_variable
                ),
                id_in_coll_expr
            ]
        )

        filter_expr = CypherExpression(
            node_type=ExpressionNodeType.FILTER_EXPRESSION,
            children=[id_in_coll_expr]
        )

        if node.child_count > 1:
            where_expr = self._extract_expression(node.child(1))
            filter_expr.children.append(where_expr)
        
        return filter_expr

    def _extract_quantifier(self, node: Node) -> Optional[CypherExpression]:
        """Extract quantifier expressions (all, any, none, single).
        
        Parses quantifier functions that test whether a predicate holds for
        all, any, none, or exactly one element in a collection.
        
        Tree-Sitter JavaScript Grammar:
        ```
        quantifier: ($) => prec(12, 
            choice(
                seq(
                    word('all'), 
                    '(', 
                    $.filter_expression, 
                    ')'
                ), 
                seq(
                    word('any'), 
                    '(', 
                    $.filter_expression, 
                    ')'
                ), 
                seq(
                    word('none'), 
                    '(', 
                    $.filter_expression, 
                    ')'
                ), 
                seq(
                    word('single'), 
                    '(', 
                    $.filter_expression, 
                    ')'
                )
            )
        ),
        ```

        Parameters
        ----------
        node : Node
            The tree-sitter Node representing a quantifier.

        Returns
        -------
        Optional[CypherExpression]
            A CypherExpression with type ALL, ANY, NONE, or SINGLE containing
            a FILTER_EXPRESSION child.
        
        Examples
        --------
        For "all(x IN [1, 2, 3] WHERE x > 0)":
        - node_type: ALL
        - child: FILTER_EXPRESSION (x IN [1,2,3] WHERE x > 0)
        """
        quantifier_type = None
        text = self._get_node_text(node).lower()
        
        if "all" in text:
            quantifier_type = ExpressionNodeType.ALL
        elif "any" in text:
            quantifier_type = ExpressionNodeType.ANY
        elif "none" in text:
            quantifier_type = ExpressionNodeType.NONE
        elif "single" in text:
            quantifier_type = ExpressionNodeType.SINGLE
        
        filter_node = node.child(2)
        filter_expr = self._extract_filter_expression(filter_node)

        return CypherExpression(
            node_type=quantifier_type,
            children=[filter_expr]
        )
