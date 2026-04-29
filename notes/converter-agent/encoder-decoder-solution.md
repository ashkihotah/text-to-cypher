# Encoder-Decoder Solution

## Rationale

For specialized, structured tasks like **Text-to-SQL**, **Text-to-SPARQL**, and **Text-to-Cypher**, Encoder-Decoder architectures (like T5-3B or specialized BART variants) can **significantly outperform** much larger Decoder-Only models (like GPT-4 or Llama-70B) in terms of accuracy-per-parameter and reliability.

They win because these tasks are effectively **translation** problems (Natural Language $\to$ Formal Logic), not "creative generation" problems.

Below is the complete motivation and a feasible, step-by-step training blueprint for building a State-of-the-Art (SOTA) Encoder-Decoder for these tasks.

### Why Encoder-Decoder Wins Here

The "Decoder-Only" architecture (GPT) suffers from a specific weakness in structured tasks: **it cannot plan the end of the sentence while writing the beginning.**

| Feature | Why Encoder-Decoder (e.g., T5) Wins | Why Decoder-Only (e.g., GPT) Struggles |
| :--- | :--- | :--- |
| **Bidirectional Schema Visibility** | The **Encoder** sees the *entire* database schema (columns, table names) and the user question simultaneously. It can cross-reference "Revenue" in the question with `col_sales_amt` in the schema *before* writing a single character of code. | The model must "remember" the schema (which was in the prompt) while generating. As the query gets longer, its attention to the schema definitions in the distant past can fade (the "Lost in the Middle" phenomenon). |
| **Hard Constraints (The "Killer App")** | You can strictly enforce grammar constraints on the **Decoder** because its *only* job is generation. You can force it to output valid SQL tokens only. | Hard constraints are difficult to apply to GPT models without breaking their "chain of thought" or reasoning capabilities. |
| **Vocabulary Efficiency** | You can train a custom tokenizer optimized for SQL/SPARQL keywords (`SELECT`, `OPTIONAL MATCH`, `WHERE`), making the model highly efficient. | Uses a general-purpose tokenizer where code keywords might be split inefficiently (e.g., `SELECT` might be one token, but a complex variable name might be three). |

## Architecture Overview

### Base Models

| **Base Model** | **T5-3B** or **CodeT5** (Start here; 3B is the sweet spot for performance/latency). |

### Constrained Decoding (Inference Time)

**This is how you beat GPT-4.**
When a Decoder-Only model generates code, it can hallucinate a table name or miss a closing parenthesis. With an Encoder-Decoder, you can use **Constrained Beam Search**.

* **Tool:** Use a library like **PICARD** (Parsing Incrementally for Constrained Auto-Regressive Decoding).
* **How it works:**
    1.  The Decoder suggests the next top 5 tokens (e.g., `FROM`, `WHERE`, `SELECT`, `human`, `table`).
    2.  PICARD checks the partial query against the **SQL Grammar** and the **Input Schema**.
    3.  If the model suggests `SELECT name FROM`, PICARD looks at the schema. If the model tries to generate `non_existent_table`, PICARD **blocks that token** (sets probability to 0).
    4.  The model is *forced* to pick a valid table name from the schema you provided in the Encoder.

**Result:** It is mathematically impossible for the model to generate a syntax error or hallucinate a column name.

## How to Train It

To beat a general-purpose LLM, you cannot just "fine-tune." You must engineer the entire pipeline—from input representation to inference constraints.

### Input Serialization (The Encoder's View)

The most critical step is how you "feed" the schema to the Encoder. You must linearize the structured data (tables/graphs) into a sequence the Transformer can understand.

* **For SQL (Relational):**
    Use a format that explicitly links columns to their tables and types.
    * *Input String:* `Question: Show me the top salesman. | Schema: [Table] employees [Col] id (int), name (text) [Table] sales [Col] emp_id (fk), amount (float)`
    * *Technique:* Use **Relation-Aware Encoding**. Add special embeddings to tell the model "This token is a Column," "This token is a Table," and "This Column belongs to this Table."

* **For SPARQL/Cypher (Graph):**
    Graph schemas are harder because they are cyclic. You must serialize "triples" or "edge patterns."
    * *Input String:* `Question: Who acted in 'The Matrix'? | Nodes: Person, Movie | Edges: (Person)-[:ACTED_IN]->(Movie), (Person)-[:DIRECTED]->(Movie)`
    * *Technique (Semantic Forwarding):* Do **not** train on raw IDs like `wd:Q76` (Wikidata ID for Obama). Pre-process your training data to replace IDs with their English labels (`wd:Barack_Obama`). It is much easier for the Encoder to map "Obama" $\to$ `wd:Barack_Obama` than "Obama" $\to$ `wd:Q76`.

| Token Type | Tokens | Purpose |
|------------|--------|---------|
| Separators | `<seq>`, `</seq>` | Standard start/end of sequence (often already present). |
| Section Markers | `<cmd>`, `<schema>` | Tells the Encoder: "This part is the User Question" vs "This part is the Database Schema." |
| Graph Structure | `<node>`, `<rel>`, `<prop>` | Explicitly marks schema elements. Tells the model: "The next word is a Node Label." |
| Data Types | `<type:str>`, `<type:int>` | Helps the model decide if it should quote a value `name='Neo'` or not `age=30`. |
| Examples | `<example:> "The Matrix"` | Provides concrete examples of property values to guide the model. |
| Pointer Tokens | `<map:0>`, `<map:1>`... | (Advanced) Used for "Pointer Networks" to link output tokens directly to input schema indices, but standard tokens work fine for T5. |

```
<cmd:> Find all movies that Tom Hanks acted in
<schema:>
    <node:> Person
        <prop:> name <type:str> <example:> "Tom Hanks"
        <prop:> born <type:int> <example:> 1956
    <node:> Movie
        <prop:> title <type:str> <example:> "Forrest Gump"
        <prop:> released <type:int> <example:> 1994
        ...
    ...
    <rel:>
        <from:> Person
        <label:> ACTED_IN
        <to:> Movie
        <prop:> role <type:str> <example:> "Forrest Gump"
    ...
```

```
MATCH (p:Person {name: "Tom Hanks"})-[:ACTED_IN]->(m:Movie) RETURN m.title
MATCH (m:Movie)<-[:ACTED_IN]-(p:Person {name: "Tom Hanks"}) RETURN m.title
```

### The Training Objective

Standard "Next Token Prediction" is insufficient. You need an objective that teaches the model the *structure* of the query language.

1.  **Intermediate Pre-training (Schema Alignment):**
    Before fine-tuning on your specific questions, train the model on millions of synthetic pairs of (Schema + Random Query).
    * *Why:* This teaches the model valid SQL/Cypher syntax without needing expensive human-labeled data.
    * *Objectives:* 
      * **Sentence-Level Denoising.** Mask out the `WHERE` clause or the `JOIN` condition and force the model to reconstruct *only* the **logical logic**, not just random words.
      * **Schema-Query Alignment.** Given a natural language description of a query, a schema and a masked query, force the model to reconstruct the masked query. The masked parts of the query are only schema specific components. This teaches the model to link NL phrases to schema elements.

2.  **Fine-Tuning (The Translation Task):**
    Train on your gold dataset (e.g., Spider for SQL, LC-QuAD for SPARQL).
    * *Hyperparameter Tip:* Use a **small learning rate** for the Encoder (to preserve language understanding) and a **larger learning rate** for the Decoder (to aggressively learn the new syntax).

| **Loss Function** | **Cross-Entropy** + **Execution Guided Rewards** (Optional: Reinforcement Learning where reward = 1 if the query executes successfully against the DB). |


## Pros And Cons

It is **highly feasible** and standard practice in enterprise settings where accuracy > creativity.

* **Training Cost:** Low. You are fine-tuning a 3B parameter model, not pre-training a 70B one. A single 8x A100 node can fine-tune T5-3B on the Spider dataset in a few hours.
* **Inference Latency:** Higher than a small GPT model (due to the constrained decoding checks), but significantly cheaper and faster than prompting GPT-4-Turbo.
