The efficiency of a Branch and Bound algorithm depends almost entirely on how quickly it can prune "dead" branches of the search tree.

Here are the **4 Critical Components** that dictate performance, ranked by impact, along with design strategies to optimize them.

---

### 1. The Upper Bound Function (The "Pruner")
**Impact:** 🚀 **Critical (Highest)**
This is the single most important component. A "loose" upper bound (one that is too optimistic) fails to prune bad branches, degrading the algorithm into a brute-force search ($O(N!)$). A "tight" upper bound allows the algorithm to stop exploring early ($O(b^N)$).

**Optimization Strategies:**

*   **Strategy A: The Hungarian Heuristic (Linear Assignment)**
    *   *Description:* Instead of simply taking the max similarity for each unmapped node independently, solve the **Linear Assignment Problem** for the unmapped nodes.
    *   *Why:* The current code allows multiple source nodes to "claim" the same target node in the UB calculation. The Hungarian algorithm forces a 1-to-1 mapping constraint in the heuristic.
    *   *Trade-off:* Adds $O(N^3)$ overhead per node, but tightens the bound drastically, usually resulting in a net speedup.

*   **Strategy B: Local Structure Lookahead**
    *   *Description:* When calculating the potential score of mapping Node A to Node B, include the edges. If Node A has an edge to an *already mapped* Node C, check if Node B has an edge to Node C's target. If not, the potential edge score is 0.
    *   *Why:* It punishes mappings that break the graph topology immediately, lowering the UB and pruning structural mismatches earlier.

*   **Strategy C: Pre-computed Similarity Matrix**
    *   *Description:* Before recursion starts, compute a matrix $S_{ij}$ representing the max possible similarity between Source Node $i$ and Target Node $j$.
    *   *Why:* The UB calculation becomes a quick lookup or summation rather than re-evaluating properties/labels inside the loop.

---

### 2. Variable Ordering (Which Source Node to Map Next?)
**Impact:** 🔥 **High**
The order in which you pick source nodes to map determines the "shape" of the search tree. You want to fail as early as possible (fail-fast).

**Optimization Strategies:**

*   **Strategy A: Minimum Remaining Values (MRV)**
    *   *Description:* Always pick the source node that has the **fewest** compatible target candidates.
    *   *Why:* If a node has only 1 valid option, map it now! If it turns out to be invalid, you prune the tree at the root. If you leave it for last, you do meaningless work on other nodes before realizing this one is impossible.

*   **Strategy B: Degree Centrality (Most Constrained First)**
    *   *Description:* Sort source nodes by their degree (number of connected edges). Map the "Hub" nodes first.
    *   *Why:* Hubs impose constraints on their neighbors. Once a hub is mapped, its neighbors' valid candidate lists shrink massively.

*   **Strategy C: Rare Label Priority**
    *   *Description:* Map nodes with unique or rare labels first.
    *   *Why:* A node labeled `:Spacecraft` likely has very few matches compared to `:Person`. Resolving it reduces ambiguity immediately.

---

### 3. Value Ordering (Which Target Node to Try First?)
**Impact:** ⚡ **Medium**
Once you pick a source node, in what order do you try the target candidates? This doesn't help with pruning *bad* branches, but it helps find a *good* solution early.

**Optimization Strategies:**

*   **Strategy A: Best-Match First (Greedy approach)**
    *   *Description:* Sort the `available_target_vars` by their immediate local similarity (labels + properties) to the current source node.
    *   *Why:* This raises the global `BEST_JACCARD_SCORE` quickly. A high `BEST_JACCARD_SCORE` makes the Pruning Condition (`UB <= BEST`) trigger more often for subsequent branches.

*   **Strategy B: Structural Support**
    *   *Description:* Prioritize target nodes that are already connected to the mapped neighbors of the current source node.
    *   *Why:* It follows the existing edges, ensuring the edge-score component of Jaccard is maximized early.

---

### 4. Domain Filtering (Candidate Generation)
**Impact:** 🛡️ **Medium (Pre-computation)**
How do you decide which target nodes are even *allowed* to be in `available_target_vars`?

**Optimization Strategies:**

*   **Strategy A: Hard Label Constraints**
    *   *Description:* If `source.labels` and `target.labels` have zero intersection, do not even add `target` to `available_target_vars`.
    *   *Why:* Reduces the branching factor. If a source node has 100 candidates, but only 5 share a label, the tree width drops from 100 to 5.

*   **Strategy B: Degree Filtering**
    *   *Description:* If `source_node` has degree 5, and `target_node` has degree 1, `target_node` is likely a bad candidate (unless you allow partial subgraph matching).
    *   *Why:* Eliminates structurally impossible matches before recursion begins.

*   **Strategy C: Property Bloom Filter**
    *   *Description:* Create a hash signature of property keys. If `source` has keys `{name, age, id}` and `target` has `{color, size}`, skip it.
    *   *Why:* Fast bitwise rejection of incompatible nodes.

### Recommended Implementation Priority

1.  **Implement Domain Filtering (4A)**: It's easy (just an `if` statement) and cuts the search space significantly for labeled graphs.
2.  **Implement Pre-computed Matrix (1C)**: Moves math out of the recursive loop.
3.  **Implement MRV Ordering (2A)**: Sort your unmapped list so hard nodes are processed first.
4.  **Implement Hungarian Heuristic (1A)**: Do this only if the algorithm is still too slow on complex graphs.