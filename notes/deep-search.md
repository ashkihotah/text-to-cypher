# **Exhaustive Catalog of Text-to-Query Datasets for Semantic Parsing: SQL, SPARQL, and Strategic Derivation for Cypher**

## **1\. Executive Summary and Contextual Landscape**

The task of Natural Language (NL) to Structured Query translation, known as Text-to-Query (T2Q) or semantic parsing, is a pivotal field in enabling intuitive access to structured data. This report provides an exhaustive catalog of essential T2Q datasets currently available, focusing specifically on Cypher Query Language (CQL) for property graphs, alongside mature benchmarks for Structured Query Language (SQL) and SPARQL, the query language for Resource Description Framework (RDF) knowledge graphs.  
The primary objective is the development of a robust Text-to-Cypher (NL2Cypher) model. Given the relative nascency of dedicated Cypher benchmarks compared to the vast resources available for relational and semantic web queries, the strategy outlined herein emphasizes the selection of high-complexity NL2SQL and NL2SPARQL datasets that can be leveraged for high-fidelity synthetic data derivation.[^1] This approach addresses the inherent data scarcity challenge within the NL2Cypher domain.

### **1.1 The Semantic Parsing Challenge in Heterogeneous Databases**

Text-to-Query systems serve the function of translating natural language questions into executable queries, thereby reducing the complexity associated with mastering specialized query languages.[^3] Historically, this field has been dominated by Text-to-SQL (NL2SQL), the universal language for data manipulation across diverse database applications.[^4] However, the rise of specialized data models has introduced two equally important, albeit structurally distinct, query languages: SPARQL for RDF triple stores and Cypher for Neo4j's property graphs.  
The current landscape reveals a significant disparity in resource maturity. The NL2SQL domain has established large-scale, cross-domain benchmarks (Tier I), while the NL2Cypher domain is still reliant on limited, foundational datasets (Tier II).[^1] To train an expert-level Cypher model, a researcher must move beyond direct native resources and transfer semantic parsing complexity from the most successful NL2SQL and NL2SPARQL challenges.  
The rationale for leveraging SPARQL data is compelling, as graph query languages share fundamental operational principles. Both Cypher and SPARQL inherently focus on pattern matching, graph navigation, and topological awareness.[^3] Conversely, SQL systems, which operate based on fixed tabular schema and explicit JOIN operations, require complex semantic restructuring to represent relationships as graph paths. Therefore, SPARQL datasets are expected to yield derived Cypher training data with higher semantic fidelity than most basic SQL datasets.

## **2\. Core Target Benchmarks: Text-to-Cypher (NL2Cypher) Datasets**

The development of any NL2Cypher model must begin with the few existing native property graph benchmarks. These resources are critical for establishing a baseline performance and validating the eventual performance of models trained on derived data.

### **2.1 CypherBench: The Foundational Benchmark**

CypherBench, developed by Megagon Labs, currently represents the most critical existing public resource for training and evaluating models that translate natural language into Cypher queries.[^7]  
This benchmark is explicitly designed for the rigorous evaluation of foundational and fine-tuned large language models (LLMs) on the Text2Cypher task.[^8] The dataset is comprehensive, providing both the raw graph structures (essential for evaluating query execution accuracy) and the corresponding natural language question-to-Cypher query pairs.[^7]  
The recommended method for acquisition is through the Hugging Face dataset repository, utilizing Git Large File Storage (LFS) to clone the repository, which contains all necessary files:  
git clone https://huggingface.co/datasets/megagonlabs/cypherbench benchmark [^7]  
As the Text2Cypher task is fundamentally a sequence-to-sequence translation problem, models trained on this data are typically evaluated using standard text-to-text comparison metrics, such as ROUGE, BLEU, METEOR, BERTScore, and FrugalScore, often implemented via the HuggingFace Evaluate library.[^8]

### **2.2 Supplementary Cypher Resources and Emerging Methodologies**

Beyond CypherBench, the research ecosystem for NL2Cypher relies heavily on tooling, methodological repositories, and advanced synthetic generation techniques, acknowledging the limitations imposed by manual data annotation.  
The Neo4j Labs text2cypher GitHub repository serves as an important resource hub for the community, providing datasets, detailed notebooks for evaluation, and scripts for fine-tuning LLMs specifically for NL2Cypher tasks.[^9] This signifies an ongoing industrial commitment to standardizing the research methodology.  
Analysis of the NL2Cypher domain confirms that the scarcity of high-quality, diverse fine-tuning datasets is a primary bottleneck. Furthermore, the effectiveness of any model is strongly correlated with its ability to handle the specific graph schema.[^1] Unlike relational schemas, Cypher relies on visual patterns—() for nodes, \`\` for relationships—with explicit labels and types, demanding deep topological awareness from the generating model.[^3]  
The transition in this field is evident in the shift from earlier rule-based or template-based semantic parsing systems toward LLM-driven generation. Early academic literature documents systems that relied on algorithmic query construction or template selection.[^3] However, contemporary research now prioritizes approaches that use advanced LLM prompting, often integrating Named Entity Recognition (NER) to map NL concepts to graph entities (nodes and relationships).[^3] This rapid methodological evolution confirms that high-quality synthetic generation is now seen as the necessary strategy to supplement limited native data.  
A sophisticated example of this evolution is **AutoCypher**, a synthetic generation technique that uses a novel LLM-as-Database-Filter approach.[^2] This method ensures that synthetically generated Cypher queries, derived from natural language, better align with the underlying schema, thereby mitigating the persistent issue of generating syntactically correct but semantically nuanced errors common in purely synthetic datasets. The reliance on such schema-aware generation techniques underscores the critical nature of schema ingestion and utilization for effective NL2Cypher systems.  
Table 2.1: Comprehensive Text-to-Cypher Dataset Catalog

| Dataset Name | Primary Download Link | Associated References (Paper/Hugging Face/GitHub) | Key Features & Relevance |
| :---- | :---- | :---- | :---- |
| CypherBench | git clone https://huggingface.co/datasets/megagonlabs/cypherbench benchmark [^7] | HuggingFace: megagonlabs/cypherbench [^7]; Paper: *Awaiting Formal Citation (arXiv: 2412.10064v1)* [^8] | Foundational benchmark; includes graph structures and NL2Cypher pairs; essential for baseline performance testing of LLMs. |
| Neo4j Labs text2cypher | https://github.com/neo4j-labs/text2cypher [^9] | GitHub Repository [^9] | Resource hub providing datasets, evaluation methodology, and finetuning scripts; critical industrial resource for standardization. |

## **3\. Tier I Data Source: Premier Text-to-SQL (NL2SQL) Benchmarks**

Text-to-SQL datasets are crucial for NL2Cypher development not for direct translation, but for providing complex natural language variance and advanced logical structures that can be adapted to graph contexts. The maturity and sheer volume of these resources make them indispensable for generating diverse training data.

### **3.1 Spider and its Derivatives: Cross-Domain Gold Standard**

**Spider** is the single most important NL2SQL resource because its design emphasizes cross-domain generalization, a requirement that directly mirrors the challenges encountered in real-world graph database applications.  
**Spider 1.0** consists of 10,175 questions and 5,693 unique, complex SQL queries derived from 200 databases spanning 138 domains.[^5] Crucially, the dataset ensures that different complex SQL queries and databases appear in the train and test sets. The challenge is thus generalization—systems must perform well not only on new queries but also on entirely new database schemas.[^5] This necessity for learning abstract semantic parsing rules, rather than schema-specific memorization, makes Spider superior to schema-specific SQL datasets for conversion purposes.  
The primary access links and references are:

* **Download Link:**([https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view](https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view)).[^5]  
* **Paper Reference:** Spider Paper (EMNLP'18).[^5]  
* **GitHub Repository:**([https://github.com/taoyds/spider](https://github.com/taoyds/spider)) (for baseline models and evaluation).[^5]

In the context of modern LLM capabilities, **Spider 2.0** was released as a more realistic and challenging iteration.[^5] Its structure is specifically designed to maintain relevance in the era of large language models. The research confirmed that even large foundational models typically fall short of capturing the full range of logical scenarios in such complex datasets, necessitating targeted fine-tuning to improve performance.[^4]

* **Spider 2.0 Download (Data/Code):**(https://github.com/xlang-ai/Spider2).[^5]  
* **Spider 2.0 Paper:** [*paper*](https://arxiv.org/abs/2411.07763) (ICLR 25 submission).[^5]

### **3.2 Context-Aware SQL Benchmarks (SParC and CoSQL)**

For developing advanced NL2Cypher models, particularly those addressing dynamic or exploratory graph traversal, datasets that incorporate conversational context are essential. Complex graph queries often involve multi-step path finding or sequential operations, requiring the model to maintain statefulness.  
**SParC (ACL'19)** addresses cross-domain semantic parsing in context.[^5] It models how users build upon previous questions, forcing the system to derive a complete query based on the current utterance and the history of the conversation. This mirrors the iterative, path-accumulating nature of many real-world Cypher query sequences (e.g., "Find entity A," then "Show me the neighbors of that entity").  
**CoSQL (EMNLP'19)** similarly focuses on Conversation-to-SQL, challenging models to build complex queries based on preceding turns.[^5]  
The conceptual connection here is profound: the cross-domain generalization required by Spider directly correlates with the schema generalization required for NL2Cypher. A high-performing NL2Cypher system must map abstract natural language concepts to schema elements (node labels, relationship types, and properties) that it may not have explicitly encountered during training. Spider’s design, which isolates schemas between the training and test sets, forces models to learn these transferable, abstract semantic parsing rules.  
It is important to recognize that converting NL2SQL data into a graph format necessitates a highly controlled dual transformation: first, the relational schema (tables and foreign keys) must be mapped to a property graph schema (nodes and relationships), and second, the SQL query logic (explicit JOINs) must be translated into equivalent Cypher path patterns (MATCH).[^3]  
Table 3.1: Premier Text-to-SQL Dataset Benchmarks

| Dataset Name | Primary Download Link | Associated References (Paper/GitHub/Related Challenges) | Key Features & Relevance to Cypher Derivation |
| :---- | :---- | :---- | :---- |
| Spider 1.0 | ([https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view](https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view)) [^5] | Paper (EMNLP'18): arXiv:1809.08887; GitHub: taoyds/spider [^5] | De-facto standard for cross-domain complexity; essential for generalized schema conversion and rule abstraction. |
| Spider 2.0 | ([https://github.com/xlang-ai/Spider2](https://github.com/xlang-ai/Spider2)) [^5] | Paper (arXiv): arXiv:2411.07763; GitHub: xlang-ai/Spider2 [^5] | Modern, more challenging benchmark; focuses on complex logical reasoning highly transferable to graph structure identification. |
| CoSQL | [Challenge Page](https://yale-lily.github.io/cosql) [^5] | Paper (EMNLP'19); Challenge Page [^5] | Context-dependent, conversational SQL; models multi-turn, stateful query building relevant for iterative graph traversal. |
| SParC | [Challenge Page](https://yale-lily.github.io/sparc) [^5] | Paper (ACL'19); Challenge Page [^5] | Context-dependent, cross-domain generalization; highly relevant for teaching path accumulation and sequential logic in graph querying. |

## **4\. Tier II Data Source: Key Text-to-SPARQL (NL2SPARQL) Benchmarks**

SPARQL datasets offer a unique advantage for Cypher model development. Because they are derived from native graph structures (RDF triple stores), the semantic distance between SPARQL and Cypher is inherently smaller than that between SQL and Cypher. This simplifies the structural and semantic mapping required during conversion.

### **4.1 Spider4SPARQL: The Direct Conversion Bridge**

Spider4SPARQL is strategically vital because it explicitly provides a template for mapping the high complexity of the Spider dataset structure into a graph query domain. This dataset features 10,181 natural language questions and 5,693 unique, complex SPARQL queries.[^10]  
The strength of Spider4SPARQL lies in the fact that it retains the challenging, cross-domain characteristics of the original Spider dataset [^10] while converting the underlying schemas into a knowledge graph format. The project provides several auxiliary resources that are invaluable for researchers attempting conversion, including the Natural Language/SPARQL pairs, *materialized Knowledge Graphs* for the development and training sets, and the original PostgreSQL compatible data dumps of the 20 Spider dev and 146 train databases.[^11]  
This comprehensive package allows researchers to study the precise mechanism by which relational constraints (from SQL) are translated into graph constraints (in SPARQL), providing a direct methodological bridge for subsequent conversion to Cypher.  
The primary access links and references are:

* **Download Link:**([https://github.com/ckosten/Spider4SPARQL](https://github.com/ckosten/Spider4SPARQL)).[^11]  
* **References:** Citation (INPROCEEDINGS): 10386182 [^11]; arXiv: 2309.16248v2.[^10]

### **4.2 Large-Scale Knowledge Graph Datasets (LC-QuAD and QALD)**

These large-scale benchmarks demonstrate complex path construction and entity resolution over massive, established knowledge bases, providing robust training examples for graph traversal.  
**LC-QuAD 2.0** is a prominent resource, consisting of 30,000 pairs of questions and their corresponding SPARQL queries, targeting the massive structure of Wikidata and DBpedia.[^12] Because of the complexity of the underlying knowledge graphs, the questions in LC-QuAD 2.0 often require detailed sub-queries, filtering, and multi-hop paths. This inherent complexity in graph navigation logic directly translates to advanced Cypher query requirements, such as handling variable-length paths and complex filtering conditions within the MATCH and WHERE clauses.

* **Download Link:**([https://huggingface.co/datasets/mohnish/lc\_quad](https://huggingface.co/datasets/mohnish/lc_quad)).[^14]  
* **References:** Paper (ISWC 2019): dubey2017lc2; Homepage: http://lc-quad.sda.tech/.[^13]

The **QALD (Question Answering over Linked Data) Series** are recurring benchmarks often used to validate techniques for SPARQL generation, including novel approaches like Chain-of-Thought (CoT) prompting.[^6] These datasets provide critical data for training models that can generate intermediate reasoning steps, a technique that enhances the generation of precise SPARQL—and by extension, precise Cypher—queries.[^6]  
The structural similarity between SPARQL and Cypher is a major operational advantage. SPARQL uses triples (subject-predicate-object) to define relationships, while Cypher uses relationship types and directions. Both are fundamentally based on defining and matching graph topology.[^3] Consequently, converting NL2SPARQL to NL2Cypher primarily involves syntactic translation and adjusting for property graph nuances, rather than the fundamental restructuring of query logic necessary when converting complex SQL JOINs to graph path patterns.  
Table 4.1: Leading Text-to-SPARQL Dataset Benchmarks

| Dataset Name | Primary Download Link | Associated References (Paper/Homepage/GitHub) | Key Features & Relevance to Cypher Derivation |
| :---- | :---- | :---- | :---- |
| Spider4SPARQL | ([https://github.com/ckosten/Spider4SPARQL](https://github.com/ckosten/Spider4SPARQL)) [^11] | Citation: 10386182; arXiv: 2309.16248v2 [^10] | Directly derived from Spider; includes Materialized KGs and PostgreSQL data; optimal resource for studying cross-paradigm conversion strategies. |
| LC-QuAD 2.0 | [Hugging Face](https://huggingface.co/datasets/mohnish/lc_quad) [^14] | Paper (ISWC 2019): dubey2017lc2; Homepage: http://lc-quad.sda.tech/ [^13] | Large-scale dataset (30k pairs) over Wikidata/DBpedia; excellent for developing complex path-finding and entity resolution capabilities. |
| QALD Series | *Varies by specific challenge/year* | Papers (e.g., SEMANTICS 2024 for COT-SPARQL) [^6] | Benchmarks various NLQ systems; useful for testing LLM reasoning strategies (CoT) in a graph context. |

## **5\. Strategic Data Derivation and Augmentation for Cypher Models**

To successfully develop an expert Text-to-Cypher model, it is mandatory to transition from the use of native, scarce Cypher data to large-scale, high-complexity derived data from SQL and SPARQL sources. This requires a systematic understanding of the technical challenges and the implementation of quality-controlled conversion frameworks.

### **5.1 Technical Challenges in Query Translation**

Effective data derivation is complex, requiring solutions to both schema mapping and query semantic equivalence.  
The fundamental difference between relational and property graph paradigms creates the primary hurdle. Relational schemas utilize tables and foreign keys to enforce structure and link data; Cypher uses nodes, typed, directional relationships, and properties. A conversion pipeline must accurately translate explicit SQL JOIN clauses into implicit Cypher path patterns, which are visually expressed using ASCII art syntax.[^3]  
The Neo4j JDBC Driver manual itself documents the difficulty, noting that shortcomings in automated SQL-to-Cypher translation often stem not from a failure in parsing the SQL, but from the lack of an "obvious, semantically equivalent Cypher construct" for certain complex relational operations.[^15] Furthermore, Cypher queries follow a rigid, linear structure, where each clause functions as a distinct step in the progression of the query (MATCH then WHERE then RETURN), a progression distinct from the monolithic block structure common in complex SQL.[^3]

### **5.2 Existing Translation Tools and Frameworks**

Several tools and industrial frameworks demonstrate the feasibility of automated query translation, providing a starting point for data derivation pipelines.  
The **SCC (SQL to Cypher Converter)** is an open-source tool designed to migrate data and translate individual SQL queries (specifically from Microsoft SQL Server) into Cypher.[^16] While useful for understanding translation mechanisms, the SCC's operational methodology—translating one query file per cycle without analyzing the comprehensive database structure—limits its use for generating complex, semantically validated training pairs.[^16] High-fidelity semantic parsing requires global schema awareness.  
A more robust indication of feasibility is the **Neo4j JDBC Driver Translator SPI**, an industrial-grade interface for programmatic SQL-to-Cypher translation.[^15] This translator supports various SQL dialects, with POSTGRES often being a suitable choice for integration.[^15] The existence and complexity of this Service Provider Interface confirm that industrial efforts have successfully mapped many relational concepts to Cypher, while simultaneously acknowledging the inherent semantic obstacles.

### **5.3 Advanced LLM-Driven Synthetic Data Generation**

The most modern and scalable method for overcoming data scarcity is leveraging Large Language Models to assist in data synthesis and validation, thereby achieving the requisite scale and diversity of the Spider benchmarks.  
The introduction of **AutoCypher** and its **LLM-as-Database-Filter** approach is central to this strategy.[^2] This technique addresses the quality control challenge inherent in synthetic generation. Since LLMs can quickly translate natural language to various query forms, the challenge shifts to ensuring the generated query is semantically valid against the target graph schema. By using an LLM in a filtering or validation role, researchers can better align the generated Cypher query with the underlying topology, significantly mitigating the semantic errors often found in raw synthetic data.[^2]  
A complementary optimization strategy involves **schema tailoring** or minimization. Before presenting a question and the full schema to an LLM, a preparatory step can be employed to call an LLM to identify only the *minimal relevant schema* required for the query.[^17] Providing this tailored, reduced schema input to the final query generation step dramatically improves LLM performance and reduces the risk of the model hallucinating irrelevant schema elements.  
The analytical conclusion regarding data derivation is clear: the optimal path for high-quality Cypher data generation should prioritize benchmarks where the schema is already graph-oriented. Thus, the highest quality synthetic Cypher data will be derived from SPARQL datasets, specifically Spider4SPARQL and LC-QuAD, due to their higher semantic fidelity to property graphs. These resources provide the essential stepping stone to bridge the gap between NL and Cypher complexity.  
Table 5.1: Tools and Concepts for Schema/Query Translation

| Tool/Concept | Source/Reference | Function & Relevance to Model Development |
| :---- | :---- | :---- |
| SCC (SQL to Cypher Converter) | GitHub: temikfart/sql2cypher [^16] | Direct translation of MS SQL query files; provides a base for understanding translation syntax, but limited by lack of global schema context. |
| Neo4j JDBC Translator SPI | Neo4j Documentation [^15] | Industrial-grade interface for programmatic SQL-to-Cypher translation; highlights semantic equivalence challenges and supports POSTGRES dialect. |
| AutoCypher (LLM-as-Filter) | Tiwari et al. (2025) [^2] | Advanced synthetic generation method; uses LLMs to filter and align derived queries with the target graph schema, mitigating semantic errors inherent in synthetic data. |

## **6\. Conclusion and Research Trajectory**

### **6.1 Summary of Actionable Dataset Strategies**

The development of an expert Text-to-Cypher model requires a hybrid strategy leveraging the maturity of SQL and SPARQL benchmarks to supplement the limited native Cypher data.

1. **Baseline Validation:** **CypherBench** is essential for establishing the foundational accuracy and performance metrics.[^7]  
2. **Optimal Derivation Source (Semantic Fidelity):** **Spider4SPARQL** and **LC-QuAD 2.0** offer the most semantically advantageous starting points for derivation. The graph-based nature of SPARQL minimizes the structural transformation required, providing ready-made complex graph traversal examples.[^10]  
3. **Complexity Augmentation Source (Logical Depth):** **Spider 1.0/2.0** and conversational benchmarks like **SParC** and **CoSQL** provide unparalleled diversity in natural language phrasing and complex logical query structure, forcing models to generalize abstract parsing rules across schemas.[^5]  
4. **Quality Control Implementation:** Any derived dataset pipeline must incorporate schema validation mechanisms, such as the LLM-as-Filter approach utilized by AutoCypher, to guarantee that the generated Cypher queries are not only syntactically correct but also semantically valid against the target property graph schema.[^2]

### **6.2 Future Research Challenges in NL2Cypher Generalization**

While utilizing derived data solves the scarcity problem, several persistent research challenges remain for achieving robust NL2Cypher generalization:  
The model must be able to handle specialized Cypher features that lack direct, simple equivalents in SQL. This includes concepts such as optional matching, highly granular variable-length paths (which define relationship depth), and the use of graph projection for analytical queries.[^3]  
Furthermore, evaluating model performance requires metrics that go beyond simple execution accuracy. Future work must incorporate robustness evaluation benchmarks, similar to Dr.Spider used in the SQL domain, to ensure that model performance remains stable under minor perturbations or variations in the natural language input.[^5]  
Finally, the reliance on LLMs for both synthetic generation and query execution necessitates continuous optimization of prompting techniques. The success demonstrated by Chain-of-Thought (CoT) prompting in the SPARQL domain [^6] suggests that similar techniques focusing on sequential graph reasoning steps must be fully integrated into NL2Cypher pipelines to ensure the model correctly maps complex NL reasoning to the linear, step-wise structure of Cypher queries. The performance of these models will ultimately depend on their capacity to effectively ingest, reason about, and utilize the complex, topological nature of the graph schema presented in the prompt.

#### **Bibliografia**

[^1]: Cypher Generation: The Good, The Bad and The Messy | Towards Data Science, accesso eseguito il giorno dicembre 3, 2025, [https://towardsdatascience.com/cypher-generation-the-good-the-bad-and-the-messy-4ec119dd72ea/](https://towardsdatascience.com/cypher-generation-the-good-the-bad-and-the-messy-4ec119dd72ea/)  
[^2]: Mind the Query: A Benchmark Dataset towards Text2Cypher Task - ACL Anthology, accesso eseguito il giorno dicembre 3, 2025, [https://aclanthology.org/2025.emnlp-industry.133.pdf](https://aclanthology.org/2025.emnlp-industry.133.pdf)  
[^3]: Real-Time Text-to-Cypher Query Generation with Large Language ..., accesso eseguito il giorno dicembre 3, 2025, [https://www.mdpi.com/1999-5903/16/12/438](https://www.mdpi.com/1999-5903/16/12/438)  
[^4]: Beyond SELECT: A Comprehensive Taxonomy-Guided Benchmark for Real-World Text-to-SQL Translation - arXiv, accesso eseguito il giorno dicembre 3, 2025, [https://arxiv.org/html/2511.13590v2](https://arxiv.org/html/2511.13590v2)  
[^5]: Spider: Yale Semantic Parsing and Text-to-SQL Challenge, accesso eseguito il giorno dicembre 3, 2025, [https://yale-lily.github.io/spider](https://yale-lily.github.io/spider)  
[^6]: Generating SPARQL from Natural Language Using Chain-of-Thoughts Prompting - DICE Research Group, accesso eseguito il giorno dicembre 3, 2025, [https://papers.dice-research.org/2024/SEMANTICS_Cot-SPARQL/public.pdf](https://papers.dice-research.org/2024/SEMANTICS_Cot-SPARQL/public.pdf)  
[^7]: megagonlabs/cypherbench: CypherBench: Towards ... - GitHub, accesso eseguito il giorno dicembre 3, 2025, [https://github.com/megagonlabs/cypherbench](https://github.com/megagonlabs/cypherbench)  
[^8]: Text2Cypher: Bridging Natural Language and Graph Databases - arXiv, accesso eseguito il giorno dicembre 3, 2025, [https://arxiv.org/html/2412.10064v1](https://arxiv.org/html/2412.10064v1)  
[^9]: neo4j-labs/text2cypher - GitHub, accesso eseguito il giorno dicembre 3, 2025, [https://github.com/neo4j-labs/text2cypher](https://github.com/neo4j-labs/text2cypher)  
[^10]: Spider4SPARQL: A Complex Benchmark for Evaluating Knowledge Graph Question Answering Systems - arXiv, accesso eseguito il giorno dicembre 3, 2025, [https://arxiv.org/html/2309.16248v2](https://arxiv.org/html/2309.16248v2)  
[^11]: ckosten/Spider4SPARQL - GitHub, accesso eseguito il giorno dicembre 3, 2025, [https://github.com/ckosten/Spider4SPARQL](https://github.com/ckosten/Spider4SPARQL)  
[^12]: Awesome-KBQA/leaderboard/lc-quad.md at main - GitHub, accesso eseguito il giorno dicembre 3, 2025, [https://github.com/RUCAIBox/Awesome-KBQA/blob/main/leaderboard/lc-quad.md](https://github.com/RUCAIBox/Awesome-KBQA/blob/main/leaderboard/lc-quad.md)  
[^13]: README.md - Dataset Card for LC-QuAD 2.0 - Hugging Face, accesso eseguito il giorno dicembre 3, 2025, [https://huggingface.co/datasets/mohnish/lc_quad/blob/ff031e8d9af0eb32c65d00375aecf2195291930c/README.md](https://huggingface.co/datasets/mohnish/lc_quad/blob/ff031e8d9af0eb32c65d00375aecf2195291930c/README.md)  
[^14]: mohnish/lc_quad · Datasets at Hugging Face, accesso eseguito il giorno dicembre 3, 2025, [https://huggingface.co/datasets/mohnish/lc_quad](https://huggingface.co/datasets/mohnish/lc_quad)  
[^15]: SQL to Cypher translation - Neo4j JDBC Driver manual, accesso eseguito il giorno dicembre 3, 2025, [https://neo4j.com/docs/jdbc-manual/current/sql2cypher/](https://neo4j.com/docs/jdbc-manual/current/sql2cypher/)  
[^16]: temikfart/sql2cypher: Converter from SQL to Cypher. - GitHub, accesso eseguito il giorno dicembre 3, 2025, [https://github.com/temikfart/sql2cypher](https://github.com/temikfart/sql2cypher)  
[^17]: Has anyone successfully done Text to Cypher/SQL with a large schema (100 nodes, 100 relationships, 600 properties) with a small, non thinking model? : r/LLMDevs - Reddit, accesso eseguito il giorno dicembre 3, 2025, [https://www.reddit.com/r/LLMDevs/comments/1o6np55/has_anyone_successfully_done_text_to_cyphersql/](https://www.reddit.com/r/LLMDevs/comments/1o6np55/has_anyone_successfully_done_text_to_cyphersql/)