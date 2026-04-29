# **The Technical Evolution and Taxonomy of Static Word Embeddings in Machine Learning**

The history of Natural Language Processing is fundamentally a history of representation. The core challenge in enabling machines to process human language lies in the transformation of discrete, symbolic tokens into a format that permits mathematical operations and statistical inference. Static word embeddings represent a definitive epoch in this evolution, bridging the gap between the rigid, sparse representations of early computational linguistics and the dynamic, context-aware architectures that define the current era of Large Language Models. A static embedding is defined as a fixed-length vector representation where a single word is mapped to a single point in a continuous vector space, invariant to its surrounding context. While the advent of Transformer-based models like BERT and GPT has introduced dynamic contextualization, the study and application of static embeddings remain critical for resource-constrained environments, large-scale indexing, and the foundational understanding of semantic vector spaces.

## **Discrete Symbolic Foundations and the Sparsity Problem**

Before the maturation of distributed representations, the field relied on sparse models that treated words as atomic, independent units. These early techniques established the baseline for text processing but highlighted the profound need for denser, more relational models.

### **One-Hot Encoding and the Identity Representation**

One-hot encoding represents the most rudimentary technique for word vectorization, originating from the basic requirement to provide numerical identifiers for categorical variables in early machine learning algorithms.1  
**The Problem**: The primary problem addressed by one-hot encoding was the need for a non-ordinal numerical representation of discrete categories. In early NLP, machines could not ingest strings directly; they required a format where each word was distinct. However, this approach treated every word as equally distant from every other word, failing to capture any semantic or syntactic relationship. Furthermore, the dimensionality of these vectors equaled the size of the entire vocabulary, leading to extreme sparsity and the "curse of dimensionality" as corpora grew.1  
**The Mechanism**: For a given vocabulary $V$, each word $w$ is assigned a unique index $i$. The representation of $w$ is a vector of length $|V|$ where the $i$-th entry is 1 and all other entries are 0\.2 This creates a high-dimensional space where all word vectors are orthogonal, meaning the dot product (and thus cosine similarity) between any two distinct words is always zero.2

| Metric | One-Hot Encoding Characteristics |
| :---- | :---- |
| **Problem Origin** | Requirement for machine-readable categorical identifiers. |
| **Operational Logic** | Unique binary index assignment in a $ |
| **Pros** | Simplicity; perfect preservation of word identity; no training required. |
| **Cons** | Extreme sparsity; lack of similarity notion; computational inefficiency. |

### **The Bag-of-Words Model and Frequency Analysis**

As researchers moved from individual words to document-level analysis, the Bag-of-Words (BoW) model emerged as the standard for representing larger spans of text.  
**The Problem**: BoW was developed to solve the problem of document feature extraction. If a researcher needed to classify a document or determine its topic, they required a way to aggregate the information contained within its constituent words.1 BoW provided a fixed-length representation for variable-length documents.  
**The Mechanism**: BoW ignores word order and grammar, treating a document as an unordered collection of words.1 It constructs a vector where each dimension corresponds to a vocabulary term, and the value is the count of that term in the document. This allows for simple comparisons between documents using distance metrics, though it famously loses the nuance of sentence structure—treating "the dog bit the man" and "the man bit the dog" identically.1

### **TF-IDF and Informational Salience**

The realization that word frequency alone does not indicate informational value led to the development of Term Frequency-Inverse Document Frequency (TF-IDF) in the late 1950s, primarily through the work of Hans Peter Luhn.5  
**The Problem**: In simple frequency models, common functional words like "the," "is," and "of" dominate the representation because of their high occurrence, even though they convey minimal topical information.1 Search engines and retrieval systems needed a way to prioritize words that were unique and descriptive of specific documents.2  
**The Mechanism**: TF-IDF weights a term by multiplying its local frequency in a document (TF) by the log-inverse of its frequency across the entire corpus (IDF).2 The mathematical formulation is $w_{i,j} = tf_{i,j} \times \log(\frac{N}{df_i})$, where $N$ is the total documents and $df_i$ is the number of documents containing term $i$.2 This effectively "penalizes" words that appear everywhere while "rewarding" those that are specific to a subset of the corpus.5

| Feature | TF-IDF Performance Profile |
| :---- | :---- |
| **Problem Origin** | Dominance of high-frequency, low-info words in retrieval. |
| **Operational Logic** | Statistical weighting based on local count and global rarity. |
| **Pros** | Strong baseline for information retrieval; highlights topical keywords. |
| **Cons** | Disregards semantic similarity (synonyms remain distinct); sparse. |

## **The Era of Statistical Distributional Models**

The shift toward "distributed representations"—where words are represented as dense vectors of real numbers—was predicated on the distributional hypothesis: words that occur in similar contexts tend to have similar meanings.4 This period saw the transition from counting words in documents to counting words near other words.

### **Latent Semantic Analysis (LSA)**

Introduced in 1990 by Deerwester et al., Latent Semantic Analysis applied advanced linear algebra to the term-document matrix to uncover hidden (latent) relationships.8  
**The Problem**: LSA addressed the "lexical gap" problem, specifically synonymy. In standard TF-IDF retrieval, a query for "physician" would fail to find a document containing "doctor".8 LSA aimed to find a lower-dimensional space where these semantically related terms would be positioned closely together.3  
**The Mechanism**: LSA performs Singular Value Decomposition (SVD) on a large term-document matrix.8 By keeping only the top $k$ singular values and their corresponding vectors, the model projects words into a "concept space." This dimensionality reduction forces the model to aggregate terms that appear in similar documents, effectively capturing second-order associations.8

| Factor | Latent Semantic Analysis (LSA) |
| :---- | :---- |
| **Problem Origin** | Synonymy and the lexical gap in document search. |
| **Operational Logic** | SVD-based dimensionality reduction of term-document matrices. |
| **Pros** | Captures global semantics; effective for document-level similarity. |
| **Cons** | Computationally expensive; poor at word-level analogy tasks. |

### **Hyperspace Analogue to Language (HAL)**

Introduced by Lund and Burgess in 1996, HAL shifted the focus from documents to local sliding windows, more closely mimicking human language acquisition.8  
**The Problem**: Researchers realized that document-level co-occurrence was often too coarse to capture granular semantic and syntactic nuances. Meaning is often derived from the immediate neighbors of a word.11  
**The Mechanism**: HAL moves a window of size $K$ across a corpus. For each word, it records the co-occurrence of neighbor words, weighting the counts inversely to their distance from the target word.8 This creates a $|V| \times |V|$ matrix where each row is a high-dimensional vector representing the word's contextual signature.11

### **Pointwise Mutual Information (PMI) and PPMI**

As count-based models became standard, the bias toward high-frequency words remained a significant hurdle. Pointwise Mutual Information (PMI) emerged as the preferred metric to distinguish meaningful associations from random co-occurrences.12  
**The Problem**: Simple counts do not account for the base probability of words. If "the" and "apple" co-occur 1,000 times, it may be less significant than "apple" and "orchard" co-occurring 50 times, given that "the" appears billions of times in the corpus.8  
**The Mechanism**: PMI is defined as $\text{PMI}(w,c) = \log \frac{P(w,c)}{P(w)P(c)}$.12 Positive Pointwise Mutual Information (PPMI) is a variant where all negative values are replaced with zero, as negative PMI values (indicating words occur together less than chance) are often statistically unreliable in sparse data.14

## **The Neural Revolution: Predictive Static Embeddings**

In 2013, the release of Word2Vec by Tomas Mikolov and colleagues at Google marked a watershed moment for NLP. It introduced the concept of "learning" word embeddings through shallow neural networks, prioritizing the "prediction" of context over the "counting" of occurrences.1

### **Word2Vec: CBOW and Skip-gram**

Word2Vec popularized the notion that high-quality semantic vectors could be learned by training a model to solve a surrogate task: predicting a word given its context or vice versa.10  
**The Problem**: Count-based models like LSA were computationally heavy and struggled to capture fine-grained linear relationships (analogies) between words.1 There was a need for an efficient, scalable way to generate dense vectors that could encode linguistic regularities such as "king is to man as queen is to woman".10  
**The Mechanism**: Word2Vec offers two primary architectures:

1. **Continuous Bag-of-Words (CBOW)**: The model predicts a **target word** using the average of the vectors of its **surrounding context words**.16 It is generally faster to train and has slightly better accuracy for frequent words.10  
2. **Skip-gram**: The model takes a **target word** as input and predicts the **surrounding context words**.4 Skip-gram is often better at representing rare words because it treats each context-target pair as a new observation, effectively up-sampling the context of infrequent terms.7

| Feature | Word2Vec (CBOW & Skip-gram) |
| :---- | :---- |
| **Problem Origin** | Need for scalable, dense vectors capturing linear analogies. |
| **Operational Logic** | Predictive shallow neural networks using local context windows. |
| **Pros** | Fast training; captures semantic/syntactic analogies; dense vectors. |
| **Cons** | Only local context; ignores global stats; one vector per word (polysemy). |

### **Mathematical Refinement: Negative Sampling and Hierarchical Softmax**

The efficiency of Word2Vec is largely due to its optimization strategies. Calculating a full softmax over a vocabulary of millions is "very expensive".16  
**The Problem**: The "partition function" in a standard softmax requires summing over the entire vocabulary for every training step, making large-scale training impossible.14  
**The Mechanism**:

1. **Hierarchical Softmax**: Represents the vocabulary as a Huffman tree, reducing the complexity of prediction from $O(V)$ to $O(\log V)$.16  
2. **Skip-Gram with Negative Sampling (SGNS)**: Turns the multi-class prediction problem into a binary logistic regression task.14 For every "real" word-context pair (positive sample), the model is shown $k$ "noise" pairs (negative samples) where the context is chosen randomly from the corpus.12 The goal is to maximize the probability that the real pair came from the data while minimizing the probability for the noise pairs.12

### **The Levy and Goldberg Unified Theory**

In 2014, Omer Levy and Yoav Goldberg provided a theoretical bridge between the new neural predictive models and the traditional count-based models.15  
**The Problem**: There was a perceived conflict between "counting" (LSA/GloVe) and "predicting" (Word2Vec). It was unclear why Word2Vec worked so well on analogies compared to matrix factorization.12  
**The Mechanism**: Levy and Goldberg proved that SGNS is **implicitly factorizing a word-context matrix**.15 Specifically, they showed that the optimal dot product between a word and context vector in SGNS is equal to the Pointwise Mutual Information (PMI) of that pair, shifted by a global constant $\log k$, where $k$ is the number of negative samples.15 The superiority of Word2Vec on analogies was found to stem from its "weighted" nature; because frequent words appear in more training steps, the model pays more "attention" to their accurate reconstruction than SVD does for all cells in a matrix.12

| Insight | Levy & Goldberg PMI Equivalence |
| :---- | :---- |
| **Mathematical Proof** | $\vec{w} \cdot \vec{c} = \text{PMI}(w,c) - \log k$ . |
| **Significance** | Unifies count-based and prediction-based embedding theories. |
| **Application** | Enables the creation of "Shifted PPMI" matrices for better results. |

## **Global Context and Subword Granularity**

Following Word2Vec, two major innovations addressed its core deficiencies: the lack of global statistical awareness and the inability to handle words as anything other than atomic, indivisible symbols.

### **GloVe: Global Vectors for Word Representation**

Introduced by Pennington et al. at Stanford in 2014, GloVe was designed to harness the best of both count-based and predictive models.4  
**The Problem**: Word2Vec relies on separate local windows and fails to utilize the global co-occurrence statistics of the entire corpus.7 Conversely, matrix factorization models like LSA capture global stats but do poorly on analogies.17  
**The Mechanism**: GloVe is a log-bilinear regression model that trains on global word-word co-occurrence counts.4 Its unique insight is that the **ratio of co-occurrence probabilities** encodes meaning better than raw counts.8 For example, the probability of "solid" given "ice" is high, and the probability of "solid" given "steam" is low. The ratio of these two probabilities accurately characterizes the semantic relationship between "ice" and "steam".18 GloVe minimizes a weighted least squares loss function that directly targets these ratios.10

| Comparison | GloVe vs. Word2Vec |
| :---- | :---- |
| **Information Source** | Global Co-occurrence Matrix vs. Local Sliding Window. |
| **Optimization** | Weighted Least Squares vs. Stochastic Gradient Descent. |
| **Pros** | More stable representations; efficiently uses all corpus data. |
| **Cons** | High memory cost to build initial co-occurrence matrix. |

### **FastText: Subword Information and Character N-grams**

As NLP expanded to morphologically rich languages (e.g., Turkish, Kannada, Finnish), the "word-as-atom" approach became a bottleneck.7  
**The Problem**: Traditional embeddings like GloVe or Word2Vec cannot handle "Out-of-Vocabulary" (OOV) words. If a word like "unhappiness" was not in the training set, the model has no representation for it.7 Furthermore, these models do not recognize that "happy" and "happier" share a root.18  
**The Mechanism**: Developed by Facebook (FAIR), FastText represents each word as a **bag of character n-grams**.7 For a word like "apple" and $n=3$, it would learn vectors for "\<ap," "app," "ppl," "ple," "le\>".7 The final word vector is the sum of its character n-gram vectors.7 This allows FastText to generate embeddings for unseen words by summing their constituent n-grams and capturing the semantic nuances of prefixes and suffixes.7

| Capability | FastText Innovation |
| :---- | :---- |
| **Problem Origin** | OOV words and morphologically rich languages. |
| **Operational Logic** | Summation of subword/character n-gram embeddings. |
| **Pros** | Robust to typos; handles rare words; captures morphological links. |
| **Cons** | Significantly higher memory usage to store n-gram vectors. |

## **Advanced Geometry and Structural Constraints**

The standard assumption that word meanings should be embedded in Euclidean space was challenged as researchers looked to model specific linguistic structures like hierarchies and entailment.

### **Poincaré Embeddings for Latent Hierarchies**

In 2017, Nickel and Kiela introduced a new approach for learning hierarchical representations by embedding symbolic data into hyperbolic space.22  
**The Problem**: Many complex datasets, such as taxonomies (e.g., WordNet), exhibit a latent hierarchical structure.22 Euclidean space is mathematically ill-suited for this because the volume of Euclidean space grows only polynomially with radius, whereas the number of nodes in a hierarchy grows exponentially with depth.23 This leads to high distortion and the need for very high dimensions to capture the hierarchy.24  
**The Mechanism**: Poincaré embeddings use the **n-dimensional Poincaré ball**, a model of hyperbolic space with constant negative curvature.22 Hyperbolic space expands exponentially, naturally matching the growth of trees.23 In this space, the distance from the center represents hierarchical depth (nodes near the center are "roots"), and the distance between nodes represents similarity.23 This allows for extremely parsimonious (low-dimensional) representations that still capture both hierarchy and similarity with high precision.22

| Attribute | Poincaré Hyperbolic Embeddings |
| :---- | :---- |
| **Problem Origin** | Exponential node growth in hierarchies (WordNet, social graphs). |
| **Operational Logic** | Riemannian optimization in the hyperbolic Poincaré ball. |
| **Pros** | Superior capacity for hierarchical data; extremely low dimensions. |
| **Cons** | Not optimized for general-purpose semantic similarity tasks. |

### **Semantic Enrichment: Retrofitting and Counter-fitting**

Because distributional embeddings learn from unlabelled corpora, they often fail to distinguish between different types of relationships, such as synonymy and antonymy.25  
**The Problem**: In distributional space, "hot" and "cold" are often close together because they appear in similar contexts (e.g., "The weather is \[X\]").25 For tasks like sentiment analysis or machine translation, it is vital to keep synonyms close while pushing antonyms apart.25  
**The Mechanism**:

1. **Retrofitting (RF)**: A post-processing graph-based method that "nudges" pre-trained word vectors to be closer to their neighbors in a knowledge base like WordNet.25 It minimizes a distance-based loss function between the word's original distributional vector and its neighbors in the lexical resource.25  
2. **Counter-fitting (CF)**: Specifically designed to repel antonyms. It uses a contrastive objective that pulls synonyms closer while explicitly pushing antonyms beyond a certain distance margin.25  
3. **Hierarchy-fitting (HF)**: A more recent variant that distinguishes between direct and indirect hypernymy using a quadruplet loss function to better integrate taxonomic nuances.25

| Method | Enrichment Objective |
| :---- | :---- |
| **Retrofitting** | Integrate synonymy from WordNet/FrameNet into existing vectors. |
| **Counter-fitting** | Specialize vector space by explicitly repelling antonyms. |
| **LexSub** | Train projection matrices to create subspaces for specific relations. |

## **Addressing Polysemy: Multisense Static Embeddings**

A fundamental critique of static embeddings is that they assign a single vector to words with multiple meanings (polysemy), such as "bank".9  
**The Problem**: Static vectors represent a "centroid" of all a word's meanings, which may not accurately represent any of them.26 While contextual embeddings solve this dynamically, they are computationally heavy.3  
**The Mechanism**:

1. **MSSG (Multi-Sense Skip-Gram)**: Extends Word2Vec by clustering the local context of each word occurrence during training. Each word is assigned $k$ vectors, corresponding to its $k$ latent senses.26  
2. **Sense2Vec**: Incorporates supervised information like Part-of-Speech (POS) or Named Entity Recognition (NER) tags into the word string (e.g., "duck\_NOUN" vs "duck\_VERB") to create separate static vectors based on the word's grammatical function.27  
3. **LLM-Clustered Sense Embeddings (2025)**: Modern researchers have proposed extracting hundreds of contextualized embeddings from a Large Language Model (e.g., DeBERTa), clustering them, and using the cluster centroids as a "static sense dictionary" for efficient inference.26

| Approach | Multisense Mechanism |
| :---- | :---- |
| **MSSG** | Unsupervised clustering of local context windows during training. |
| **Sense2Vec** | Supervised tagging of word strings to disambiguate POS/Entity. |
| **LLM-Cluster** | Post-hoc clustering of LLM hidden states to define static senses. |

## **The Modern Resurgence: Static Embeddings in the LLM Era (2024-2025)**

In the current landscape dominated by 100B+ parameter models, static word embeddings have found a new role as high-efficiency, cost-effective proxies for large transformers.30

### **SWE4Semantics and Decontextualized LLM Embeddings**

As models scale up, the cost of processing billions of sentences becomes prohibitive. Researchers are now looking to "distill" the knowledge of LLMs back into static lookup tables.30  
**The Problem**: LLMs like LLaMA 3 or GPT-4 require massive GPU resources and high latency for simple inference.30 There is a need for "LLM-quality" representations that can run on a smartphone CPU or process massive datasets efficiently.30  
**The Mechanism**:

1. **SWE4Semantics (2025)**: This state-of-the-art technique extracts embeddings from a pre-trained Sentence Transformer, applies sentence-level Principal Component Analysis (PCA) to remove components irrelevant to overall semantics, and refines the resulting static vectors via knowledge distillation or contrastive learning.30 During inference, a sentence is encoded by simply **averaging** these refined static word vectors, which is thousands of times faster than a Transformer forward pass.30  
2. **WordLlama and Model2Vec (2024)**: These tools extract static vectors from the input layers of LLMs like LLaMA 3 or Mistral.30 They use a "Zipfian-weighted" average or SIF (Smooth Inverse Frequency) weighting to combine these static vectors into sentence representations.32  
3. **Direct LLM Extraction**: Research in 2025 has shown that decontextualized static embeddings (obtained by feeding single words into an LLM's tokenizer) perform significantly better on analogy tasks and clustering than classical models like Word2Vec.35

| Benchmark | LLM-Induced Static vs. Classical Static (2025 Findings) |
| :---- | :---- |
| **Analogy Tasks** | LLMs (LLaMA3, Gemma) outperform Word2Vec/GloVe significantly. |
| **Clustering** | LLM-extracted vectors show tighter semantic grouping. |
| **Sentence Similarity** | Specialized classical models like SimCSE often still outperform raw LLM static averages. |

## **Synthesized Chronology and Technological Transitions**

The following table provides a high-level chronological map of the techniques discussed, highlighting the conceptual shift across decades of research.

| Era | Technique Class | Key Innovation | Representative Model |
| :---- | :---- | :---- | :---- |
| **Pre-1990** | Sparse Discrete | Term Weighting | TF-IDF 5 |
| **1990-2010** | Count-Based Stat | Dimensionality Reduction | LSA / SVD 8 |
| **2013-2014** | Neural Predictive | Local Context Prediction | Word2Vec (SGNS) 4 |
| **2014-2015** | Global Distributional | Probability Ratios | GloVe 17 |
| **2016-2017** | Subword/Morphological | Character N-grams | FastText 7 |
| **2017-2018** | Geometric/Structural | Hyperbolic Geometry | Poincaré Ball 23 |
| **2024-2025** | LLM-Distilled | Transformer Distillation | SWE4Semantics 30 |

## **Future Directions and Emerging Paradigms**

As the field looks beyond 2025, static embeddings are evolving toward multimodal and cross-lingual consistency.1  
**Multimodal Static Embeddings**: Researchers are now developing static lookup tables where text, image patches, and audio fragments are embedded into a shared space.1 This allows for instantaneous cross-modal retrieval without the need for large multimodal encoders.33  
**Cross-Lingual Alignment**: The 2025 state of the art includes cross-lingual SWEs optimized for sentence representation.30 By aligning the static vector spaces of multiple languages using parallel corpora and contrastive learning, models can perform "translation-free" search across distant language pairs like English and Chinese with surprisingly high accuracy.30  
**Energy-Efficient and Ethical AI**: As sustainability becomes a core metric, static embeddings are favored for their low energy footprint.33 Furthermore, new post-processing techniques like "DirectBias" projection are being used to "de-bias" static embeddings by removing gender or racial subspaces from the learned vectors before deployment.37

## **Conclusion**

The trajectory of static word embeddings demonstrates a move from treating words as isolated tokens to understanding them as part of a complex, multidimensional semantic landscape. While the "contextual" revolution has redefined accuracy in NLP, the "static" paradigm continues to define efficiency and accessibility. The integration of LLM-scale knowledge into static lookup tables represents a full circle in the field's history: using the most complex models to create the most simple, powerful, and portable representations possible. Static embeddings remain the "connective tissue" of modern AI systems, ensuring that even as models grow in scale, their foundational building blocks remain mathematically elegant and computationally feasible.

#### **Bibliografia**

1. The Evolution of NLP: From Basic Models to Word Embeddings and Beyond \- Medium, accesso eseguito il giorno gennaio 25, 2026, [https://medium.com/@mukul.mschauhan/the-evolution-of-nlp-from-basic-models-to-word-embeddings-and-beyond-3ac164d21006](https://medium.com/@mukul.mschauhan/the-evolution-of-nlp-from-basic-models-to-word-embeddings-and-beyond-3ac164d21006)  
2. Word representation techniques in natural language processing \- WisdomGale, accesso eseguito il giorno gennaio 25, 2026, [https://www.wisdomgale.com/jcsi/index.php?fulltxt=222107\&fulltxtj=286\&fulltxtp=286-1727348712.pdf](https://www.wisdomgale.com/jcsi/index.php?fulltxt=222107&fulltxtj=286&fulltxtp=286-1727348712.pdf)  
3. From Static to Contextual: A Survey of Embedding Advances in NLP, accesso eseguito il giorno gennaio 25, 2026, [https://journal.dcircle.org/index.php/perfect/article/download/77/58/389](https://journal.dcircle.org/index.php/perfect/article/download/77/58/389)  
4. Word embeddings in NLP: A Complete Guide \- Turing, accesso eseguito il giorno gennaio 25, 2026, [https://www.turing.com/kb/guide-on-word-embeddings-in-nlp](https://www.turing.com/kb/guide-on-word-embeddings-in-nlp)  
5. Dense vs Sparse: A Short, Chaotic, and Honest History of RAG Retrievers (From TF-IDF to ColBert) | by Pınar Ece Aktan | Medium, accesso eseguito il giorno gennaio 25, 2026, [https://medium.com/@pinareceaktan/dense-vs-sparse-a-short-chaotic-and-honest-history-of-rag-retrievers-from-tf-idf-to-colbert-7bb3a60414a1](https://medium.com/@pinareceaktan/dense-vs-sparse-a-short-chaotic-and-honest-history-of-rag-retrievers-from-tf-idf-to-colbert-7bb3a60414a1)  
6. From Words to Vectors: The Evolution of Word Embedding Techniques in Natural Language Processing \- Oreate AI Blog, accesso eseguito il giorno gennaio 25, 2026, [http://oreateai.com/blog/from-words-to-vectors-the-evolution-of-word-embedding-techniques-in-natural-language-processing/39567c5fb41f6e2c6cd36d960a8960b0](http://oreateai.com/blog/from-words-to-vectors-the-evolution-of-word-embedding-techniques-in-natural-language-processing/39567c5fb41f6e2c6cd36d960a8960b0)  
7. Introduction to word embeddings – Word2Vec, Glove, FastText and ELMo \- Alpha Quantum, accesso eseguito il giorno gennaio 25, 2026, [https://www.alpha-quantum.com/blog/word-embeddings/introduction-to-word-embeddings-word2vec-glove-fasttext-and-elmo/](https://www.alpha-quantum.com/blog/word-embeddings/introduction-to-word-embeddings-word2vec-glove-fasttext-and-elmo/)  
8. \[1901.09069\] Word Embeddings: A Survey \- ar5iv \- arXiv, accesso eseguito il giorno gennaio 25, 2026, [https://ar5iv.labs.arxiv.org/html/1901.09069](https://ar5iv.labs.arxiv.org/html/1901.09069)  
9. \[D\] What are the main differences between the word embeddings of ELMo, BERT, Word2vec, and GloVe? : r/MachineLearning \- Reddit, accesso eseguito il giorno gennaio 25, 2026, [https://www.reddit.com/r/MachineLearning/comments/aptwxm/d\_what\_are\_the\_main\_differences\_between\_the\_word/](https://www.reddit.com/r/MachineLearning/comments/aptwxm/d_what_are_the_main_differences_between_the_word/)  
10. Word Embedding Explained — Word2Vec GloVe, FastText | by Neri Van Otten \- Medium, accesso eseguito il giorno gennaio 25, 2026, [https://medium.com/@neri.vvo/word-embedding-a-powerful-tool-word2vec-glove-fasttext-dd6e2171d5](https://medium.com/@neri.vvo/word-embedding-a-powerful-tool-word2vec-glove-fasttext-dd6e2171d5)  
11. (PDF) Probabilistic hyperspace analogue to language \- ResearchGate, accesso eseguito il giorno gennaio 25, 2026, [https://www.researchgate.net/publication/221301239\_Probabilistic\_hyperspace\_analogue\_to\_language](https://www.researchgate.net/publication/221301239_Probabilistic_hyperspace_analogue_to_language)  
12. Neural Word Embedding as Implicit Matrix Factorization \- NIPS, accesso eseguito il giorno gennaio 25, 2026, [https://proceedings.neurips.cc/paper/5477-neural-word-embedding-as-implicit-matrix-factorization.pdf](https://proceedings.neurips.cc/paper/5477-neural-word-embedding-as-implicit-matrix-factorization.pdf)  
13. Continuous Word Embedding Fusion via Spectral Decomposition \- ACL Anthology, accesso eseguito il giorno gennaio 25, 2026, [https://aclanthology.org/K18-1002.pdf](https://aclanthology.org/K18-1002.pdf)  
14. Proceedings of the 55th Annual Meeting of the Association for Computational Linguistics \- ACL Anthology, accesso eseguito il giorno gennaio 25, 2026, [https://aclanthology.org/P17-1185.pdf](https://aclanthology.org/P17-1185.pdf)  
15. Neural word embedding as implicit matrix factorization \- Tel Aviv University, accesso eseguito il giorno gennaio 25, 2026, [https://cris.tau.ac.il/en/publications/neural-word-embedding-as-implicit-matrix-factorization/](https://cris.tau.ac.il/en/publications/neural-word-embedding-as-implicit-matrix-factorization/)  
16. Lecture 4: Static word embeddings, accesso eseguito il giorno gennaio 25, 2026, [https://courses.grainger.illinois.edu/cs546/sp2020/Slides/Lecture04.pdf](https://courses.grainger.illinois.edu/cs546/sp2020/Slides/Lecture04.pdf)  
17. Word Embedding: GloVe \- Sahil \- Medium, accesso eseguito il giorno gennaio 25, 2026, [https://sahiltinky94.medium.com/word-embedding-glove-dd27f630c663](https://sahiltinky94.medium.com/word-embedding-glove-dd27f630c663)  
18. Word2Vec, GloVe, and FastText, Explained | Towards Data Science, accesso eseguito il giorno gennaio 25, 2026, [https://towardsdatascience.com/word2vec-glove-and-fasttext-explained-215a5cd4c06f/](https://towardsdatascience.com/word2vec-glove-and-fasttext-explained-215a5cd4c06f/)  
19. Neural Word Embedding as Implicit Matrix Factorization \- NIPS, accesso eseguito il giorno gennaio 25, 2026, [https://papers.nips.cc/paper/5477-neural-word-embedding-as-implicit-matrix-factorization](https://papers.nips.cc/paper/5477-neural-word-embedding-as-implicit-matrix-factorization)  
20. Neural Word Embedding as Implicit Matrix Factorization \- NIPS, accesso eseguito il giorno gennaio 25, 2026, [https://papers.nips.cc/paper/5477-neural-word-embedding-as-implicit-matrix-factorization.pdf](https://papers.nips.cc/paper/5477-neural-word-embedding-as-implicit-matrix-factorization.pdf)  
21. (PDF) Survey of Word Embedding Techniques in Deep Learning-Based NLP, accesso eseguito il giorno gennaio 25, 2026, [https://www.researchgate.net/publication/399452972\_Survey\_of\_Word\_Embedding\_Techniques\_in\_Deep\_Learning-Based\_NLP](https://www.researchgate.net/publication/399452972_Survey_of_Word_Embedding_Techniques_in_Deep_Learning-Based_NLP)  
22. Poincaré Embeddings for Learning Hierarchical Representations \- NIPS, accesso eseguito il giorno gennaio 25, 2026, [https://papers.nips.cc/paper/7213-poincare-embeddings-for-learning-hierarchical-representations](https://papers.nips.cc/paper/7213-poincare-embeddings-for-learning-hierarchical-representations)  
23. Poincaré Embeddings for Learning Hierarchical ... \- arXiv, accesso eseguito il giorno gennaio 25, 2026, [https://arxiv.org/pdf/1705.08039](https://arxiv.org/pdf/1705.08039)  
24. \[1705.08039\] Poincaré Embeddings for Learning Hierarchical Representations \- arXiv, accesso eseguito il giorno gennaio 25, 2026, [https://arxiv.org/abs/1705.08039](https://arxiv.org/abs/1705.08039)  
25. Semantic enrichment of neural word embeddings: Leveraging ..., accesso eseguito il giorno gennaio 25, 2026, [https://resolve.cambridge.org/core/journals/natural-language-processing/article/semantic-enrichment-of-neural-word-embeddings-leveraging-taxonomic-similarity-for-enhanced-distributional-semantics/09D7B4F2C73301E31D7514A69C19C953](https://resolve.cambridge.org/core/journals/natural-language-processing/article/semantic-enrichment-of-neural-word-embeddings-leveraging-taxonomic-similarity-for-enhanced-distributional-semantics/09D7B4F2C73301E31D7514A69C19C953)  
26. Multi-Sense Embeddings for Language Models and Knowledge Distillation \- ACL Anthology, accesso eseguito il giorno gennaio 25, 2026, [https://aclanthology.org/2025.findings-acl.691.pdf](https://aclanthology.org/2025.findings-acl.691.pdf)  
27. \[1511.06388\] sense2vec \- A Fast and Accurate Method for Word Sense Disambiguation In Neural Word Embeddings \- arXiv, accesso eseguito il giorno gennaio 25, 2026, [https://arxiv.org/abs/1511.06388](https://arxiv.org/abs/1511.06388)  
28. Ultimate Guide to Static and Contextual Embeddings | Prompts.ai, accesso eseguito il giorno gennaio 25, 2026, [https://www.prompts.ai/blog/ultimate-guide-to-static-and-contextual-embeddings](https://www.prompts.ai/blog/ultimate-guide-to-static-and-contextual-embeddings)  
29. Multi-Sense Embeddings for Language Models and Knowledge Distillation \- arXiv, accesso eseguito il giorno gennaio 25, 2026, [https://arxiv.org/abs/2504.06036](https://arxiv.org/abs/2504.06036)  
30. Static Word Embeddings for Sentence Semantic Representation \- arXiv, accesso eseguito il giorno gennaio 25, 2026, [https://arxiv.org/html/2506.04624v1](https://arxiv.org/html/2506.04624v1)  
31. Revisiting Word Embeddings in the LLM Era \- arXiv, accesso eseguito il giorno gennaio 25, 2026, [https://arxiv.org/html/2502.19607v1](https://arxiv.org/html/2502.19607v1)  
32. Static Word Embeddings for Sentence Semantic Representation \- ACL Anthology, accesso eseguito il giorno gennaio 25, 2026, [https://aclanthology.org/2025.emnlp-main.316.pdf](https://aclanthology.org/2025.emnlp-main.316.pdf)  
33. Top Embedding Models in 2025 — The Complete Guide \- Artsmart.ai, accesso eseguito il giorno gennaio 25, 2026, [https://artsmart.ai/blog/top-embedding-models-in-2025/](https://artsmart.ai/blog/top-embedding-models-in-2025/)  
34. twadada/swe4semantics \- GitHub, accesso eseguito il giorno gennaio 25, 2026, [https://github.com/twadada/swe4semantics](https://github.com/twadada/swe4semantics)  
35. Revisiting Word Embeddings in the LLM Era \- ACL Anthology, accesso eseguito il giorno gennaio 25, 2026, [https://aclanthology.org/2025.ijcnlp-long.145/](https://aclanthology.org/2025.ijcnlp-long.145/)  
36. Revisiting Word Embeddings in the LLM Era \- arXiv, accesso eseguito il giorno gennaio 25, 2026, [https://arxiv.org/html/2402.11094v3](https://arxiv.org/html/2402.11094v3)  
37. LLM-Based Language Analysis \- Emergent Mind, accesso eseguito il giorno gennaio 25, 2026, [https://www.emergentmind.com/topics/large-language-model-llm-based-analysis](https://www.emergentmind.com/topics/large-language-model-llm-based-analysis)