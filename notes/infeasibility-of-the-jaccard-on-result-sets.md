# Is the jaccard similarity between two result sets feasible to compute at a time complexity better than O(N^2)?

The short answer is **no for an exact solution**, but **yes for a high-quality approximation**.

Here is the theoretical breakdown of why, and how algorithms sidestep this limit:

### 1. The $O(N^2)$ Lower Bound for Exact Matching
To find the exact theoretical optimal alignment (or even to run the deterministic greedy algorithm currently in the code), you have to know the Jaccard similarity between *every* row in $V_L$ and *every* row in $V_R$. 

Generating this pairwise similarity matrix requires calculating $N \times N$ combinations. Thus, simply constructing the information needed to make the exact optimal choice has a hard mathematical lower bound of **$O(N^2)$**. 

Actually computing the absolute optimal alignment from that matrix (the Assignment Problem) takes **$O(N^3)$** using algorithms like the Hungarian method.

### 2. Can we approximate it in sub-$O(N^2)$ time?
Yes. In modern data science, computing Jaccard similarity at scale (e.g., comparing millions of documents or graph nodes) bypasses the $O(N^2)$ bottleneck using **probabilistic data structures**.

If you wanted to optimize this evaluation function to run in roughly $O(N \log N)$ or even $O(N)$ expected time, you would use **MinHash** combined with **Locality-Sensitive Hashing (LSH)**:

*   **MinHash:** Instead of keeping exact sets of cell values, you generate a small, fixed-length signature for each row. The mathematical property of MinHash is that the probability of two signatures matching is exactly equal to their Jaccard similarity.
*   **LSH (Locality-Sensitive Hashing):** You then place these signatures into hash buckets. Rows that have a high Jaccard similarity will highly likely fall into the same bucket. 

Instead of comparing Row A against all $N$ rows in Table B, you only compare Row A against the handful of rows that landed in the exact same LSH bucket. 

### 3. The $O(N)$ Exact Matching Proxy
If the requirement of *partial* row similarity was relaxed, and the Jaccard metric only cared about *exact* row matches (which is mostly what matters in database evaluation), you could simply hash the entire row (e.g., `hash(frozenset(row))`). 

Finding the intersection and union of two tables of hashed rows is a simple dictionary/hash-set lookup, which drops the time complexity instantly to **$O(N)$**. The current implementation attempts to tolerate partial row overlaps (e.g., 3 out of 4 columns match), which forces it into the expensive dense $O(N^2)$ set-)$ set\_(N^2)$ territory.

# So is any greedy approximation of the Jaccard similarity a valid lower bound, and does it guarantee a score of 1.0 for exact matches? (for example, the one implemented in `runtime.py`)

Yes to both questions. Here is the formal reasoning for why that is the case:

### 1. Is the computed score a strict lower bound?
**Yes.** 
By definition, the true optimal Jaccard similarity is the maximum possible score across all mathematically valid permutations (alignments) of the tabular rows:
$$ J_{optimal} = \max_{p \in \text{Permutations}} J(p) $$

The greedy algorithm in `make_alignment` simply generates **one specific valid permutation**, let's call it $p_{greedy}$. It evaluates the Jaccard score for that specific alignment. 

Because $J(p_{greedy})$ is drawn from the set of all possible permutation scores, it is guaranteed that:
$$ J(p_{greedy}) \le J_{optimal} $$
Therefore, the heuristic implementation strictly serves as a lower bound for the real optimal assignment score.

### 2. Are exact matches guaranteed to evaluate to 1.0?
**Yes.** 
If the generated result is an exact match to the ground truth, it means $D_L$ and $D_R$ contain the exact same multiset of rows, just possibly in a different order.

The greedy algorithm is entirely safe in this scenario due to the absolute ceiling of the Jaccard metric:
1. **The 1.0 Ceiling:** The maximum possible value for `rowsim` (Jaccard similarity of two row sets) is exactly `1.0`.
2. **Greedy perfection:** When the algorithm evaluates row $L_i$, it scans the theoretical remaining unaligned pool in $R$. Because the two tables hold the exact same rows, there is mathematically guaranteed to be at least one remaining row $R_j$ that is identical to $L_i$.
3. When it compares $L_i$ to $R_j$, it yields `rowsim = 1.0`. Because the score cannot possibly go higher than `1.0`, the greedy algorithm **always successfully pairs identical rows together** and never mistakenly sacrifices a perfect match for a sub-optimal one. 
4. Once all rows are perfectly aligned ($V_{L, i} \equiv V_{R, i}$ for all $i$), the flattened sets $S_L$ and $S_R$ in `df_sim` become completely identical.
5. Evaluating perfectly overlapping sets yields: $\frac{|S_L \cap S_R|}{|S_L \cup S_R|} = \frac{x}{x} = 1.0$.

In summary, while the greedy heuristic severely underestimates mid-to-high similarity outputs, it handles exact matches flawlessly and guarantees a Jaccard score of 1.