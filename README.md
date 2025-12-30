
# other TODOs

1. integrate mandatory and optional patterns in SingleCypherQuery as a unique field pattern in which each node/edge has a flag is_optional. This leads to simplifications and better accuracy in the evaluation metrics.
2. implement find_optimal_mapping at SingleCypherQuery level using Constrained Optimization algorithms such as Branch and Bound ...
3. implement multi_part_query support in the evaluation metrics.
4. review the to_canonical_form method for correctness and efficiency.

5. Unit tests for the evaluation metrics and graph pattern extraction.
6. Integration Tests to validate end-to-end functionality of the metric computation.