# Text-to-Cypher (Text2Cypher)

This repository contains the implementation, experiments, and evaluation for translating Natural Language questions into Neo4j Cypher queries. 

## Overview
The primary goal of this project is to accurately convert user queries in natural language into executable Cypher queries on a Neo4j Knowledge Graph. To achieve this, we developed and compared two main approaches:
1. **ReAct Agent (GPT-4.1)**: An autonomous agent leveraging the ReAct (Reasoning and Acting) framework. The agent is powered by GPT-4.1 and augmented with specialized tools that query indexes built directly on the Neo4j Knowledge Graph, allowing it to explore the schema and data properties to synthesize highly accurate Cypher statements dynamically.
2. **Fine-tuned Open-Weights Models**: We evaluated our tool-augmented agent against instruction-tuned open-weights models specifically fine-tuned for the Text2Cypher task, namely **Gemma-2-9B-IT** and **Llama-3.1-8B**.

## Project Structure
- `data/`: Contains raw datasets (`cypherbench`, `neo4j-2024v1`), interim predictions, and generations. Tracked via DVC.
- `src/`: Core Python source code.
  - `experiments/`: Scripts for data generation, collecting predictions, and evaluation (`generate.py`, `generate_with_hf.py`, `evaluate.py`).
- `notebooks/`: Jupyter notebooks for exploratory data analysis, effectiveness, and efficiency evaluations.
- `external/`: Submodules and external libraries like `cypherbench` and `text2cypher`.
- `indexes/`: Vector and retrieval indices (e.g., `minishlab/potion-retrieval-32M`).
- `dvc.yaml` / `dvc.lock`: Data Version Control pipelines defining the generative and evaluative DAG, ensuring highly reproducible ML experiments.
- `pyproject.toml`: Python dependency management powered by `uv`.

## Evaluation Metrics
We measure the effectiveness of the generated Cypher queries across structural, execution-based, and lexical metrics:
- **Jaccard Similarity**: Evaluated on the resulting sets/graphs fetched from Neo4j computations.
- **Exact Match**: Binary score representing if the Jaccard similarity between the graph results is exactly 1.0 (perfect semantic retrieval).
- **Google BLEU**: Lexical overlap using NLTK's `sentence_gleu`.
- **ROUGE-L F1**: Longest common subsequence matching utilizing `rouge_score`.

## Results
Below are the updated evaluation results on the test set comparing our GPT-4.1 ReAct agent approach against the fine-tuned Gemma and Llama models.

| Model | Jaccard Similarity | Exact Match | Google Bleu | Rouge L F1 |
| :--- | :--- | :--- | :--- | :--- |
| **gpt-4.1 (ReAct Agent)** | 0.3561 ± 0.4707 | 0.3364 ± 0.4726 | 0.5339 ± 0.2632 | 0.6294 ± 0.2708 |
| **gemma-2-9b-it (Fine-tuned)** | 0.3523 ± 0.4698 | 0.3348 ± 0.4720 | 0.6400 ± 0.2054 | 0.7364 ± 0.1774 |
| **llama-3.1-8b (Fine-tuned)** | 0.2253 ± 0.4133 | 0.2166 ± 0.4120 | 0.5906 ± 0.2074 | 0.6898 ± 0.1852 |

*Note: While the GPT-4.1 ReAct agent offers highly competitive execution accuracy (Jaccard/Exact Match) without needing task-specific fine-tuning, the fine-tuned models exhibit higher lexical scores (BLEU/ROUGE) as their generative syntax maps closer to the ground-truth training data.*
