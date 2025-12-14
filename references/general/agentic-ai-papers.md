To build a solution at the Master’s Thesis level, you need to trace the lineage of how LLMs evolved from **Static Text Generators** to **Dynamic Agents**.

Here is the curated bibliography of the fundamental papers you need to study. I have categorized them logically from the **Theoretical Foundation** to **Fine-Tuning Methodologies** and **Optimization**.

---

### Category 1: The Theoretical Foundation (The "What")
*Before fine-tuning, you must understand the data structure (trajectories) you are fine-tuning on.*

#### 1. ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al., ICLR 2023)
*   **The Core Idea:** This is the most important paper for your thesis. It introduced the interleaved pattern of `Thought` $\rightarrow$ `Action` $\rightarrow$ `Observation`. Before this, models either just reasoned (CoT) or just acted.
*   **Relevance:** Your synthetic training data will follow this exact format. You are essentially "distilling" ReAct capabilities into the model weights.

#### 2. Chain-of-Thought Prompting Elicits Reasoning in Large Language Models (Wei et al., NeurIPS 2022)
*   **The Core Idea:** LLMs perform better when they "show their work" before giving an answer.
*   **Relevance:** Your "Thought" step in the agent loop is a direct application of CoT. Understanding why CoT works helps explain why your agent needs a "Reasoning" step before calling a tool.

---

### Category 2: Tool Learning & API Fine-Tuning (The "How")
*These papers specifically tackle how to modify weights to output function calls.*

#### 3. Toolformer: Language Models Can Teach Themselves to Use Tools (Schick et al., Meta AI, 2023)
*   **The Core Idea:** The first major paper to show that you can fine-tune a model to *self-generate* API calls. They used a self-supervised method to insert API calls into plain text where they were useful.
*   **Relevance:** It proves that tool use can be learned as a language modeling task. It defines the `[func_name(args)]` tokenization strategy.

#### 4. Gorilla: Large Language Model Connected with Massive APIs (Patil et al., UC Berkeley, 2023)
*   **The Core Idea:** They fine-tuned LLaMA specifically to make correct API calls (handling constraints, arguments, and syntax) without hallucinating. They introduced "Retrieval-Aware Training" (combining retriever + LLM).
*   **Relevance:** Your thesis is effectively building a "Graph-Gorilla." Study their "APIBench" dataset construction; it’s a blueprint for your dataset.

#### 5. ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs (Qin et al., 2023)
*   **The Core Idea:** They introduced **DFS (Depth-First Search) based Decision Trees** to generate training data. Instead of just one path, they explored multiple tool paths to find the best one, then trained on that.
*   **Relevance:** This validates the "Agentic" approach over the static one. It shows that navigating a complex space (like a graph schema) requires planning capabilities learned during fine-tuning.

---

### Category 3: Agent-Tuning (The "Workflow")
*These papers focus on fine-tuning specifically for the "Agent Loop" logic.*

#### 6. FireAct: Toward Language Agents with Fine-grained Reactivity (Chen et al., 2023)
*   **The Core Idea:** This paper explicitly compares **Prompting (ReAct)** vs. **Fine-Tuning (FireAct)**. They used GPT-4 to generate ReAct trajectories and then fine-tuned smaller models (Llama-2) on them.
*   **Relevance:** **This is your thesis methodology.** They proved that a fine-tuned small model can outperform a prompted large model in agentic tasks. It validates your hypothesis.

#### 7. AgentTuning: Enabling Generalized Agent Abilities for LLMs (Zeng et al., 2023)
*   **The Core Idea:** They created a dataset called **AgentInstruct**. They mixed "Agent Trajectories" with "General Chat Data" to prevent the model from losing its general language abilities (Catastrophic Forgetting) while becoming a better agent.
*   **Relevance:** If you find your model becomes too "robotic" or loses its ability to chat normally, this paper offers the solution (mixing data sources).

---

### Category 4: Optimization & Alignment (The "Refinement")
*How to make the agent prefer the "Right" path (DPO).*

#### 8. Direct Preference Optimization: Your Language Model is Secretly a Reward Model (Rafailov et al., NeurIPS 2023)
*   **The Core Idea:** As discussed, this replaces PPO with a stable classification loss.
*   **Relevance:** The mathematical justification for using DPO in your thesis.

#### 9. Calibrating Sequence likelihood Improves Conditional Language Generation (Calibration papers)
*   *Note:* While not a single "famous" paper, look for literature on **Token Probability Calibration** in agents.
*   **Relevance:** You need your agent to be confident when it knows the schema, and uncertain when it doesn't. DPO helps here by penalizing hallucinations.

---

### Category 5: Domain Specific (Graph & Structure)
*Papers that apply these concepts to Structured Data/Graphs.*

#### 10. StructGPT: A General Framework for Large Language Model to Reason over Structured Data (Jiang et al., 2023)
*   **The Core Idea:** They proposed an "Iterative Reading-then-Reasoning" approach on knowledge graphs (interfaces). They treat the graph as an API.
*   **Relevance:** It bridges the gap between "Abstract Agent Papers" and "Concrete Graph Problems."

#### 11. Binder: Neural-Symbolic Execution (Cheng et al., 2023)
*   **The Core Idea:** Maps natural language to an intermediate programming language (like SQL/Cypher) but allows the LM to "call out" to an execution engine during generation to resolve values.
*   **Relevance:** Very similar to your idea of checking the schema/values before finalizing the query.

---

### Summary: Your "Reading Order"

1.  **Read `ReAct` (Yao)** first to understand the *trajectory* structure.
2.  **Read `FireAct` (Chen)** next. This is the **Blueprint** for your fine-tuning strategy (Teacher -> Student distillation).
3.  **Read `Gorilla` (Patil)** to understand how to handle strict syntax for your Python tools.
4.  **Read `DPO` (Rafailov)** to understand the loss function you will use for the second stage of training.

If you cite these 4 pillars in your thesis, you will demonstrate a complete command of the State of the Art.