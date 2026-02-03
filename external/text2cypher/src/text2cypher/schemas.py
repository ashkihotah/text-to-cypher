from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class DataTypeSchema(BaseModel):
    """A data type in the graph."""
    name: str = Field(description="The name of the data type")
    examples: List[str] = Field(
        description="Examples of values for this data type",
        # default=None
    )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DataTypeSchema):
            return NotImplemented
        return self.name == other.name

class NodeSchema(BaseModel):
    """A node in the graph."""
    label: str = Field(description="The label associated with the node")
    properties: Dict[str, DataTypeSchema] = Field(
        description="This field maps property names to their data types"
    )
    # examples: List[str] = Field(
    #     description="Example of an instance of this node",
    #     # default=None
    # )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NodeSchema):
            return NotImplemented
        return self.label == other.label
    
    def jaccard(self, other: NodeSchema) -> float:
        if not isinstance(other, NodeSchema):
            return 0.0
        if self.label != other.label:
            return 0.0
        set_self_props = set((prop_name, data_type) for prop_name, data_type in self.properties.items())
        set_other_props = set((prop_name, data_type) for prop_name, data_type in other.properties.items())
        intersection = set_self_props.intersection(set_other_props)
        union = set_self_props.union(set_other_props)
        if not union:
            return 1.0  # Both have no properties, consider them identical
        return len(intersection) / len(union)

class RelationSchema(BaseModel):
    """A relationship in the graph."""
    label: str = Field(description="The label associated with the relationship")
    properties: Dict[str, DataTypeSchema] = Field(
        description="This field maps property names to their data types"
    )
    from_node_label: str = Field(description="The label of the starting node of the relationship")
    to_node_label: str = Field(description="The label of the ending node of the relationship")
    # examples: List[str] = Field(
    #     description="Example of an instance of this relationship",
    #     # default=None
    # )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RelationSchema):
            return NotImplemented
        return (
            self.label == other.label 
            and self.from_node_label == other.from_node_label 
            and self.to_node_label == other.to_node_label
        )
    
    def jaccard(self, other: RelationSchema) -> float:
        if not isinstance(other, RelationSchema):
            return 0.0
        if (
            self.label != other.label 
            or self.from_node_label != other.from_node_label 
            or self.to_node_label != other.to_node_label
        ):
            return 0.0
        set_self_props = set((prop_name, data_type) for prop_name, data_type in self.properties.items())
        set_other_props = set((prop_name, data_type) for prop_name, data_type in other.properties.items())
        intersection = set_self_props.intersection(set_other_props)
        union = set_self_props.union(set_other_props)
        if not union:
            return 1.0  # Both have no properties, consider them identical
        return len(intersection) / len(union)

class KGSchema(BaseModel):
    """Schema of the knowledge graph."""
    nodes: List[NodeSchema] = Field(description="The relevant nodes in the graph")
    relationships: List[RelationSchema] = Field(description="The relevant relationships in the graph")

    def jaccard(self, other: KGSchema) -> float:
        if not isinstance(other, KGSchema):
            return 0.0
        
        total_elements = len(self.nodes) + len(self.relationships)
        if total_elements == 0:
            return 1.0  # Both schemas are empty

        # Jaccard for nodes
        unmatched_other_nodes = set(other.nodes)
        node_similarities = []
        for node in self.nodes:
            max_sim = 0.0
            for other_node in unmatched_other_nodes:
                sim = node.jaccard(other_node)
                if sim > max_sim:
                    max_sim = sim
                    best_match = other_node
            if max_sim > 0.0:
                unmatched_other_nodes.remove(best_match)
            node_similarities.append(max_sim)
        
        # Jaccard for relationships
        unmatched_other_rels = set(other.relationships)
        rel_similarities = []
        for rel in self.relationships:
            max_sim = 0.0
            for other_rel in unmatched_other_rels:
                sim = rel.jaccard(other_rel)
                if sim > max_sim:
                    max_sim = sim
                    best_match = other_rel
            if max_sim > 0.0:
                unmatched_other_rels.remove(best_match)
            rel_similarities.append(max_sim)
        
        overall_jaccard = (sum(node_similarities) + sum(rel_similarities)) / total_elements
        return overall_jaccard
