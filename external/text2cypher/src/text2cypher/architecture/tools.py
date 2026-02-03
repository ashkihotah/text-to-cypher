import json
from pathlib import Path
from functools import wraps
from typing import List, Literal, Optional, Union

from langchain_neo4j import Neo4jGraph
from langchain_core.tools import tool
import tiktoken

from text2cypher.architecture.indexes import SchemaIndex
from text2cypher.architecture.vector_stores import FAISSIndex
from text2cypher.config import PROJECT_ROOT

def append_md_to_docstring(md_file: str):
    """Decorator to load docstring from markdown file."""
    def decorator(func):
        path = PROJECT_ROOT / md_file

        with open(path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        if func.__doc__:
            func.__doc__ += "\n" + md_content
        else:
            func.__doc__ = md_content
        return func
    return decorator

class RetrievalToolKit:
    __slots__ = (
        "tools",
        "neo4j",
        "schema_index",
        "schema_vector_store",
        "tokenizer",
        "token_limit",
    )

    def __init__(
        self,
        neo4j: Neo4jGraph,
        schema_index: SchemaIndex, 
        schema_vector_store: FAISSIndex, 
        token_limit: int = 4000
    ):
        self.init_runtime(
            neo4j=neo4j,
            schema_index=schema_index,
            schema_vector_store=schema_vector_store,
        )
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.token_limit = token_limit

        @tool
        # @append_md_to_docstring('rsc/prompts/schema_retrieval/execute_cypher_query_examples.md')
        def execute_cypher_query(cypher: str) -> List[dict]:
            """Execute arbitrary Cypher queries against the Neo4j database.

            This tool allows you to run custom Cypher queries to explore the database,
            verify assumptions, or retrieve specific information that is not easily
            accessible through other tools.

            Parameters
            ----------
            cypher : str
                The Cypher query to execute. Should be a valid Cypher query string
                (e.g., 'MATCH (n:Person) RETURN n.name LIMIT 5').

            Returns
            -------
            List[dict]
                The query results as a list of dictionaries, where each dictionary
                represents a row of results with keys corresponding to the RETURN clause.
                Returns an empty list if the query produces no results or if the query fails.
            """ 
            message = ""

            records = self.neo4j.query(cypher)
            if len(records) > 0:
                message += f"Results:\n{records}"
            else:
                message += "The query returned no results!"

            # Truncate strictly based on token count
            tokens = self.tokenizer.encode(message)
            if len(tokens) > self.token_limit:
                truncated_tokens = tokens[:self.token_limit]
                message = self.tokenizer.decode(truncated_tokens)
                message += f"\n\n... (Output truncated because it exceeded {self.token_limit} tokens)"
            
            return message
        
        @tool
        @append_md_to_docstring('rsc/docstrings/search_for_examples.md')
        def search_for(
            components: List[Literal["nodes", "relationships", "properties"]],
            similar_to: str,
            top_k: int = 10
        ) -> str:
            """
            Complex user queries often involve multiple information needs.
            Each information need may be represented using multiple different
            property knowledge graph schema formalisms such as node labels,
            relationship types, and property keys.

            The main goal of this tool is to identify all plausible and 
            possible candidate schema formalisms for each independent 
            information need by finding node labels, relationship types 
            or property keys that are most similar to the given query, 
            ensuring comprehensiveness in coverage and recall.

            Use this tool to quickly discover all possible schema formalisms
            that could represent a specific information need in the knowledge graph,
            prioritizing recall over precision.

            **IMPORTANT**: In order to achieve this in the most efficient way possible, 
            it's crucial to exploit **parallelism** by calling this tool 
            for each independent information need simultaneously.

            It uses Model2Vec embeddings and FAISS indexing to compute
            similarity scores.

            Parameters
            ----------
            components : List[Literal["nodes", "relationships", "properties"]]
                The types of schema components to search for:
                - 'nodes': Search also for node labels
                - 'relationships': Search also for relationship types
                - 'properties': Search also for property keys
            similar_to : str
                The search query text describing the information need you're looking for.
                Can be a natural language description (e.g., 'CEO Person', 'works at company' etc.)
                or any specific keywords related to the schema component (e.g., 'TopActor', 
                'ACTED_IN', "_Top_Actor_", etc.).
            top_k : int, optional
                The number of most similar items to return (default is 10).

            Returns
            -------
            str
                A formatted string listing the top k most similar schema components with
                their relevance scores. Each line contains the component type, name, and
                similarity score.
            
            """
            
            results = []
            message = ""

            for component in components:
                if component not in {"nodes", "relationships", "properties"}:
                    message += (
                        f"Invalid schema_component: {component}. "
                        f"Choose from: 'nodes', 'relationships', 'properties'\n"
                    )
            
            node_index = self.schema_vector_store.node_index
            rel_index = self.schema_vector_store.rel_index
            prop_index = self.schema_vector_store.prop_index
            
            if "nodes" in components:
                temp_results = node_index.similarity_search_with_relevance_scores(
                    similar_to, k=top_k,
                )
                results.extend([
                    (f"Node Label: {item[0].page_content}", item[1]) 
                    for item in temp_results
                ])
            if "relationships" in components:
                temp_results = rel_index.similarity_search_with_relevance_scores(
                    similar_to, k=top_k,
                )
                results.extend([
                    (f"Relationship Type: {item[0].page_content}", item[1]) 
                    for item in temp_results
                ])
            if "properties" in components:
                temp_results = prop_index.similarity_search_with_relevance_scores(
                    similar_to, k=top_k,
                )
                results.extend([
                    (f"Property Key: {item[0].page_content}", item[1]) 
                    for item in temp_results
                ])
            
            results = sorted(results, key=lambda x: x[1], reverse=True)[:top_k]
            
            # format the string results
            message += "\n".join(
                [f"{item[0]} (score: {item[1]:.4f})" for item in results]
            )
            if len(results) < top_k:
                message += "\n"
                message += (
                    f"Note: The number of {", ".join(components)}"
                    " found in the knowledge graph is less than"
                    f" top_k={top_k}. So this result is exhaustive!\n"
                )
            return message

        @tool
        @append_md_to_docstring('rsc/docstrings/get_properties_from_examples.md')
        def get_properties_from(
            components: List[Literal["nodes", "relationships"]],
            of_types: List[str],
            similar_to: Optional[List[str]] = None,
            top_k: Union[int, List[int]] = 10
        ) -> str:
            """Retrieve properties for specific node labels or relationship types.

            This tool queries the schema index to find all properties associated with
            given node labels or relationship types. Optionally, it can rank these
            properties by semantic similarity to specified search queries, helping
            identify the most relevant properties for your information needs.

            **IMPORTANT**: To achieve this efficiently, it's crucial to call this tool
            by **batching** multiple types in a single invocation, rather than
            calling it separately for each type.

            Parameters
            ----------
            components : List[Literal["nodes", "relationships"]]
                For each type in `of_types`, specify whether it is a node label
                or a relationship type.
            of_types : List[str]
                List of node labels or relationship types to get properties from
                (e.g., ['Person', 'Organization'] or ['WORKS_AT', 'MANAGES']).
            similar_to : Optional[List[str]], optional
                List of search queries to rank properties by semantic similarity.
                Must match the length of `of_types` if provided. Each query corresponds
                to the type at the same index (e.g., ['employee info', 'company data']).
            top_k : Union[int, List[int]], optional
                Number of top-ranked properties to return. Can be a single integer
                applied to all types, or a list of integers (one per type). Default is 10.

            Returns
            -------
            str
                A formatted string listing properties for each requested type, with
                similarity scores if `similar_to` is provided.
            """
            type_props = self.schema_index.get_properties_from(
                components=components,
                of_types=of_types,
                similar_to=similar_to,
                top_k=top_k
            )

            if not isinstance(top_k, list):
                top_k = [top_k] * len(of_types)

            message = ""
            for i, (_type, props) in enumerate(type_props):
                if not props:
                    message += f"No properties found for '{_type}'.\n"
                else:
                    message += f"Properties for '{_type}' are:\n"
                    if isinstance(props[0], tuple):  # (property, score)
                        message += "\n".join([
                            f"  - {prop.name}: {prop.type} (score: {score:.4f})"
                            for prop, score in props
                        ])
                        if len(props) < top_k[i]:
                            message += "\n"
                            message += (
                                f"Note: The number of properties found for '{_type}'"
                                f" is less than top_k={top_k[i]}. So this result is exhaustive!\n"
                            )
                    else:
                        message += "\n".join([
                            f"  - {prop.name}: {prop.type}"
                            for prop in props
                        ])
                    message += "\n"
            return message
        
        @tool
        @append_md_to_docstring('rsc/docstrings/get_domains_ranges_of_examples.md')
        def get_domains_ranges_of(
            relationships: List[str],
            similar_to: Optional[List[str]] = None,
            order_by: List[Literal["domains", "ranges"]] = None,
            top_k: Union[int, List[int]] = 10
        ) -> str:
            """Get domain and range node labels for specified relationship types.

            This tool retrieves all valid (source, target) node label pairs for given
            relationship types, showing which node types can be connected by each
            relationship. Optionally ranks these pairs by semantic similarity to help
            identify the most relevant connection patterns.

            **IMPORTANT**: To achieve this efficiently, it's crucial to call this tool
            by **batching** multiple relationship types in a single invocation, rather than
            calling it separately for each relationship type.

            Parameters
            ----------
            relationships : List[str]
                List of relationship types to query (e.g., ['WORKS_AT', 'MANAGES']).
            similar_to : Optional[List[str]], optional
                List of search queries to rank domain-range pairs by semantic similarity.
                Must match the length of `relationships` if provided. Each query
                corresponds to the relationship at the same index.
            order_by : List[Literal["domains", "ranges"]], optional
                For each relationship, whether to rank domain-range pairs
                by similarity of 'domains' or 'ranges'. Must match the length of `relationships`
                if provided. Default is 'domains' for all relationships.
            top_k : Union[int, List[int]], optional
                Number of top-ranked domain-range pairs to return. Can be a single
                integer applied to all relationships, or a list of integers (one per
                relationship). Default is 10.

            Returns
            -------
            str
                A formatted string listing domain-range pairs for each relationship,
                with similarity scores if `similar_to` is provided.
            """
            rel_dom_ranges = self.schema_index.get_domains_ranges_of(
                relationships=relationships,
                similar_to=similar_to,
                order_by=order_by,
                top_k=top_k
            )

            if not isinstance(top_k, list):
                top_k = [top_k] * len(relationships)

            message = ""
            for i, (rel, dom_ranges) in enumerate(rel_dom_ranges):
                if not dom_ranges:
                    message += f"No domain/range found for relationship '{rel}'.\n"
                else:
                    message += f"Relationship: {rel}\n"
                    # format the query result as a message
                    if isinstance(dom_ranges[0][1], float):  # (domain, range, score)
                        message += "\n".join([
                            f"  ({dom_range[0][0]})->({dom_range[0][1]}) (score: {dom_range[1]:.4f})"
                            for dom_range in dom_ranges
                        ])
                        if len(dom_ranges) < top_k[i]:
                            message += "\n"
                            message += (
                                f"Note: The number of domain/range pairs found for relationship '{rel}'"
                                f" is less than top_k={top_k[i]}. So this result is exhaustive!\n"
                            )
                    else:
                        message += "\n".join([
                            f"  ({dom_range[0]})->({dom_range[1]})\n"
                            for dom_range in dom_ranges
                        ])
                    message += "\n"
            return message

        @tool
        @append_md_to_docstring('rsc/docstrings/get_components_with_property_examples.md')
        def get_components_with_property(
            keys: List[str],
            components: List[Literal["nodes", "relationships", "both"]],
            similar_to: Optional[List[str]] = None,
            top_k: Union[int, List[int]] = 10
        ) -> str:
            """
            Often complex user queries with a lot of ambiguousness require identifying
            which node labels or relationship types contain certain property keys.
            If these property keys are highly discriminative and less common, they can help narrow down
            the possible schema components that may represent the user's information need.
            
            This tool performs reverse property lookup, finding all node labels or
            relationship types that contain specified property keys. Optionally
            ranks results by semantic similarity to given queries to identify the most relevant
            schema components among those that have the desired properties.

            **IMPORTANT**: To achieve this efficiently, it's crucial to call this tool
            by **batching** multiple property keys, and optionally queries, 
            in a single invocation, rather than calling it separately for each property key.

            Parameters
            ----------
            keys : List[str]
                List of property keys to search for (e.g., ['name', 'email', 'created_at']).
            components : List[Literal["nodes", "relationships", "both"]]
                For each property key, whether to search for node labels,
                relationship types, or both that contain that property key.
            similar_to : Optional[List[str]], optional
                For each property key, a search query to rank the found components by semantic similarity.
                Helps identify which node labels or relationship types are most relevant to
                your use case.
            top_k : Union[int, List[int]], optional
                Number of top-ranked components to return for each property key.
                Can be a single integer applied to all keys, or a list of integers
                (one per key). Default is 10.

            Returns
            -------
            str
                A formatted string listing node labels or relationship types for each
                property key, with similarity scores if `similar_to` is provided.
                If the provided property key does not exist in the schema, an appropriate
                warning message is returned.
            """
            results = self.schema_index.get_components_with_property(
                keys=keys,
                components=components,
                similar_to=similar_to,
                top_k=top_k
            )

            if not isinstance(top_k, list):
                top_k = [top_k] * len(keys)

            message = ""
            for i, (key, comp_list) in enumerate(results):
                if not comp_list:
                    message += f"No components found with property key '{key}'.\n"
                else:
                    message += f"Components with property key '{key}':\n"
                    if similar_to:  # (component, score)
                        message += "\n".join([
                            f"  - {comp[0][0]}: {comp[0][1]} (score: {comp[1]:.4f})" for comp in comp_list
                        ])
                        if len(comp_list) < top_k[i]:
                            message += "\n"
                            message += (
                                f"Note: The number of components found with property key '{key}'"
                                f" is less than top_k={top_k[i]}."
                                " So this result is exhaustive!\n"
                            )
                    else:
                        message += "\n".join([
                            f"  - {comp[0]}: {comp[1]}" for comp in comp_list
                        ])
                    message += "\n"
            return message

        self.tools = {
            "execute_cypher_query": execute_cypher_query,
            "search_for": search_for,
            "get_properties_from": get_properties_from,
            "get_domains_ranges_of": get_domains_ranges_of,
            "get_components_with_property": get_components_with_property,
        }
    
    def init_runtime(
        self,
        neo4j: Neo4jGraph,
        schema_index: SchemaIndex,
        schema_vector_store: FAISSIndex,
    ) -> None:
        self.neo4j = neo4j
        self.schema_index = schema_index
        self.schema_vector_store = schema_vector_store

    def get_tools_description(self, format: Literal["text", "json"] = "text") -> str:
        """
        Returns a formatted string describing all available tools.
        
        Args:
            format: "text" for human-readable, "json" for JSON schema format
        
        Returns:
            Formatted string with tool descriptions for system prompts
        """
        if format == "json":
            tools_schema = []
            for name, tool_func in self.tools.items():
                # Get the tool's input schema from LangChain tool
                schema = tool_func.get_input_schema().model_json_schema()
                tools_schema.append(schema)
            return json.dumps(tools_schema, indent=2)    
        else:  # text format
            lines = ["## Available Tools\n"]
            for name, tool_func in self.tools.items():
                schema = tool_func.get_input_schema().model_json_schema()
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                
                lines.append(f"### {name}")
                lines.append(f"**Description:** {tool_func.description}\n")
                lines.append("**Parameters:**")
                
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "No description")
                    req_marker = "(required)" if param_name in required else "(optional)"
                    lines.append(f"  - `{param_name}` ({param_type}) {req_marker}: {param_desc}")
                
                lines.append("")  # blank line between tools

            return "\n".join(lines)
