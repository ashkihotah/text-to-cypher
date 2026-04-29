| Dataset Name | Primary Download Link | Associated References (Paper/Hugging Face/GitHub) | Key Features & Relevance |
| :---- | :---- | :---- | :---- |
| CypherBench | git clone https://huggingface.co/datasets/megagonlabs/cypherbench benchmark [^7] | HuggingFace: megagonlabs/cypherbench [^7]; Paper: *Awaiting Formal Citation (arXiv: 2412.10064v1)* [^8] | Foundational benchmark; includes graph structures and NL2Cypher pairs; essential for baseline performance testing of LLMs. |
| Neo4j Labs text2cypher | https://github.com/neo4j-labs/text2cypher [^9] | GitHub Repository [^9] | Resource hub providing datasets, evaluation methodology, and finetuning scripts; critical industrial resource for standardization. |

| Dataset Name | Primary Download Link | Associated References (Paper/GitHub/Related Challenges) | Key Features & Relevance to Cypher Derivation |
| :---- | :---- | :---- | :---- |
| Spider 1.0 | ([https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view](https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view)) [^5] | Paper (EMNLP'18): arXiv:1809.08887; GitHub: taoyds/spider [^5] | De-facto standard for cross-domain complexity; essential for generalized schema conversion and rule abstraction. |
| Spider 2.0 | ([https://github.com/xlang-ai/Spider2](https://github.com/xlang-ai/Spider2)) [^5] | Paper (arXiv): arXiv:2411.07763; GitHub: xlang-ai/Spider2 [^5] | Modern, more challenging benchmark; focuses on complex logical reasoning highly transferable to graph structure identification. |
| CoSQL | [Challenge Page](https://yale-lily.github.io/cosql) [^5] | Paper (EMNLP'19); Challenge Page [^5] | Context-dependent, conversational SQL; models multi-turn, stateful query building relevant for iterative graph traversal. |
| SParC | [Challenge Page](https://yale-lily.github.io/sparc) [^5] | Paper (ACL'19); Challenge Page [^5] | Context-dependent, cross-domain generalization; highly relevant for teaching path accumulation and sequential logic in graph querying. |

| Dataset Name | Primary Download Link | Associated References (Paper/Homepage/GitHub) | Key Features & Relevance to Cypher Derivation |
| :---- | :---- | :---- | :---- |
| Spider4SPARQL | ([https://github.com/ckosten/Spider4SPARQL](https://github.com/ckosten/Spider4SPARQL)) [^11] | Citation: 10386182; arXiv: 2309.16248v2 [^10] | Directly derived from Spider; includes Materialized KGs and PostgreSQL data; optimal resource for studying cross-paradigm conversion strategies. |
| LC-QuAD 2.0 | [Hugging Face](https://huggingface.co/datasets/mohnish/lc_quad) [^14] | Paper (ISWC 2019): dubey2017lc2; Homepage: http://lc-quad.sda.tech/ [^13] | Large-scale dataset (30k pairs) over Wikidata/DBpedia; excellent for developing complex path-finding and entity resolution capabilities. |
| QALD Series | *Varies by specific challenge/year* | Papers (e.g., SEMANTICS 2024 for COT-SPARQL) [^6] | Benchmarks various NLQ systems; useful for testing LLM reasoning strategies (CoT) in a graph context. |