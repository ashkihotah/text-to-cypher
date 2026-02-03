from __future__ import annotations

from dataclasses import asdict, dataclass
import traceback
import json
import re
from typing import Any, List, Optional, override

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage
from langchain_neo4j import Neo4jGraph
from langgraph.graph import StateGraph
from langchain_core.tools import tool
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel, Field, ValidationError

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import MessagesState

from text2cypher.architecture.indexes import SchemaIndex
from text2cypher.architecture.tools import RetrievalToolKit
from text2cypher.schemas import KGSchema

class ToolCallItem(BaseModel):
    """A tool call with name and arguments."""
    name: str = Field(description="The name of the tool to call")
    arguments: dict = Field(description="The arguments to pass to the tool")

class ToolCalls(BaseModel):
    """Response when a tool needs to be called."""
    tool_calls: List[ToolCallItem] = Field(description="The tools to call")

class AgentResponse(BaseModel):
    """The agent's response - either a tool call or a final answer."""
    thought: str = Field(description="Your reasoning process")
    action: ToolCalls = Field(
        description="The tools to call based on your reasoning",
    )

class RetrievalAgent:

    class Result(BaseModel):
        """Response when providing the final answer."""
        
        motivation: str = Field(
            description="If the retrieval process is finished succesfully,"
            " this field explains the reasoning behind the final retrieved schema components."
            "if the retrieval process is not finished succesfully, this field explains why."
        )
        cypher_query: Optional[str] = Field(
            description="The Cypher query that would be used to answer the user's question.",
            default=None
        )
        kg_schema: Optional[KGSchema] = Field(
            description="If the retrieval process is not finished succesfully,"
            "this field contains the relevant retrieved part of the schema of the knowledge graph"
            " to be used to build the final Cypher query. Otherwise, it is None.",
            default=None
        )
    
    class ToolKit(RetrievalToolKit):

        @override
        def __init__(self, neo4j: Neo4jGraph, schema_index: SchemaIndex, schema_vector_store: FAISS):
            super().__init__(neo4j, schema_index, schema_vector_store)

            @tool
            def register_retrieval_result(
                motivation: str,
                cypher_query: Optional[str] = None,
                kg_schema: Optional[KGSchema] = None
            ) -> RetrievalAgent.Result:
                """
                Use this tool ONLY when you have finished the retrieval process
                and are ready to provide the final retrieval result. Do not use any other
                tools after calling this one.

                Args:
                    motivation: Your reasoning behind the final retrieved schema components.
                    cypher_query: The Cypher query that would be used to answer the user's question.
                    kg_schema: The relevant retrieved part of the schema of the knowledge graph
                        to be used to build the final Cypher query.

                Returns:
                    Confirmation that the final answer has been recorded.
                """
                if kg_schema:
                    kg_schema = KGSchema.model_validate(kg_schema) 

                if cypher_query:
                    self.neo4j.query(cypher_query)

                return RetrievalAgent.Result(
                    cypher_query=cypher_query,
                    motivation=motivation,
                    kg_schema=kg_schema
                )
            
            self.tools["register_retrieval_result"] = register_retrieval_result
        
    class State(MessagesState):
        """Extended state that tracks both retrieval and generation results."""
        result: RetrievalAgent.Result

    def __init__(
        self,
        mode: str,
        toolkit: RetrievalAgent.ToolKit,
        llm: BaseChatModel,
        system_prompt: str,
        user_prompt: str,
    ):
        self.regex = re.compile(r'(?P<json>\{[\s\S]*\})')
        # check the fact that in system prompt curly braces must be escaped
        # if they are not used for formatting placeholders such as {tools_definition},
        # {user_query}, {kg_schema}, {cypher_query}, etc.
        self.mode = mode
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.toolkit = toolkit
        self.init_workflow(llm)

    def init_workflow(self, llm: BaseChatModel):
        def tool_native_llm_node(state: RetrievalAgent.State):
            messages = state['messages']
            response = self.llm.invoke(messages)
            return {"messages": [response]}
        
        def structured_output_llm_node(state: RetrievalAgent.State):
            messages = state['messages']
            dict_response: AgentResponse = self.llm.invoke(messages)
            
            if dict_response.get("parsing_error"):
                # try to extract JSON from the raw content using regex
                match = self.regex.search(dict_response['raw'].content)
                if match:
                    json_str = match.group("json")
                    dict_response = json.loads(json_str)
                    response = AgentResponse.model_validate(dict_response)
                else:
                    raise ValueError("Failed to parse LLM response and extract JSON.")
            else:
                response = dict_response["parsed"]

            content = response.thought # dict_response['raw'].content
            tool_calls = []
            if hasattr(response.action, 'tool_calls'):
                tool_calls=[
                    {
                        "id": f"call_{i}_{tc.name}",
                        "name": tc.name,
                        "args": tc.arguments,
                        "type": "tool_call"
                    }
                    for i, tc in enumerate(response.action.tool_calls)
                ]
                # remove tool_calls field from dict_response['raw'].content
                # content = re.sub(r'"tool_calls"\s*:\s*\[.*?\],?', '', content, flags=re.DOTALL)
            else:
                raise ValueError("Invalid action type in AgentResponse")
            
            return {
                "messages": [
                    AIMessage(
                        content=content,
                        tool_calls=tool_calls
                    )
                ]
            }

        def is_retrieval_complete(state: RetrievalAgent.State):
            """Route based on whether final_answer was called."""
            if state["result"] is not None:
                return "__end__"
            return "LLM"

        def tool_node(state: RetrievalAgent.State):
            last_message = state['messages'][-1]
            state_updates = {"messages": []}

            if not last_message.tool_calls:
                # check if the last message is completely empty
                # if this is true remove it to avoid issues
                if not last_message.content.strip():
                    state_updates["messages"].append(
                        RemoveMessage(id=last_message.id)
                    )
                    return state_updates

                state_updates["messages"].append(
                    SystemMessage(
                        content=(
                            "No tool calls were made in the last message. "
                            "Please make sure to call at least one tool."
                        )
                    )
                )
                # return state_updates
            
            for tool_call in last_message.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']

                try:
                    tool_fn = self.toolkit.tools[tool_name]
                    result = tool_fn.invoke(tool_args)
                except ValidationError:
                    schema = json.dumps(tool_fn.get_input_schema().model_json_schema(), indent=2)
                    result = (
                        f"[ERROR]: Tool invocation failed due to invalid arguments format. "
                        f"Remember to follow the following JSON schema for the tool `{tool_name}`:\n"
                        f"```json\n{schema}\n```"
                    )
                except Exception as e:
                    # tb = traceback.format_exc()
                    result = f"[ERROR]: Tool execution failed with the following error:\n{e}"

                if isinstance(result, RetrievalAgent.Result):
                    state_updates["result"] = result
                    state_updates["messages"].append(
                        ToolMessage(
                            content="Retrieval process completed. Result registered.", 
                            tool_call_id=tool_call['id']
                        )
                    )
                else:
                    state_updates["messages"].append(
                        ToolMessage(
                            content=str(result), 
                            tool_call_id=tool_call['id']
                        )
                    )
            
            return state_updates

        workflow = StateGraph(
            state_schema=RetrievalAgent.State,
        )
        if self.mode == "native_tool_call":
            self.llm = llm.bind_tools(list(self.toolkit.tools.values()))
            workflow.add_node("LLM", tool_native_llm_node)
        elif self.mode == "structured_output":
            self.llm = llm.with_structured_output(AgentResponse, include_raw=True)
            workflow.add_node("LLM", structured_output_llm_node)
        else:
            raise ValueError(f"Unknown RetrievalAgent type: {self.mode}")
        workflow.add_node("tools", tool_node)
        
        workflow.set_entry_point("LLM")
        workflow.add_edge("LLM", "tools")
        workflow.add_conditional_edges("tools", is_retrieval_complete)

        self.workflow = workflow.compile(checkpointer=InMemorySaver())

    @dataclass
    class WorkflowInitialState():
        user_query: str
    
    @dataclass
    class DatasetInitialState(WorkflowInitialState):
        kg_schema: str
        cypher_query: str

    def get_init_state(self, init_state: RetrievalAgent.WorkflowInitialState) -> dict:
        system_prompt = self.system_prompt

        if "{user_query}" not in self.user_prompt:
            raise ValueError(
                "User prompt must contain '{user_query}' placeholder "
                "to insert the user's question."
            )
    
        if isinstance(init_state, RetrievalAgent.DatasetInitialState):
            if "{kg_schema}" not in self.user_prompt:
                raise ValueError(
                    "User prompt must contain '{kg_schema}' placeholder "
                    "to insert the knowledge graph schema."
                )
            
            if "{cypher_query}" not in self.user_prompt:
                raise ValueError(
                    "User prompt must contain '{cypher_query}' placeholder "
                    "to insert the ground truth Cypher query."
                )
        
        user_prompt = self.user_prompt.format(**asdict(init_state))

        if self.mode == "structured_output":
            if "{tools_definition}" not in self.system_prompt:
                raise ValueError(
                    "System prompt must contain '{tools_definition}' placeholder "
                    "to insert the tools description."
                )
        
            # if "{model_json_schema}" not in self.system_prompt:
            #     raise ValueError(
            #         "System prompt must contain '{model_json_schema}' placeholder "
            #         "to insert the JSON schema of the structured output."
            #     )

            system_prompt = self.system_prompt.format(
                # model_json_schema=json.dumps(AgentResponse.model_json_schema(), indent=2),
                tools_definition=self.toolkit.get_tools_description(format="text")
            )

        return {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ],
            "result": None,
            "cypher_query": None,
        }
    
    def invoke(
        self,
        init_state: RetrievalAgent.WorkflowInitialState,
        thread_id: str,
    ) -> (dict[str, Any] | Any):
        init_state = self.get_init_state(init_state)
        return self.workflow.invoke(
            input=init_state,
            config={
                "configurable": {
                    "thread_id": thread_id
                }
            }
        )

    def log_node_updates_dict(node_updates_dict: dict, verbose: bool = False, log_file_path: str = None):
        output = ''
        for node, update in node_updates_dict.items():
            # output += f"\n# "
            messages = update.get("messages", [])
            for msg in messages:
                pretty_repr = f"\n# {msg.pretty_repr()}"
                pretty_repr = pretty_repr.replace("Tool Calls:", "\n## Tool Calls:")
                if verbose:
                    print(pretty_repr)
                output += pretty_repr + "\n"
            # for key, value in update.items():
            #     print(f"{key}: {value}")
        if log_file_path:
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(output)
        # input("next> ")

    def logged_stream(
        self,
        init_state: RetrievalAgent.WorkflowInitialState,
        thread_id: str,
        verbose: bool = False,
        log_file_path: str = None,
    ) -> (dict[str, Any] | Any):
        init_state = self.get_init_state(init_state)
        node_updates_dicts = self.workflow.stream(
            input=init_state,
            config={
                "configurable": {
                    "thread_id": thread_id
                }
            },
            stream_mode="updates"
        )
        if log_file_path:
            log_file_path = Path(log_file_path)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            if log_file_path.exists():
                log_file_path.unlink()

        RetrievalAgent.log_node_updates_dict(
            {"init_state": init_state},
            verbose=verbose,
            log_file_path=log_file_path
        )
        for node_updates_dict in node_updates_dicts:
            RetrievalAgent.log_node_updates_dict(
                node_updates_dict,
                verbose=verbose,
                log_file_path=log_file_path
            )
            # input("next> ")
    
        # Get the actual final state from the workflow
        final_state = self.workflow.get_state(
            config={"configurable": {"thread_id": thread_id}}
        ).values
        return final_state

    @staticmethod
    def serialize_messages_state(state: MessagesState) -> list[dict]:
        trajectory = []
        
        for msg in state['messages']:            
            if isinstance(msg, SystemMessage):
                trajectory.append({
                    "role": "system",
                    "content": msg.content
                }) 
            elif isinstance(msg, HumanMessage):
                trajectory.append({
                    "role": "user",
                    "content": msg.content
                })           
            elif isinstance(msg, AIMessage):
                trajectory.append({
                    "role": "assistant",
                    "content": msg.content, # would evetually contain <think>thoughts</think>
                })
                if msg.tool_calls:
                    tool_calls = []
                    for tool_call in msg.tool_calls:
                        call_json = json.dumps({
                            "id": tool_call['id'],
                            "type": tool_call['type'],
                            "function": {
                                "name": tool_call['name'], 
                                "arguments": tool_call['args']
                            }
                        })
                        tool_calls.append(call_json)
                    trajectory[-1]["tool_calls"] = tool_calls    
            elif isinstance(msg, ToolMessage):
                trajectory.append({
                    "role": "tool",
                    # "name": ,
                    # "tool_call_id": ,
                    "content": str(msg.content)
                })
                
        return trajectory

