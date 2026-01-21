from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, List, Literal, Optional, Tuple, Union
from langchain_neo4j import Neo4jGraph
from langchain_core.embeddings import Embeddings
from collections import defaultdict

import numpy as np

class SchemaIndex:

    __slots__ = (
        "node_to_prop",
        "rel_to_prop",
        "rel_to_domains_ranges",
        "prop_to_nodes",
        "prop_to_rels",
        "neo4j",
        "embedding_model",
    )

    @dataclass
    class Property():
        name: str
        type: str

    def __init__(
        self,
        neo4j: Neo4jGraph,
        embedding_model: Embeddings,
    ) -> None:
        self.neo4j = neo4j
        self.embedding_model = embedding_model
        self._build_indexes()
    
    def _build_indexes(self) -> None:
        """Build all schema index dictionaries from Neo4jGraph.structured_schema."""
        schema = self.neo4j.get_structured_schema
        
        # Initialize dictionaries
        self.node_to_prop: dict[str, list[SchemaIndex.Property]] = {}
        self.rel_to_prop: dict[str, list[SchemaIndex.Property]] = {}
        self.rel_to_domains_ranges: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.prop_to_nodes = defaultdict(list)
        self.prop_to_rels = defaultdict(list)
        
        # Build node_to_prop: node label -> set of property names
        for node_label, property_dicts in schema["node_props"].items():
            self.node_to_prop[node_label] = [
                SchemaIndex.Property(name=prop_dict["property"], type=prop_dict["type"])
                for prop_dict in property_dicts
            ]
            for property_dict in property_dicts:
                # Build reverse index: prop_to_nodes
                prop_name = property_dict["property"]
                self.prop_to_nodes[prop_name].append(node_label)
        
        # Build rel_to_prop: relationship type -> set of property names
        for rel_type, property_dicts in schema["rel_props"].items():
            self.rel_to_prop[rel_type] = [
                SchemaIndex.Property(name=prop_dict["property"], type=prop_dict["type"])
                for prop_dict in property_dicts
            ]
            for property_dict in property_dicts:
                # Build reverse index: prop_to_rels
                prop_name = property_dict["property"]
                self.prop_to_rels[prop_name].append(rel_type)
        
        
        for rel_dict in schema["relationships"]:
            rel_type = rel_dict["type"]
            start_label = rel_dict["start"]
            end_label = rel_dict["end"]
            self.rel_to_domains_ranges[rel_type].append((start_label, end_label))
        
        # Convert defaultdict to regular dict
        self.rel_to_domains_ranges = dict(self.rel_to_domains_ranges)
        self.prop_to_nodes = dict(self.prop_to_nodes)
        self.prop_to_rels = dict(self.prop_to_rels)

    def to_dict(self) -> dict:
        """Return all indexes as a dictionary."""
        return {
            "node_to_prop": {
                node: [asdict(prop) for prop in props]  # Convert Property objects to dicts
                for node, props in self.node_to_prop.items()
            },
            "rel_to_prop": {
                rel: [asdict(prop) for prop in props]  # Convert Property objects to dicts
                for rel, props in self.rel_to_prop.items()
            },
            "rel_to_domains_ranges": self.rel_to_domains_ranges,
            "prop_to_nodes": self.prop_to_nodes,
            "prop_to_rels": self.prop_to_rels,
        }

    def similarity_sort(
        self,
        items: List[Any],
        sort_key: Callable[[Any], str],
        similar_to: str,
        top_k: Optional[int] = None
    ) -> List[Tuple[str, float]]:

        if top_k is None:
            top_k = len(items)

        query_embedding = self.embedding_model.embed_query(similar_to)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        items_keys = [sort_key(item) for item in items]

        item_embeddings = self.embedding_model.embed_documents(items_keys)
        item_embeddings = item_embeddings / np.linalg.norm(item_embeddings, axis=1, keepdims=True)

        scores = np.dot(item_embeddings, query_embedding)
        sorted_indices = np.argsort(scores)[-top_k:][::-1].tolist()

        # return sorted indices with scores
        return [
            (items[idx], scores[idx].item())
            for idx in sorted_indices
        ]

    def get_properties_from(
        self,
        components: List[Literal["nodes", "relationships"]],
        of_types: List[str],
        similar_to: Optional[List[str]] = None,
        top_k: Union[int, List[int]] = 10
    ) -> Union[
            List[
                Tuple[
                    str, 
                    List[SchemaIndex.Property]
                ]
            ],
            List[
                Tuple[
                    str, 
                    List[Tuple[
                        SchemaIndex.Property,
                        float
                    ]]
                ]
            ]
        ]:
        results = []

        if any(c not in {"nodes", "relationships"} for c in components):
            raise ValueError("components must be either 'nodes' or 'relationships'")

        if len(of_types) != len(components):
            raise ValueError("Length of 'of_types' parameter must match length of 'components' parameter")

        for i, type_ in enumerate(of_types):
            if components[i] == "relationships":
                properties = self.rel_to_prop.get(type_, [])
            else:
                properties = self.node_to_prop.get(type_, [])
            results.append((type_, properties))
        
        if similar_to:
            if isinstance(top_k, int):
                top_k = [top_k] * len(of_types)
            if len(similar_to) != len(of_types):
                raise ValueError("Length of 'similar_to' parameter must match length of 'of_types' parameter")
            if len(similar_to) != len(top_k):
                raise ValueError("Length of 'similar_to' parameter must match length of 'top_k' parameter") 

            for i, (type_, properties) in enumerate(results):
                if properties:
                    top_properties = self.similarity_sort(
                        items=properties,
                        sort_key=lambda x: x.name,
                        similar_to=similar_to[i],
                        top_k=top_k[i]
                    )
                    results[i] = (type_, top_properties)

        return results

    def get_components_with_property(
        self,
        keys: List[str],
        components: List[Literal["nodes", "relationships", "both"]],
        similar_to: Optional[List[str]] = None,
        top_k: Union[int, List[int]] = 10
    ) -> Union[
            List[
                Tuple[
                    str,
                    List[str]
                ]
            ],
            List[
                Tuple[
                    str,
                    List[Tuple[str, float]]
                ]
            ]
        ]:
        results = []

        if any(c not in {"nodes", "relationships", "both"} for c in components):
            raise ValueError("components must be either 'nodes', 'relationships' or 'both'")
        
        if len(keys) != len(components):
            raise ValueError("Length of 'keys' parameter must match length of 'components' parameter")

        for i, key in enumerate(keys):
            related_components = []
            if components[i] == "relationships" or components[i] == "both":
                related_components.extend([
                    ("Relationship", rel)
                    for rel in self.prop_to_rels.get(key, [])
                ])
            if components[i] == "nodes" or components[i] == "both":
                related_components.extend([
                    ("Node", node)
                    for node in self.prop_to_nodes.get(key, [])
                ])
            results.append((key, related_components))

        if similar_to:
            if isinstance(top_k, int):
                top_k = [top_k] * len(keys)
            if len(keys) != len(top_k):
                raise ValueError("Length of 'top_k' parameter must match length of 'keys' parameter")
            if len(similar_to) != len(keys):
                raise ValueError("Length of 'similar_to' parameter must match length of 'keys' parameter")

            for i, (key, components_list) in enumerate(results):
                if components_list:
                    top_components = self.similarity_sort(
                        items=components_list,
                        sort_key=lambda x: x[1],
                        similar_to=similar_to[i],
                        top_k=top_k[i]
                    )
                    results[i] = (key, top_components)

        return results

    def get_domains_ranges_of(
        self,
        relationships: List[str],
        similar_to: Optional[List[str]] = None,
        order_by: List[Literal["domains", "ranges"]] = None,
        top_k: Union[int, List[int]] = 10
    ) -> Union[
            List[
                Tuple[
                    str,
                    List[Tuple[str, str]]
                ]
            ],
            List[
                Tuple[
                    str,
                    List[Tuple[
                        Tuple[str, str], 
                        float
                    ]]
                ]
            ]
        ]:
        results = []
        for rel in relationships:
            domains_ranges = self.rel_to_domains_ranges.get(rel, [])
            results.append((rel, domains_ranges))

        if similar_to:
            if isinstance(top_k, int):
                top_k = [top_k] * len(relationships)
            if order_by is None:
                order_by = ["domains"] * len(relationships)
            if len(similar_to) != len(relationships):
                raise ValueError("Length of 'similar_to' parameter must match length of 'relationships' parameter")
            if len(similar_to) != len(top_k):
                raise ValueError("Length of 'similar_to' parameter must match length of 'top_k' parameter") 
            if len(similar_to) != len(order_by):
                raise ValueError("Length of 'similar_to' parameter must match length of 'order_by' parameter")

            for i, (rel, domains_ranges) in enumerate(results):
                if domains_ranges:
                    if order_by[i] == "domains":
                        sort_key = lambda x: x[0]
                    else:
                        sort_key = lambda x: x[1]
                    
                    top_domains_ranges = self.similarity_sort(
                        items=domains_ranges,
                        sort_key=sort_key,
                        similar_to=similar_to[i],
                        top_k=top_k[i]
                    )
                    results[i] = (rel, top_domains_ranges)
        return results

    # extract "metadata" subfields such as
    # "index" and "constraint"