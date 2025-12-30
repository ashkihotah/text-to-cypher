## Efficient Enough Exact Optimal (relative to Jaccard similarity) Variable Mapping Algorithms for Cypher Graph Patterns / Queries

Since you require an **exact** solution (meaning you must find the mathematical global maximum of your Jaccard function), you are solving a version of the **Graph Edit Distance (GED)** or **Maximum Common Subgraph (MCS)** problem. These are NP-Hard, so no polynomial algorithm exists.

However, "efficient" in this context means algorithms that are **worst-case exponential but average-case tractable**. They work by ignoring vast swathes of the search space that are mathematically proven to be suboptimal.

Here are the standard algorithmic approaches to finding exact graph mappings efficiently:

---

### 1. A* Search with Admissible Heuristics (The Gold Standard)

**Description:**
Instead of a depth-first recursion (like your current code), this uses a Best-First Search strategy. It treats the mapping process as a pathfinding problem in a state-space tree.
*   **State:** A partial mapping of some nodes.
*   **Cost Function $f(n) = g(n) + h(n)$**:
    *   $g(n)$: The actual similarity score calculated for the nodes/edges mapped *so far*.
    *   $h(n)$: An **admissible heuristic** that estimates the *maximum possible* score obtainable from the remaining unmapped nodes.

**Rationale:**
The algorithm always expands the most promising partial mapping first. Crucially, if the heuristic $h(n)$ is "optimistic" (never underestimates the potential future score), the moment A* reaches a complete mapping, it is mathematically guaranteed to be the optimal one.

**Why it is efficient:**
If you have a partial mapping that looks "okay" but the heuristic says "even if everything else matches perfectly, the total score can't beat the solution we already found," A* completely abandons that branch.

**The "Killer" Optimization for A*:**
Use the **Hungarian Algorithm** (Linear Assignment) as the heuristic $h(n)$.
1.  For the unmapped nodes, ignore edges.
2.  Calculate a similarity matrix based only on node properties.
3.  Solve the assignment in $O(N^3)$.
4.  Use that score as the upper bound for the future edge matching. This effectively bounds the search space tightly.

---

### 2. Branch and Bound (B&B)

**Description:**
Similar to A*, but typically uses Depth-First Search (DFS) which is more memory efficient.
1.  Keep track of a global variable: `best_score_found_so_far`.
2.  Traverse the tree of possible mappings.
3.  At every node in the tree, calculate an **Upper Bound (UB)**. This is a mathematical calculation: "Given this partial mapping, what is the absolute best score theoretically possible if all remaining nodes match perfectly?"
4.  **Pruning Condition:** If `UB <= best_score_found_so_far`, stop. Do not go deeper. Backtrack immediately.

**Rationale:**
In Cypher queries, if you map a `:Person` to a `:Movie` early in the tree, the edge similarity potential drops to near zero. The Upper Bound calculation detects that this branch can never exceed a valid mapping you found earlier, allowing you to prune millions of permutations instantly.

**Pros:**
*   Memory efficient (linear space complexity vs exponential for A*).
*   Can be combined with the Hungarian algorithm for tight bounding.

---

### 3. Maximum Clique Reduction (Association Graph)

**Description:**
This approach transforms the graph alignment problem into a completely different graph problem: finding the **Maximum Weight Clique**.
1.  **Construct an Association Graph:**
    *   Create a "meta-node" for every possible pair $(u, v)$ where $u \in GraphA$ and $v \in GraphB$.
    *   Draw an edge between meta-node $(u, v)$ and meta-node $(x, y)$ if and only if the mapping is consistent (e.g., the relationship between $u-x$ in Graph A is similar to $v-y$ in Graph B).
2.  **Solve:** Find the Maximum Clique (the largest fully connected subgraph) in this Association Graph. The nodes in the clique represent your optimal mapping.

**Rationale:**
A clique in the Association Graph mathematically corresponds to a Common Subgraph. By assigning weights to the meta-nodes (based on property similarity) and meta-edges (based on edge similarity), finding the maximum weight clique gives you the exact Jaccard maximum.

**Pros:**
*   You can use highly optimized, state-of-the-art MaxClique solvers (like PMC or MaxCliqueDyn) which are often faster than custom recursion.
*   Handles disconnected graphs and complex topologies naturally.

**Cons:**
*   The Association Graph can get large ($N \times M$ nodes), consuming significant memory ($O((NM)^2)$ edges).

---

### 4. Integer Linear Programming (ILP)

**Description:**
Formulate the mapping problem as a mathematical optimization equation and feed it to an industrial solver (like Gurobi, CPLEX, or the open-source CBC).
*   **Variables:** Binary variables $x_{i,j}$ where $x_{i,j} = 1$ if source node $i$ maps to target node $j$.
*   **Constraints:**
    *   $\sum_j x_{i,j} \leq 1$ (Each source node maps to at most one target).
    *   $\sum_i x_{i,j} \leq 1$ (Each target node receives at most one source).
*   **Objective Function:** Maximize $\sum x_{i,j} \cdot \text{Sim}(i,j) + \sum x_{i,j} \cdot x_{k,l} \cdot \text{EdgeSim}((i,k), (j,l))$.

**Rationale:**
The edge term makes this a **Quadratic Assignment Problem (QAP)**. While QAP is NP-Hard, modern solvers use sophisticated "Linearization" techniques (converting quadratic terms to linear constraints) and "Cut Generation" to solve these efficiently for $N < 30-40$.

**Pros:**
*   Zero implementation logic errors (you define the math, the solver does the work).
*   Solvers are incredibly optimized for "proving" optimality.

---

### 5. Constraint Programming (CP) with Domain Filtering

**Description:**
Use a Constraint Satisfaction Problem (CSP) solver (like Google OR-Tools).
*   **Variables:** One variable per node in the source graph.
*   **Domain:** The list of all nodes in the target graph.
*   **Constraints:**
    *   `AllDifferent` (Injective mapping).
    *   **Implication Constraints:** "If Node A maps to Node X, and there is an edge A->B, then Node B MUST map to a neighbor of X."

**Rationale:**
CP solvers use **Propagators**. If you decide `A maps to X`, the solver looks at all constraints and removes invalid options for `B`, `C`, and `D` immediately. This "Forward Checking" dramatically reduces the search tree size before you even try to traverse it.

**Pros:**
*   Very high performance for "sparse" graphs (which Cypher queries almost always are).
*   Handles the labels and property constraints natively as domain filters.

---

### Recommendation

For a pure Python implementation without external C++ solvers:
**Option 2 (Branch and Bound)** is your best bet.

1.  **Pre-process:** Filter domains by Labels (as discussed previously).
2.  **Order:** Sort source nodes by "degree" or "uniqueness" (map the hardest nodes first).
3.  **Search:** Use DFS.
4.  **Prune:** At every step, check: *"If I perfectly match all remaining edges, can I beat the current best score?"* If no, `return`.

If you are willing to use libraries:
**Option 4 (ILP)** using `scipy.optimize` (for linear approximations) or `pulp`/`ortools` (for exact ILP) is often the most robust solution for code maintainability.

## Complexity Analysis

Here is the complexity breakdown for the exact graph matching algorithms.

**Notation:**
*   **N**: Number of nodes in the source/target graphs (assuming $N \approx M$).
*   **k**: Number of edges (sparsity).
*   **d**: Domain size (number of compatible target candidates per source node after label filtering).

---

### 1. A* Search (with Hungarian Heuristic)
*   **Main Characteristic:** Uses memory to store states; guarantees the fewest nodes visited if the heuristic is good, but heuristic calculation is expensive ($O(N^3)$ per state).

1.  **Best Case:** $O(N^3)$
    *   *Scenario:* The heuristic is perfect. The algorithm walks straight down the tree to the solution without backtracking. The cost is dominated by the Hungarian calculation on the root.
2.  **Average Case:** $O(N^3 \cdot b^d)$ (where $b$ is a small branching factor)
    *   *Scenario:* The heuristic makes occasional mistakes, requiring limited backtracking.
3.  **Worst Case:** $O(N! \cdot N^3)$
    *   *Scenario:* The heuristic fails to prune anything (e.g., highly symmetric graphs), and every state requires an $O(N^3)$ calculation.
4.  **Intractability Threshold:** **~15–20 Nodes**
    *   *Reason:* **Memory Exhaustion.** A* keeps open states in a Priority Queue. The queue grows exponentially, crashing RAM before CPU time runs out.

---

### 2. Branch and Bound (DFS-based)
*   **Main Characteristic:** Memory efficient (linear space); relies entirely on "Pruning" (detecting early that a branch is dead).

1.  **Best Case:** $O(N^2)$
    *   *Scenario:* You pick the correct mapping on the first try (lucky sorting), and the pruning logic is fast enough to reject all other branches instantly.
2.  **Average Case:** $O(b^N)$ (where $1 < b \ll N$)
    *   *Scenario:* Labels and degrees prune the search space significantly. For Cypher queries, $b$ is usually very small.
3.  **Worst Case:** $O(N!)$
    *   *Scenario:* The graph is "Homogeneous" (e.g., mapping a blank grid to a blank grid). No pruning is possible; you must visit every leaf.
4.  **Intractability Threshold:** **~25–30 Nodes**
    *   *Reason:* **Time Timeout.** Unlike A*, it won't crash your RAM, but it will simply run for the lifetime of the universe on symmetric graphs.

---

### 3. Maximum Clique Reduction (Association Graph)
*   **Main Characteristic:** transforms the problem into finding the largest cluster in a larger "Product Graph" of size $N^2$.

1.  **Best Case:** $O(N^4)$
    *   *Scenario:* Constructing the association graph takes $O(N^2 \cdot N^2)$ comparisons. If the clique is obvious, solving is fast, but construction dominates.
2.  **Average Case:** $O(c^{N})$
    *   *Scenario:* Modern clique solvers (like MaxCliqueDyn) are very fast on sparse graphs.
3.  **Worst Case:** $O(3^{N^2/3})$
    *   *Scenario:* This is the theoretical worst case for MaxClique on a graph with $N^2$ vertices. It is worse than factorial.
4.  **Intractability Threshold:** **~20 Nodes**
    *   *Reason:* The "Association Graph" explodes. For $N=20$, the association graph has 400 nodes. Finding a max clique in a 400-node dense graph is very hard.

---

### 4. Integer Linear Programming (ILP)
*   **Main Characteristic:** Uses Matrix Algebra and "Cutting Planes" to bound the search space geometrically. Requires linearization of the quadratic (edge) term.

1.  **Best Case:** $O(N^6)$ or $O(N^7)$
    *   *Scenario:* The "Linear Relaxation" (treating binary variables as continuous 0.0-1.0) happens to yield integer results immediately. Cost is matrix inversion on $N^2$ variables.
2.  **Average Case:** Exponential (but with very flat curve)
    *   *Scenario:* Solvers like Gurobi/CPLEX are incredibly optimized.
3.  **Worst Case:** $O(2^{N^2})$
    *   *Scenario:* The solver has to branch on every single binary variable because the "cuts" aren't working.
4.  **Intractability Threshold:** **~30–40 Nodes**
    *   *Reason:* The number of variables is $N^2$. At $N=40$, you have 1,600 binary variables. This is the practical limit for QAP (Quadratic Assignment Problems).

---

### 5. Constraint Programming (CP)
*   **Main Characteristic:** Uses "Propagators" to filter domains. If $A=B$, it removes $B$ from everyone else's list immediately.

1.  **Best Case:** $O(N^2 \cdot k)$
    *   *Scenario:* Propagation chains trigger immediately. Assigning the first node cascades and forces the assignment of all other nodes deterministically.
2.  **Average Case:** $O(d^N)$ (where $d$ is remaining domain size)
    *   *Scenario:* Typical Cypher query with labels.
3.  **Worst Case:** $O(N! \cdot N)$
    *   *Scenario:* Symmetries prevent propagation (e.g., mapping a ring to a ring). The solver degrades into standard backtracking.
4.  **Intractability Threshold:** **~40–50 Nodes** (for labeled graphs)
    *   *Reason:* CP is often the most robust for "pattern matching" because it handles the specific constraints of labels/properties natively, rather than purely mathematically.

### Summary Comparison

| Strategy | Best Case | Worst Case | Intractable At | Best For... |
| :--- | :--- | :--- | :--- | :--- |
| **A\*** | $O(N^3)$ | Memory Crash | > 15 Nodes | Short, complex paths where heuristic guides well. |
| **B & B** | $O(N^2)$ | $O(N!)$ | > 25 Nodes | **General usage**, easy to implement in Python. |
| **Max Clique** | $O(N^4)$ | $O(3^{N^2})$ | > 20 Nodes | Subgraph isomorphism (finding partial matches). |
| **ILP** | $O(N^6)$ | $O(2^{N^2})$ | > 35 Nodes | If you have a license for Gurobi/CPLEX. |
| **CP** | $O(N^2)$ | $O(N!)$ | > 45 Nodes | **Labeled/Property graphs** (like Cypher/Neo4j). |