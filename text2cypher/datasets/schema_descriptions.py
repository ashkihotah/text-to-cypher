
import argparse
import os
from pathlib import Path

from langchain_neo4j import Neo4jGraph
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

import traceback

import json
import tqdm
import yaml

import dotenv

from text2cypher.utils import add_agent_args, get_llm

def init_parser():
    parser = argparse.ArgumentParser(description="Generate synthetic schema descriptions.")

    parser.add_argument("--system-message", type=str,
        help="The system message file path to use for the LLM.",
    )
    parser.add_argument("--user-message", type=str,
        help="The user message file path to use for the LLM.",
    )
    parser.add_argument("--neo4j-username", type=str, default=None,
        help="Neo4j username. If not provided, will be read from .env file.",
    )
    parser.add_argument("--neo4j-password", type=str, default=None,
        help="Neo4j password. If not provided, will be read from .env file.",
    )
    parser.add_argument("--neo4j-uri", type=str, default=None,
        help="Neo4j URI. If not provided, will be read from .env file.",
    )
    parser.add_argument("--db", type=str, default=None,
        help="The Neo4j database name to connect to. If not provided, will be read from .env file.",
    )
    parser.add_argument("--env-path", type=str, default=None,
        help="Path to the .env file containing Neo4j username, password, and URI.",
    )
    parser.add_argument("--output-path", type=str, required=True,
        help="Path to the output schema description file where generated descriptions will be saved.",
    )
    parser.add_argument("--verbose", type=bool, default=True,
        help="Enable verbose logging.",
    )

    add_agent_args(parser)
    return parser

'''
python text2cypher/datasets/schema_descriptions.py
    --system-message rsc/prompts/descriptions_generation/system_prompt.md
    --user-message rsc/prompts/descriptions_generation/user_prompt.md
    --output-path ./data/interim/schema_descriptions.yaml
    --neo4j-username companies
    --neo4j-password companies
    --neo4j-uri bolt+s://demo.neo4jlabs.com:7687
    --db companies

'''

def resume(output_path: Path) -> dict:
    if output_path.exists():
        with open(output_path, "r") as f:
            schema_descriptions = yaml.safe_load(f)
    else:
        schema_descriptions = {
            "nodes": {},
            "relations": {},
        }
    return schema_descriptions

def get_neo4j(args: argparse.Namespace) -> Neo4jGraph:
    db = args.db or os.getenv("NEO4J_DATABASE")
    neo4j_username = args.neo4j_username or os.getenv("NEO4J_USERNAME")
    neo4j_password = args.neo4j_password or os.getenv("NEO4J_PASSWORD")
    neo4j_uri = args.neo4j_uri or os.getenv("NEO4J_URI")

    return Neo4jGraph(
        url=neo4j_uri,
        username=neo4j_username,
        password=neo4j_password,
        database=db,
    )

def get_prompt_template(args: argparse.Namespace) -> ChatPromptTemplate:
    messages = []
    with open(args.system_message, "r") as f:
        system_message = f.read()
        messages.append(("system", system_message))
    with open(args.user_message, "r") as f:
        user_message = f.read()
        messages.append(("human", user_message))
    
    # Create prompt template
    return ChatPromptTemplate.from_messages(messages)

def get_props(props_list: list[dict]) -> str:
    props_str = ""
    for prop in props_list:
        prop_name = prop['property']
        prop_type = prop['type']
        props_str += f"- {prop_name}: {prop_type}\n"
    return props_str

if __name__ == "__main__":
    args = init_parser().parse_args()
    dotenv.load_dotenv(args.env_path)
    args.output_path = Path(args.output_path)

    schema_descriptions = resume(args.output_path)  
    
    neo4j = get_neo4j(args)
    llm = get_llm(args.provider, args.model)
    prompt_template = get_prompt_template(args)
    chain = prompt_template | llm
    
    try:
        schema = neo4j.get_structured_schema

        node_descriptions = schema_descriptions['nodes']
        bar = tqdm.tqdm(schema["node_props"].items(), desc=f"Generating node descriptions for {args.db}")
        for node_label, node_info in bar:
            if node_label not in node_descriptions:
                properties = get_props(node_info) if node_info else "No properties defined"
                response: AIMessage = chain.invoke({
                    "element_type": "node label",
                    "label": node_label,
                    "properties": properties,
                    "context": neo4j.schema,
                })
                node_descriptions[node_label] = response.content
        
        relation_descriptions = schema_descriptions['relations']
        bar = tqdm.tqdm(schema["relationships"], desc=f"Generating relationship descriptions for {args.db}")
        for rel in bar:
            relation_label = rel['type']
            start = rel['start']
            end = rel['end']
            relationship = f"{start}-[{relation_label}]->{end}"
            if relationship not in relation_descriptions:
                relation_info = schema["rel_props"].get(relation_label, None)
                properties = get_props(relation_info) if relation_info else "No properties defined"
                response: AIMessage = chain.invoke({
                    "element_type": "relationship type",
                    "label": relationship,
                    "properties": properties,
                    "context": neo4j.schema,
                })
                relation_descriptions[relationship] = response.content
    except KeyboardInterrupt:
        print("\nGeneration interrupted by user.")
    except Exception as e:
        traceback.print_exc()
    finally:
        print(f"\nSaving progress to {args.output_path}...")
        with open(args.output_path, "w") as f:
            yaml.dump(schema_descriptions, f)