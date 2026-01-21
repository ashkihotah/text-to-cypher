User: Can you explain me mathematically and formally why there is the necessity to:
1. normalize computed embeddings in Model2VecEmbeddings
2. add distance_strategy=DistanceStrategy.COSINE and normalize_L2=True to langchain FAISS
I'm a computer science master student in artificial intelligence, so you can use formal language

GitHub Copilot:
# Mathematical Foundation for Cosine Similarity in FAISS

## 1. Why Normalize Embeddings in Model2VecEmbeddings

### Cosine Similarity Definition

Cosine similarity between two vectors **u**, **v** ∈ ℝⁿ is defined as:

```
cos(θ) = (u · v) / (||u|| ||v||)
```

where:
- `u · v` is the dot product: `Σᵢ uᵢvᵢ`
- `||u|| = √(Σᵢ uᵢ²)` is the L2 norm (Euclidean norm)
- The result is bounded: `cos(θ) ∈ [-1, 1]`

### Normalized Vectors and Inner Product

When vectors are L2-normalized (unit vectors):

```
u' = u / ||u||,  v' = v / ||v||
```

The cosine similarity reduces to the dot product:

```
cos(θ) = u' · v'
```

This is computationally efficient because:
- **O(n)** multiplication vs **O(n) + O(√n)** for unnormalized
- No division needed at query time
- FAISS can use optimized inner product search directly

## 2. Why Normalization is Required: Why Use `DistanceStrategy.COSINE` and `normalize_L2=True`

### FAISS Distance Metrics

FAISS supports several similarity metrics:

1. **METRIC_INNER_PRODUCT**: Computes `u · v`
2. **METRIC_L2**: Computes squared Euclidean distance `||u - v||²`

### Relationship Between Metrics

For **normalized vectors** (||u|| = ||v|| = 1), there's an equivalence:

```
||u - v||² = ||u||² + ||v||² - 2(u · v)
           = 1 + 1 - 2(u · v)
           = 2(1 - u · v)
```

Therefore:

```
u · v = 1 - ||u - v||²/2
```

Since `u · v = cos(θ)` for unit vectors:

```
cos(θ) = 1 - ||u - v||²/2
```

Or equivalently:

```
||u - v||² = 2(1 - cos(θ))
```

# Langchain FAISS implementation details

User: Can you deeply and formally explain how langchain has implemented:
1. first the base class with all distances, relevance and similarity functions focusing also on COSINE similarity between -1 and 1
2. and then how FAISS sublclass was implemented

GitHub Copilot:
# LangChain VectorStore Architecture: Distance Metrics & Relevance Functions

## 1. Base VectorStore Class Architecture

### 1.1 Distance-to-Relevance Mapping Philosophy

LangChain's `VectorStore` base class (in base.py) implements a **two-stage architecture**:

1. **Distance Stage**: Vector stores compute raw distance/similarity metrics
2. **Relevance Stage**: Distance scores are normalized to `[0, 1]` relevance scores

This separation allows:
- Vector stores to use their native distance metrics
- Consistent API across different distance strategies
- User-facing relevance scores that are interpretable

### 1.2 Three Canonical Relevance Score Functions

The base class defines three static methods for distance-to-relevance conversion:

#### **Euclidean Distance Relevance**

```python
@staticmethod
def _euclidean_relevance_score_fn(distance: float) -> float:
    return 1.0 - distance / math.sqrt(2)
```

**Mathematical Foundation**:
- For **unit-normalized embeddings** (L2 norm = 1):
  ```
  ||u - v||² = ||u||² + ||v||² - 2(u · v)
             = 1 + 1 - 2cos(θ)
             = 2(1 - cos(θ))
  
  ||u - v|| = √(2(1 - cos(θ)))
  ```
- Maximum Euclidean distance for unit vectors: `√2` (when `cos(θ) = -1`)
- Minimum distance: `0` (when `cos(θ) = 1`)

**Mapping**:
```
relevance = 1 - d/√2 where d ∈ [0, √2]
```
- `d = 0` → `relevance = 1` (identical)
- `d = √2` → `relevance = 0` (opposite)

#### **Cosine Distance Relevance**

```python
@staticmethod
def _cosine_relevance_score_fn(distance: float) -> float:
    return 1.0 - distance
```

**Mathematical Foundation**:

Cosine **distance** is defined as:
```
d_cos = 1 - cos(θ) where cos(θ) ∈ [-1, 1]
```

Therefore:
```
d_cos ∈ [0, 2]
```
- `cos(θ) = 1` → `d_cos = 0` (identical)
- `cos(θ) = -1` → `d_cos = 2` (opposite)

**Mapping to Relevance**:
```
relevance = 1 - d_cos = 1 - (1 - cos(θ)) = cos(θ)
```

**Critical Assumption**: This assumes the vector store returns cosine **distance** in `[0, 2]`, not cosine similarity in `[-1, 1]`.

#### **Max Inner Product Relevance**

```python
@staticmethod
def _max_inner_product_relevance_score_fn(distance: float) -> float:
    if distance > 0:
        return 1.0 - distance
    return -1.0 * distance
```

**Mathematical Foundation**:

FAISS's `METRIC_INNER_PRODUCT` actually computes **negative inner product** for distance:
```
d_IP = -u · v
```

For **normalized vectors**:
```
d_IP = -cos(θ) where cos(θ) ∈ [-1, 1]
```

Therefore `d_IP ∈ [-1, 1]`.

**Mapping Logic**:
```python
if d_IP > 0:  # Original inner product was negative
    relevance = 1 - d_IP
else:         # Original inner product was positive
    relevance = -d_IP = u · v = cos(θ)
```

This ensures:
- `u · v = 1` → `d_IP = -1` → `relevance = 1`
- `u · v = -1` → `d_IP = 1` → `relevance = 0`

### 1.3 Similarity Search with Relevance Scores

The key method implementing the two-stage pipeline:

```python
def _similarity_search_with_relevance_scores(
    self, query: str, k: int = 4, **kwargs: Any
) -> list[tuple[Document, float]]:
    
    # Stage 1: Get distance function
    relevance_score_fn = self._select_relevance_score_fn()
    
    # Stage 2: Get raw distances from subclass
    docs_and_scores = self.similarity_search_with_score(query, k, **kwargs)
    
    # Stage 3: Apply relevance transformation
    return [(doc, relevance_score_fn(score)) for doc, score in docs_and_scores]
```

**Flow**:
1. `_select_relevance_score_fn()` → returns appropriate transformation
2. `similarity_search_with_score()` → subclass provides raw distances
3. Apply `relevance_score_fn` element-wise

### 1.4 Abstract Method Contract

The base class defines:

```python
@abstractmethod
def similarity_search_with_score(
    self, *args: Any, **kwargs: Any
) -> list[tuple[Document, float]]:
    """Return docs with DISTANCE scores (not relevance)."""
    raise NotImplementedError
```

**Contract**: Subclasses must return **raw distance metrics** from their native implementation.

---

## 2. FAISS Subclass Implementation

### 2.1 Distance Strategy Enumeration

From `langchain_community.vectorstores.utils`:

```python
class DistanceStrategy(str, Enum):
    EUCLIDEAN_DISTANCE = "EUCLIDEAN_DISTANCE"
    MAX_INNER_PRODUCT = "MAX_INNER_PRODUCT"
    COSINE = "COSINE"
```

### 2.2 FAISS Index Type Selection

In `FAISS.__from()`:

```python
if distance_strategy == DistanceStrategy.MAX_INNER_PRODUCT:
    index = faiss.IndexFlatIP(len(embeddings[0]))  # Inner Product
else:
    index = faiss.IndexFlatL2(len(embeddings[0]))  # L2 (Euclidean²)
```

**Key Observation**: 
- `DistanceStrategy.COSINE` uses `IndexFlatL2`, **not** a dedicated cosine index
- This is why normalization is critical

### 2.3 The Normalization Mechanism

#### **During Index Construction** (`__add` method):

```python
def __add(self, texts: Iterable[str], embeddings: Iterable[List[float]], ...) -> List[str]:
    faiss = dependable_faiss_import()
    
    # Convert to numpy array
    vector = np.array(embeddings, dtype=np.float32)
    
    # Critical: L2 normalization for COSINE strategy
    if self._normalize_L2:
        faiss.normalize_L2(vector)
    
    # Add to index (uses METRIC_L2 or METRIC_IP internally)
    self.index.add(vector)
```

**Mathematical Effect** (for `DistanceStrategy.COSINE`):

Given embeddings **e₁**, **e₂**, ..., **eₙ** ∈ ℝᵈ:

1. **Normalization**:
   ```
   e'ᵢ = eᵢ / ||eᵢ||₂
   ```

2. **L2 Distance Between Normalized Vectors**:
   ```
   ||e'ᵢ - e'ⱼ||² = ||e'ᵢ||² + ||e'ⱼ||² - 2(e'ᵢ · e'ⱼ)
                  = 1 + 1 - 2cos(θᵢⱼ)
                  = 2(1 - cos(θᵢⱼ))
   ```

3. **Therefore**:
   ```
   cos(θᵢⱼ) = 1 - ||e'ᵢ - e'ⱼ||²/2
   ```

#### **During Query** (`similarity_search_with_score_by_vector`):

```python
def similarity_search_with_score_by_vector(
    self, embedding: List[float], k: int = 4, **kwargs: Any
) -> List[Tuple[Document, float]]:
    faiss = dependable_faiss_import()
    
    # Query embedding
    vector = np.array([embedding], dtype=np.float32)
    
    # CRITICAL: Normalize query the same way
    if self._normalize_L2:
        faiss.normalize_L2(vector)
    
    # FAISS search returns (distances, indices)
    scores, indices = self.index.search(vector, k)
    
    # scores[0][j] contains L2² distance for EUCLIDEAN
    # or -inner_product for MAX_INNER_PRODUCT
    docs = [(doc, scores[0][j]) for j, i in enumerate(indices[0]) if i != -1]
    
    return docs
```

**Return Values**:
- For `IndexFlatL2`: Returns **squared** L2 distance `||u - v||²`
- For `IndexFlatIP`: Returns **negative** inner product `-u · v`

### 2.4 Relevance Score Selection

```python
def _select_relevance_score_fn(self) -> Callable[[float], float]:
    if self.override_relevance_score_fn is not None:
        return self.override_relevance_score_fn
    
    if self.distance_strategy == DistanceStrategy.MAX_INNER_PRODUCT:
        return self._max_inner_product_relevance_score_fn
    elif self.distance_strategy == DistanceStrategy.EUCLIDEAN_DISTANCE:
        return self._euclidean_relevance_score_fn
    elif self.distance_strategy == DistanceStrategy.COSINE:
        return self._cosine_relevance_score_fn
    else:
        raise ValueError("Unknown distance strategy")
```

### 2.5 Complete COSINE Strategy Pipeline

Let's trace a complete query with `DistanceStrategy.COSINE` and `normalize_L2=True`:

#### **Step 1**: Index Construction
```python
embeddings = [[0.6, 0.8], [0.8, 0.6]]  # Example
vector = np.array(embeddings)
faiss.normalize_L2(vector)
# vector = [[0.6, 0.8], [0.8, 0.6]] (already normalized in this case)
index = faiss.IndexFlatL2(2)
index.add(vector)
```

#### **Step 2**: Query Processing
```python
query_embedding = [0.6, 0.8]
query_vector = np.array([query_embedding])
faiss.normalize_L2(query_vector)
# query_vector = [[0.6, 0.8]]

scores, indices = index.search(query_vector, k=2)
# For first doc: ||[0.6,0.8] - [0.6,0.8]||² = 0
# For second doc: ||[0.6,0.8] - [0.8,0.6]||² = 2(0.6-0.8)² = 0.08
```

#### **Step 3**: Distance to Cosine Similarity
```python
# scores = [[0.0, 0.08]]

# Using relationship: ||u-v||² = 2(1 - cos(θ))
# cos(θ) = 1 - ||u-v||²/2

cos_similarity_0 = 1 - 0.0/2 = 1.0
cos_similarity_1 = 1 - 0.08/2 = 0.96
```

#### **Step 4**: Cosine Distance Calculation

**FAISS returns squared L2 distance**, but `_cosine_relevance_score_fn` expects **cosine distance**!

**The Issue**: There's a **mismatch** in the current implementation:

```python
# FAISS returns: d_L2² = 2(1 - cos(θ))
# But _cosine_relevance_score_fn expects: d_cos = 1 - cos(θ)

# Current (incorrect) transformation:
relevance = 1 - d_L2²  # WRONG!

# Should be:
d_cos = d_L2² / 2  # Convert squared L2 to cosine distance
relevance = 1 - d_cos = 1 - (1 - cos(θ)) = cos(θ)
```

### 2.6 The Actual Implementation in `_similarity_search_with_relevance_scores`

Looking at FAISS's override:

```python
def _similarity_search_with_relevance_scores(
    self, query: str, k: int = 4, **kwargs: Any
) -> List[Tuple[Document, float]]:
    
    relevance_score_fn = self._select_relevance_score_fn()
    
    docs_and_scores = self.similarity_search_with_score(query, k, **kwargs)
    
    docs_and_rel_scores = [
        (doc, relevance_score_fn(score)) for doc, score in docs_and_scores
    ]
    return docs_and_rel_scores
```

For `DistanceStrategy.COSINE`:
- `similarity_search_with_score` returns: `d_L2² = 2(1 - cos(θ)) ∈ [0, 4]`
- `_cosine_relevance_score_fn(d)` returns: `1 - d`

**Result**:
```
relevance = 1 - 2(1 - cos(θ))
         = 1 - 2 + 2cos(θ)
         = -1 + 2cos(θ)
         = 2cos(θ) - 1
```

For `cos(θ) ∈ [-1, 1]`:
```
relevance ∈ [-3, 1]  # NOT [0, 1]!
```

### 2.7 Why It Works in Practice

**The Critical Assumption**: Most embeddings models (OpenAI, Sentence Transformers, Model2Vec) produce **non-negative cosine similarities** in practice:
- `cos(θ) ∈ [0, 1]` for most real queries

Under this assumption:
```
d_L2² ∈ [0, 2]  # Since cos(θ) ∈ [0, 1]
relevance = 1 - d_L2² ∈ [-1, 1]
```

And the warning triggers:
```python
if any(similarity < 0.0 or similarity > 1.0 for _, similarity in docs_and_similarities):
    warnings.warn("Relevance scores must be between 0 and 1, got ...")
```

---

## 3. The Correct Implementation

### 3.1 What Should Happen

For **normalized embeddings** with `DistanceStrategy.COSINE`:

```python
@staticmethod
def _cosine_relevance_score_fn_corrected(squared_l2_distance: float) -> float:
    """Convert squared L2 distance to cosine similarity.
    
    Given: d² = 2(1 - cos(θ))
    Solve: cos(θ) = 1 - d²/2
    """
    return 1.0 - squared_l2_distance / 2.0
```

### 3.2 Why LangChain's Current Implementation "Works"

The current implementation:
```python
return 1.0 - distance
```

Actually computes:
```
relevance = 1 - 2(1 - cos(θ)) = 2cos(θ) - 1
```

This is a **linear transformation** of cosine similarity:
```
f(x) = 2x - 1 where x = cos(θ)
```

**Properties**:
- Preserves ordering (monotonic)
- Maps `[0, 1]` → `[-1, 1]` (matches cosine similarity range)
- Still differentiates documents correctly

However, it **violates the stated contract** that relevance ∈ `[0, 1]`.

---

## 4. Summary Table

| Component | Raw Metric | Range | Relevance Function | Output Range |
|-----------|-----------|-------|-------------------|--------------|
| **Euclidean (normalized)** | `√(2(1-cos(θ)))` | `[0, √2]` | `1 - d/√2` | `[0, 1]` ✓ |
| **Inner Product (normalized)** | `-cos(θ)` | `[-1, 1]` | Piecewise | `[0, 1]` ✓ |
| **Cosine (FAISS, current)** | `2(1-cos(θ))` | `[0, 4]` | `1 - d` | `[-3, 1]` ✗ |
| **Cosine (FAISS, corrected)** | `2(1-cos(θ))` | `[0, 4]` | `1 - d/2` | `[0, 1]` ✓ |

The **key insight**: FAISS with `DistanceStrategy.COSINE` uses L2 distance on normalized vectors, which requires division by 2 to recover true cosine similarity.

User: So is this an implementation error in langchain? And if i want cosine similarities between [-1, 1] how can i fix it? List me all possible fixes grouped by:
1. modifying langchain library/packages components
2. modifying external code in my local project that fixes this internal langchain bug

GitHub Copilot:

# Is This a LangChain Bug?

**Yes and No**:
- **Yes**: The `_cosine_relevance_score_fn` doesn't correctly convert FAISS's squared L2 distance to cosine similarity
- **No**: The documentation states relevance scores should be in `[0, 1]`, not `[-1, 1]`

However, if you want **true cosine similarity in `[-1, 1]`**, here are all possible fixes:

---

## 1. Fixes by Modifying LangChain Library Components

### Fix 1.1: Patch `_cosine_relevance_score_fn` in VectorStore Base Class

````python
@staticmethod
def _cosine_relevance_score_fn(distance: float) -> float:
    """Convert squared L2 distance to cosine similarity.
    
    For normalized vectors: d² = 2(1 - cos(θ))
    Therefore: cos(θ) = 1 - d²/2
    
    Returns:
        Cosine similarity in [-1, 1]
    """
    return 1.0 - distance / 2.0  # Changed from: 1.0 - distance
````

**Pros**: Fixes root cause
**Cons**: Modifies core LangChain package, breaks on updates

### Fix 1.2: Override in FAISS Class Specifically

````python
class FAISS(VectorStore):
    # ...existing code...
    
    @staticmethod
    def _cosine_relevance_score_fn(distance: float) -> float:
        """Convert FAISS squared L2 distance to cosine similarity.
        
        FAISS with IndexFlatL2 on normalized vectors returns d² = 2(1 - cos(θ))
        """
        return 1.0 - distance / 2.0
````

**Pros**: More targeted fix
**Cons**: Still requires library modification

### Fix 1.3: Add Squared L2 to Cosine Distance Strategy

````python
class DistanceStrategy(str, Enum):
    EUCLIDEAN_DISTANCE = "EUCLIDEAN_DISTANCE"
    MAX_INNER_PRODUCT = "MAX_INNER_PRODUCT"
    COSINE = "COSINE"
    COSINE_SQUARED_L2 = "COSINE_SQUARED_L2"  # New strategy
````

````python
@staticmethod
def _cosine_squared_l2_relevance_score_fn(squared_distance: float) -> float:
    """For FAISS IndexFlatL2 with normalized embeddings."""
    return 1.0 - squared_distance / 2.0

def _select_relevance_score_fn(self) -> Callable[[float], float]:
    # ...existing code...
    elif self.distance_strategy == DistanceStrategy.COSINE_SQUARED_L2:
        return self._cosine_squared_l2_relevance_score_fn
````

**Pros**: Most elegant, preserves existing behavior
**Cons**: Requires changes across multiple files

---

## 2. Fixes by Modifying External Code (Your Project)

### Fix 2.1: Custom FAISS Wrapper Class (Recommended)

````python
import numpy as np
from typing import List, Tuple, Callable
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

class CosineSimFAISS(FAISS):
    """FAISS wrapper that returns true cosine similarity in [-1, 1]."""
    
    @staticmethod
    def _cosine_relevance_score_fn(squared_l2_distance: float) -> float:
        """Convert FAISS squared L2 distance to cosine similarity.
        
        For normalized vectors: d² = 2(1 - cos(θ))
        Therefore: cos(θ) = 1 - d²/2
        
        Args:
            squared_l2_distance: FAISS's squared L2 distance
            
        Returns:
            Cosine similarity in [-1, 1]
        """
        return 1.0 - squared_l2_distance / 2.0
    
    def similarity_search_with_cosine_scores(
        self, 
        query: str, 
        k: int = 4,
        **kwargs
    ) -> List[Tuple[Document, float]]:
        """Search and return documents with cosine similarity scores in [-1, 1].
        
        Returns:
            List of (Document, cosine_similarity) tuples
        """
        docs_and_distances = self.similarity_search_with_score(query, k, **kwargs)
        
        # Convert squared L2 distances to cosine similarities
        docs_and_similarities = [
            (doc, self._cosine_relevance_score_fn(distance))
            for doc, distance in docs_and_distances
        ]
        
        return docs_and_similarities
````

**Usage**:

````python
from text2cypher.indexes import Model2VecEmbeddings, CosineSimFAISS

class Text2CypherToolkit:
    def create_indexes(self, db: str) -> None:
        query = "CALL db.labels() YIELD label RETURN label"
        labels = [record['label'] for record in self.neo4j.query(query)]
        
        self.node_index = CosineSimFAISS.from_texts(
            texts=labels,
            embedding=self.embedding_model,
            distance_strategy=DistanceStrategy.COSINE,
            normalize_L2=True
        )
        
        # Use new method for cosine similarity in [-1, 1]
        results = self.node_index.similarity_search_with_cosine_scores("company", k=5)
        for doc, sim in results:
            print(f"{doc.page_content}: {sim:.4f}")  # sim ∈ [-1, 1]
````

**Pros**: 
- No library modification
- Clean, reusable
- Type-safe

**Cons**: Requires using custom method name

### Fix 2.2: Override `_select_relevance_score_fn` via Inheritance

````python
from typing import Callable
from langchain_community.vectorstores import FAISS

class CosineSimFAISS(FAISS):
    """FAISS that correctly implements cosine similarity."""
    
    def _select_relevance_score_fn(self) -> Callable[[float], float]:
        """Override to return correct cosine similarity function."""
        if self.override_relevance_score_fn is not None:
            return self.override_relevance_score_fn
        
        # Only override for COSINE strategy
        if self.distance_strategy == DistanceStrategy.COSINE:
            return lambda d: 1.0 - d / 2.0  # Correct transformation
        
        # Use parent implementation for other strategies
        return super()._select_relevance_score_fn()
````

**Usage**:

````python
self.node_index = CosineSimFAISS.from_texts(
    texts=labels,
    embedding=self.embedding_model,
    distance_strategy=DistanceStrategy.COSINE,
    normalize_L2=True
)

# Now similarity_search_with_relevance_scores returns cosine sim in [-1, 1]
results = self.node_index.similarity_search_with_relevance_scores("company", k=5)
````

**Pros**: 
- Transparent drop-in replacement
- Uses standard LangChain API

**Cons**: Relies on internal LangChain method

### Fix 2.3: Custom Relevance Function via Constructor

````python
def cosine_similarity_score_fn(squared_l2_distance: float) -> float:
    """Convert squared L2 to cosine similarity."""
    return 1.0 - squared_l2_distance / 2.0

# Create index with custom relevance function
self.node_index = FAISS.from_texts(
    texts=labels,
    embedding=self.embedding_model,
    distance_strategy=DistanceStrategy.COSINE,
    normalize_L2=True,
    relevance_score_fn=cosine_similarity_score_fn  # Override default
)
````

**Pros**: 
- Minimal code
- Uses built-in override mechanism

**Cons**: 
- `relevance_score_fn` parameter may not exist in all LangChain versions
- Less discoverable

### Fix 2.4: Post-Processing Wrapper Function

````python
from typing import List, Tuple
from langchain_core.documents import Document

def search_with_cosine_similarity(
    faiss_index: FAISS,
    query: str,
    k: int = 4,
    **kwargs
) -> List[Tuple[Document, float]]:
    """Wrapper that converts FAISS distances to true cosine similarities.
    
    Args:
        faiss_index: FAISS index with COSINE strategy and normalize_L2=True
        query: Query string
        k: Number of results
        
    Returns:
        List of (Document, cosine_similarity) tuples with scores in [-1, 1]
    """
    # Get raw squared L2 distances
    docs_and_distances = faiss_index.similarity_search_with_score(query, k, **kwargs)
    
    # Convert: cos(θ) = 1 - d²/2
    docs_and_similarities = [
        (doc, 1.0 - distance / 2.0)
        for doc, distance in docs_and_distances
    ]
    
    return docs_and_similarities

# Usage:
results = search_with_cosine_similarity(toolkit.node_index, "company", k=5)
````

**Pros**: 
- No class modification
- Functional approach

**Cons**: 
- Extra function to remember
- Not object-oriented

### Fix 2.5: Monkey Patch at Runtime (Quick & Dirty)

````python
from langchain_community.vectorstores import FAISS

# Monkey patch the class method
def _corrected_cosine_relevance_score_fn(distance: float) -> float:
    return 1.0 - distance / 2.0

FAISS._cosine_relevance_score_fn = staticmethod(_corrected_cosine_relevance_score_fn)

# Now all FAISS instances use corrected function
toolkit = Text2CypherToolkit(...)
````

**Pros**: 
- One-line fix
- Affects all instances

**Cons**: 
- Global side effect
- Fragile
- Hard to debug

---

## Recommendation

**Best Practice: Use Fix 2.1 or 2.2** (Custom FAISS Wrapper)

````python
class CosineSimFAISS(FAISS):
    """FAISS with corrected cosine similarity scores in [-1, 1]."""
    
    def _select_relevance_score_fn(self) -> Callable[[float], float]:
        if self.override_relevance_score_fn:
            return self.override_relevance_score_fn
        
        if self.distance_strategy == DistanceStrategy.COSINE:
            # Correct transformation for FAISS squared L2
            return lambda d: 1.0 - d / 2.0
        
        return super()._select_relevance_score_fn()
````

This gives you:
- ✅ True cosine similarity in `[-1, 1]`
- ✅ No library modification
- ✅ Drop-in replacement for `FAISS`
- ✅ Compatible with LangChain updates
- ✅ Clean, testable code