This is a complex AI Engineering challenge. To design this fine-tuning process successfully, you must treat the LLM not just as a text generator, but as a **state-machine** that transitions between "Reasoning", "Tool Calling", and "Code Generation".

Here is the deep-dive design for the fine-tuning pipeline, broken down into **Data Synthesis**, **Data Formatting**, and **Training Strategy**.

---

### Phase 1: The Conceptual Framework (ReAct Pattern)

You are essentially implementing the **ReAct (Reason + Act)** pattern directly into the model's weights.

*   **Standard SFT:** `Input` $\rightarrow$ `Cypher Query`
*   **Agentic SFT (Your Goal):** `Input` $\rightarrow$ `Thought` $\rightarrow$ `Tool Call` $\rightarrow$ `[External Tool Output]` $\rightarrow$ `Thought` $\rightarrow$ `Final Cypher Query`.

**Crucial Concept:** During training, the "External Tool Output" is provided as static text. During inference, your Python script injects it.

---

### Phase 2: Synthetic Data Generation (The "Teacher")

You likely possess a dataset of `(Question, Ground_Truth_Cypher)` pairs. You lack the intermediate "Agent steps." We must synthesize them.

#### 1. Define Your Tools
Before generating data, define the Python function signatures strictly. The LLM needs to learn these signatures.
*   `find_node_label(search_term: str)`
*   `find_relationship_type(search_term: str)`
*   `get_property_keys(label_or_type: str)`

#### 2. The Synthesis Prompt (using GPT-4o/Claude 3.5)
You iterate through your existing dataset. For every pair, you ask a strong "Teacher" model to hallucinate the *process* of solving it.

**Prompt Template for the Teacher:**
> "You are an expert Neo4j developer. I will give you a Natural Language Question and the correct Ground Truth Cypher query.
>
> Your goal is to generate a **step-by-step conversation history** that leads to this result.
> Imagine you have access to the following tools: [List Tools].
>
> **Rules:**
> 1. Start by reasoning about what schema elements you need to find.
> 2. Call a tool using this JSON format: `{"tool": "name", "args": {...}}`.
> 3. Imagine the output the tool would return (ensure it matches the Ground Truth schema).
> 4. Repeat until you have enough info, then generate the final Cypher.
>
> **Input:**
> Question: "How many movies did Tom Hanks act in?"
> Cypher: `MATCH (p:Person {name: 'Tom Hanks'})-[:ACTED_IN]->(m:Movie) RETURN count(m)`"

#### 3. The Resulting "Trajectory"
The Teacher will output a conversation trace like this:
1.  **Assistant:** "I need to find the node label for people and movies, and the relationship for acting."
2.  **Assistant:** `<tool_code>{"name": "find_node_label", "args": {"search_term": "Tom Hanks"}}</tool_code>`
3.  **Tool Output:** `["Person", "Actor"]` (The teacher simulates this based on the ground truth).
4.  **Assistant:** "The label is Person. Now I need the relationship..."
... (steps continue) ...
5.  **Assistant:** "I have the schema. Here is the query:" `MATCH...`

---

### Phase 3: Dataset Formatting (Tokenization Strategy)

This is the most technical part. You must format the data so the model learns *when to stop* and wait for execution.

#### Special Tokens
You need to add special tokens to the tokenizer to handle the control flow.
*   `<|start_header_id|>` / `<|end_header_id|>` (Standard Llama-3 structure)
*   `<|tool_call|>` (Marks the start of a function call)
*   `<|tool_output|>` (Marks the start of the observation provided by the environment)

#### The Training Sample Structure
A single training sample will look like a long string of text (a chat history).

```text
<|begin_of_text|>
<|start_header_id|>system<|end_header_id|>
You are a graph database assistant. Use the available tools to explore the schema before querying.

<|start_header_id|>user<|end_header_id|>
How many movies did Tom Hanks act in?

<|start_header_id|>assistant<|end_header_id|>
I need to identify the correct labels for 'movies' and 'Tom Hanks'.
<|tool_call|>{"name": "find_node_label", "args": {"query": "Tom Hanks"}}<|eot_id|>

<|start_header_id|>tool<|end_header_id|>
[{"label": "Person", "property": "name", "example": "Tom Hanks"}]<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>
Now I need the relationship type for 'act in'.
<|tool_call|>{"name": "find_relationship_type", "args": {"query": "act in"}}<|eot_id|>

<|start_header_id|>tool<|end_header_id|>
["ACTED_IN", "DIRECTED"]<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>
I have sufficient information.
```cypher
MATCH (p:Person {name: 'Tom Hanks'})-[:ACTED_IN]->(m:Movie) RETURN count(m)
```<|eot_id|>
```

---

### Phase 4: The Loss Function & Masking (Crucial)

When fine-tuning, you use **Cross-Entropy Loss**. However, you should **not** train the model to predict the User's questions or the Tool's outputs.

*   **Why?** The Tool Output is deterministic (it comes from the database). We don't want the LLM to *hallucinate* the tool output; we want it to *read* the tool output and predict the *next action*.

**Masking Strategy:**
1.  **User Prompt:** Mask loss (set labels to -100).
2.  **Assistant Thought & Tool Call:** **Train** (Calculate loss). We want the model to learn to reason and call tools.
3.  **Tool Output:** Mask loss. This text is injected by your script during inference. The model should just condition on it, not predict it.
4.  **Final Cypher:** **Train** (Calculate loss).

---

### Phase 5: Training Implementation

Since you are a student, use **QLoRA** (Quantized Low-Rank Adaptation) to train on a consumer GPU (like an RTX 3090 or A100 on Colab).

**Recommended Stack:**
*   **Base Model:** `Llama-3-8B-Instruct` or `Gemma-7b-it`.
*   **Library:** `Unsloth` (highly recommended for 2x faster training) or `HuggingFace TRL` (Transformer Reinforcement Learning library).
*   **Peft Config:**
    *   `r` (Rank): 16 or 32.
    *   `target_modules`: `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]` (Train all linear layers for better reasoning).

---

### Phase 6: The Inference Loop (The Agent Runtime)

Once the model is trained, you cannot just run `model.generate()`. You need a controller script.

**Logic:**
1.  Append User Question to chat history.
2.  Run `model.generate()` with a stop_token set to `<|eot_id|>` or `<|tool_call|>`.
3.  **Check Output:**
    *   **Case A:** The output contains a Cypher query block. $\rightarrow$ **Done.** Return to user.
    *   **Case B:** The output contains `<|tool_call|>`.
        1.  Parse the JSON inside the tag.
        2.  Execute the actual Python function against Neo4j.
        3.  Format the result as a `<|tool_output|>` message.
        4.  Append this result to the chat history.
        5.  **GOTO Step 2** (Feed the history back into the model).

### Summary for your Thesis

To satisfy the "Agentic" requirement of your thesis:
1.  You are **simulating** an expert human's workflow via synthetic data generation.
2.  You are **embedding** that workflow into the LLM via Fine-Tuning with specific masking.
3.  You are **enabling** the workflow via a custom inference loop that handles the tool execution.

This is semantically equivalent to how "GPT-4 Function Calling" works under the hood, but you are building it manually for a specific domain (Graph Databases), which often yields SOTA results over generalist models.