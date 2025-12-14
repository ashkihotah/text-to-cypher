# Prompt

Does every open source LLMs have their own versions of all these special tokens you mentioned? Are they all the same for each open source LLM or do they differ in syntax? If each open source LLM has their own agentic special tokens, can you list me for each of them what are all special tokens?

---

The short answer is: **No, they are not the same.**

Every major Large Language Model family (Meta, Google, Mistral, Alibaba, etc.) speaks a different "structural dialect." They use different special tokens to define where a user message starts, where the system prompt ends, and how tool calls are handled.

This is often called the **"Chat Template"** problem.

Here is the complete breakdown of the special tokens for the major open-source LLMs you are likely to use.

---

### 1. The Llama-3 Family (Llama-3, 3.1, 3.2)
*Meta changed everything from Llama-2 to Llama-3. This is currently the most robust format for Agentic work.*

**Chat Structure Tokens:**
*   `<|begin_of_text|>`: Marks the start of the entire sequence.
*   `<|start_header_id|>`: Starts a role definition.
*   `<|end_header_id|>`: Ends a role definition.
*   `<|eot_id|>`: End of Turn (Wait for user/tool).
*   `<|fin_id|>`: (Llama 3.1 only) End of the generation.

**Roles:** `system`, `user`, `assistant`, `ipython` (for tool use).

**Native Agentic Tokens (Llama 3.1 specific):**
Llama 3.1 was explicitly trained for tool use and includes these native tokens (so you don't strictly *have* to add your own, though for a thesis, custom tokens are often safer):
*   `<|python_tag|>`: Signals a call to a python interpreter.
*   `<|eom_id|>`: End of Message (distinct from End of Turn—used when the model wants to execute a tool but isn't done talking).

**Example Structure:**
```text
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an agent.<|eot_id|><|start_header_id|>user<|end_header_id|>

Query the graph.<|eot_id|><|start_header_id|>assistant<|end_header_id|>
```

---

### 2. The Gemma Family (Gemma 1, Gemma 2)
*Google uses a simpler, XML-like tag structure.*

**Chat Structure Tokens:**
*   `<bos>`: Beginning of stream.
*   `<eos>`: End of stream.
*   `<start_of_turn>`: Starts a message.
*   `<end_of_turn>`: Ends a message.

**Roles:** `user`, `model` (Note: Gemma uses "model", not "assistant").

**Native Agentic Tokens:**
Gemma **does not** have native `<|tool_call|>` tokens in its base vocabulary. You **must** add them (using `tokenizer.add_special_tokens`) or train it to output plain text JSON blocks.

**Example Structure:**
```text
<bos><start_of_turn>user
Hello<end_of_turn>
<start_of_turn>model
Hi there<end_of_turn>
```

---

### 3. The Mistral / Mixtral Family (v0.1, v0.2, NeMo)
*Mistral traditionally uses the Llama-2 style "Instruction" format, though newer versions (Tekken) are evolving.*

**Chat Structure Tokens:**
*   `<s>`: Beginning of string.
*   `</s>`: End of string.
*   `[INST]`: Starts a User Instruction.
*   `[/INST]`: Ends a User Instruction.

**Roles:** Mistral doesn't explicitly use "Role" tokens like Llama-3. It relies on the `[INST]` brackets to imply the User, and text outside brackets to imply the Assistant.

**Native Agentic Tokens:**
Mistral Models (specifically `Mistral-Large` or `Mistral-Nemo`) have been trained for function calling, but the open-weights versions usually rely on a specific JSON schema prompt rather than specific control tokens like Llama 3.1.

**Example Structure:**
```text
<s>[INST] What is the weather? [/INST] It is sunny.</s>
```

---

### 4. ChatML (Qwen, Yi, Microsoft Phi-3)
*ChatML is a format originally defined by OpenAI (internally) but popularized by open-source models like Qwen (Alibaba) and Yi (01.AI). It is very popular for fine-tuning.*

**Chat Structure Tokens:**
*   `<|im_start|>`: Start of a message.
*   `<|im_end|>`: End of a message.

**Roles:** `system`, `user`, `assistant`.

**Native Agentic Tokens:**
Like Gemma, these usually do not have reserved tokens for tools by default. You treat tool outputs as a specific message type or add your own tokens.

**Example Structure:**
```text
<|im_start|>system
You are a bot.<|im_end|>
<|im_start|>user
Hi<|im_end|>
<|im_start|>assistant
Hello<|im_end|>
```

---

### 5. Command R+ (Cohere)
*This is a massive open-weights model explicitly built for RAG and Agents.*

**Chat Structure Tokens:**
*   `<|START_OF_TURN_TOKEN|>`
*   `<|END_OF_TURN_TOKEN|>`
*   `<|USER_TOKEN|>`
*   `<|CHATBOT_TOKEN|>`
*   `<|SYSTEM_TOKEN|>`

**Native Agentic Tokens:**
Cohere has specific tokens for tools because it is an agent-first model.
*   `<|TOOL_CALLS_GENERATION_SEPARATOR|>`
*   `<|TOOL_OUTPUTS_GENERATION_SEPARATOR|>`

---

### Summary Table for Your Implementation

| Model Family | Start Token | End Token | Role Wrapper | Native Tool Tokens? |
| :--- | :--- | :--- | :--- | :--- |
| **Llama 3 / 3.1** | `<|begin_of_text|>` | `<|eot_id|>` | `<|start_header_id|>` | **Yes** (in 3.1) |
| **Gemma 2** | `<bos>` | `<end_of_turn>` | `<start_of_turn>` | No |
| **Mistral** | `<s>` | `</s>` | `[INST] ... [/INST]` | No |
| **Qwen (ChatML)** | (None) | `<|im_end|>` | `<|im_start|>` | No |

### How to Handle This in Your Code?

Do not hardcode strings like `"<|start_header_id|>"` unless you are exclusively using Llama-3.

Instead, use the **HuggingFace Chat Template** engine. It automatically applies the correct tokens for the model you loaded.

```python
from transformers import AutoTokenizer

model_id = "meta-llama/Meta-Llama-3-8B-Instruct"
# OR model_id = "google/gemma-2-9b-it"

tokenizer = AutoTokenizer.from_pretrained(model_id)

messages = [
    {"role": "user", "content": "Hello!"}
]

# This automatically converts the list to the correct string format
# e.g., for Llama-3 it produces "<|begin_of_text|><|start_header_id|>..."
# e.g., for Gemma it produces "<bos><start_of_turn>..."
prompt = tokenizer.apply_chat_template(messages, tokenize=False)
```

### Strategic Advice for Your Thesis

Since you are **fine-tuning**, you have two choices:

1.  **The Purist Route (Recommended):** Stick to **Llama-3.1**. It has the most sophisticated token definitions for agents. You can reuse its existing `<|python_tag|>` or define your own `<|tool_call|>` and insert it into the Llama-3 tokenizer.
2.  **The Custom Route:** If you use Gemma or Mistral, you **must** add your custom special tokens (`<|tool_call|>`, etc.) to the tokenizer before training. If you don't, the model will split `<|tool_call|>` into multiple tokens like `<` `|` `tool` `_` `call` `|` `>`, which destroys the "trigger" effect you need for your Python parser.

**Recommendation:** Use **Llama-3-8B-Instruct**. Its tokenizer is explicitly designed for the state-machine logic you are building.