
1. il planning iniziale influenza fortemente l'intera traiettoria
   1. Nel planning bisognerebbe dire di iniziare la ricerca dai termini più generali per poi andare verso i più specifici, dato che sono quelli più probabili di essere presenti nello schema
2. Talvolta il tool restituisce più risultati utili per la query ma il modello non riesce ad accorgersene e ragiona solo per il suo obiettivo immediato

# TODOs

1. Run the trajectories generation + evaluation of results
2. Train and evaluate functiongemma

3. ✅​ Design and implement retrieval tools
4. ⚠️​ Implement evaluation metrics for retrieval trajectories
5. ✅​ Implement runtime evaluation metrics for Cypher queries
6. ❌​ Implement static evaluation metrics for Cypher queries (UNFEASIBLE)
7. ❌​ Implement relevant schema extractor from a Cypher query (UNFEASIBLE)

# other TODOs

1. integrate mandatory and optional patterns in SingleCypherQuery as a unique field pattern in which each node/edge has a flag is_optional. This leads to simplifications and better accuracy in the evaluation metrics.
2. implement find_optimal_mapping at SingleCypherQuery level using Constrained Optimization algorithms such as Branch and Bound ...
3. implement multi_part_query support in the evaluation metrics. How?
   1. Extract each reading clause between WITH statements as a SingleCypherQuery.
   2. For each WITH statement, "compile" the entire multi part query flow in a single GraphPattern that summarize the entire Provenance Sub Graph:
      1. assigning to each node/edge their corresponding conditions in the WHERE clause.
      2. assigning every introduced variable, before the WITH statement, to node/edges in the next SingleCypherQuery
      3. and so on (it is possible trust me, deeply think about it. This is possible since the with clause is a simple projection_body + where clause)
4. design how to combine similarity scores for expressions in GraphPatterns and viceversa.
5. review the to_canonical_form method for correctness and efficiency.

6. Unit tests for the evaluation metrics and graph pattern extraction.
7. Integration Tests to validate end-to-end functionality of the metric computation.