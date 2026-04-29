## Prompt

Assuming that i already correctly have completed the training and fine tuning of my Agent, how can i integrate it into langchain Agent feature in order to use it as every other supported langchain agent already available? Try to describe the entire process starting from the model already available and beeing as complete as possible

## Answer

This is the final engineering step: **Deployment**.

Since you have fine-tuned your model (let's assume it's a Llama-3 variant) to output specific "Thoughts" and "Tool Calls" (e.g., in JSON format), you cannot simply use the out-of-the-box `OpenAIFunctionsAgent` because your model likely doesn't support the proprietary OpenAI API headers.

Instead, you must build a **Custom Agent using LCEL (LangChain Expression Language)**. This gives you full control over how the model's output is parsed.

Here is the complete, step-by-step integration pipeline.

---

### Step 1: Serving Your Model (The Inference Engine)

Do not load the model directly inside Python using `transformers` if you want performance. Use an inference server. I strongly recommend **vLLM** because it creates an **OpenAI-Compatible API server**. This tricks LangChain into thinking it is talking to GPT-4, making integration trivial.

**1.1. Launch the Server (Terminal)**
```bash
# Assuming you merged your LoRA adapters into the base model
vllm serve "path/to/your/fine-tuned-model" \
  --dtype auto \
  --api-key "EMPTY" \
  --port 8000
```

**1.2. Connect LangChain to it**
```python
from langchain_openai import ChatOpenAI

# We use ChatOpenAI, but point it to our local vLLM server
llm = ChatOpenAI(
    model="path/to/your/fine-tuned-model",
    openai_api_key="EMPTY",
    openai_api_base="http://localhost:8000/v1",
    temperature=0, # Deterministic for tool use
    max_tokens=512,
    stop=["<|eot_id|>", "<|tool_output|>"] # CRITICAL: Stop generating when tool should run
)
```

---

### Step 2: Define Your Tools

You must wrap your Python graph logic into LangChain `Tool` objects.

```python
from langchain.tools import tool

@tool
def get_schema_elements(query: str) -> str:
    """
    Useful for finding node labels or relationship types similar to the query string.
    Input should be a simple string like 'movie' or 'acted in'.
    """
    # ... Your Neo4j Vector Index Logic Here ...
    return "Found: Node(:Movie), Rel(:ACTED_IN)"

@tool
def run_cypher(query: str) -> str:
    """
    Executes a read-only Cypher query against the database.
    Input must be a valid Cypher string.
    """
    # ... Your Neo4j Driver Logic Here ...
    return str(results)

tools = [get_schema_elements, run_cypher]
```

---

### Step 3: The Custom Output Parser (The "Bridge")

This is the most important part. Your fine-tuned model outputs text (e.g., a JSON string or a specific XML tag). LangChain needs to convert that text into an `AgentAction` object.

You need to write a regex parser that matches **exactly** how your fine-tuned model outputs tool calls.

*Assumption: Your model was trained to output: `<|tool_call|>{"name": "...", "args": {...}}`*

```python
import json
import re
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import BaseOutputParser

class MyFineTunedAgentParser(BaseOutputParser):
    
    def parse(self, text: str):
        # 1. Check if the model is done (Standard final answer)
        # Adjust this logic based on how your model signals completion
        if "Final Answer:" in text:
            return AgentFinish(
                return_values={"output": text.split("Final Answer:")[-1].strip()},
                log=text
            )

        # 2. Regex to find your custom tool call syntax
        # Looking for: <|tool_call|>{ JSON }
        pattern = r"<\|tool_call\|>(.*?)(?:<\|eot_id\|>|$)"
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            try:
                # Extract JSON
                json_str = match.group(1).strip()
                tool_call = json.loads(json_str)
                
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # Return the Action to LangChain
                return AgentAction(
                    tool=tool_name,
                    tool_input=tool_args,
                    log=text
                )
            except Exception as e:
                raise OutputParserException(f"Failed to parse tool JSON: {e}")
        
        # 3. If no tool call and no final answer, treat as thought or error
        # For robustness, you might return AgentFinish here if it looks like plain text
        return AgentFinish(return_values={"output": text}, log=text)
```

---

### Step 4: The Prompt Template (The "Context")

You must reconstruct the exact prompt format used during training. If you used Llama-3 system prompts, use them here.

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Define the System Prompt exactly as you did in training
system_prompt = """You are a graph engineering agent.
You have access to the following tools:
{tools_desc}

To use a tool, output: <|tool_call|>{{"name": "tool_name", "args": {{"arg_name": "value"}}}}

Always check the schema before writing Cypher.
"""

# Format tools for the prompt
tools_desc = "\n".join([f"{t.name}: {t.description}" for t in tools])
formatted_system = system_prompt.format(tools_desc=tools_desc)

prompt = ChatPromptTemplate.from_messages([
    ("system", formatted_system),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"), # History of thoughts/actions
])
```

---

### Step 5: Assembly (LCEL)

Now we chain the components together: `Prompt -> LLM -> Parser`.

```python
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.agents import AgentExecutor

# 1. Create the Runnable Agent
agent = (
    {
        "input": lambda x: x["input"],
        # This formats previous steps (Thought -> Tool -> Obs) back into the prompt
        "agent_scratchpad": lambda x: format_log_to_str(x["intermediate_steps"]), 
    }
    | prompt
    | llm
    | MyFineTunedAgentParser()
)

# 2. Create the Executor (The Loop Manager)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10, # Prevent infinite loops
    handle_parsing_errors=True # If the model outputs bad JSON, try to recover
)
```

---

### Step 6: Execution

Now you use it exactly like any other LangChain agent.

```python
response = agent_executor.invoke({"input": "How many movies did Tom Hanks act in?"})
print(response["output"])
```

### Summary of the Flow

1.  **User Input:** "How many movies..."
2.  **Prompt:** Injects input + system instructions into Llama-3.
3.  **LLM (vLLM):** Generates `I need to find the node. <|tool_call|>{"name": "get_schema", ...}`.
4.  **Stop Token:** vLLM pauses because it sees `<|tool_call|>`.
5.  **Parser:** Regex extracts the JSON. Returns `AgentAction`.
6.  **AgentExecutor:** Sees `AgentAction`. Calls the Python function `get_schema`.
7.  **Observation:** `Found (:Person)`.
8.  **Scratchpad:** Formats the history: `User: ... \n AI: <|tool_call|>... \n Tool: Found (:Person)`.
9.  **Loop:** Sends history back to LLM.
10. **LLM:** Generates `Match (p:Person)... Final Answer: 5`.
11. **Parser:** Detects "Final Answer". Returns `AgentFinish`.

This setup allows you to leverage LangChain's ecosystem (memory, callbacks, tracing with LangSmith) while using your bespoke, fine-tuned "brain."

#