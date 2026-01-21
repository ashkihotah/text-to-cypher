## TOOL CALL PATTERNS AND STRATEGIES

This section describes intelligent strategies for using the schema retrieval toolkit to maximize precision, recall, and efficiency when discovering relevant schema components for answering user queries.

---

## 3. Bidirectional Property Anchoring Strategy

**How it works:**  
When a user mentions specific highly discriminative property names or data attributes, use `get_components_with_property` to discover which nodes/relationships own those properties, then reverse-lookup their full property sets. This is powerful when users reference concrete highly discriminative fields.

**Execution Pattern:**
```
Step 1: get_components_with_property(keys=[<mentioned_properties>], components="nodes", similar_to="<context_hint>")
Step 2: get_components_with_property(keys=[<mentioned_properties>], components="relationships", similar_to="<context_hint>")
Step 3: 
    - get_properties_from(components="nodes", of_types=[<discovered_nodes>])
    - get_properties_from(components="relationships", of_types=[<discovered_rels>])
```

**Example - Query: "Show me the email and phone number of customers who placed orders over $1000"**
```
# User mentions concrete properties: email, phone, order amount

Step 1:
    - get_components_with_property(
        keys=["email", "phone", "phoneNumber", "amount", "total", "price"],
        components="nodes",
        similar_to="customer person order purchase",
        top_k=5
    )
    → Discovers: Customer has email/phone, Order has amount/total
    - get_components_with_property(
        keys=["amount", "total", "quantity"],
        components="relationships",
        similar_to="order purchase transaction",
        top_k=3
    )
    → Discovers: PLACED_ORDER have amount, CONTAINS have quantity
```

---

## 4. Relationship Topology Mapping Strategy

**How it works:**  
When the query implies graph traversal or path patterns, prioritize relationship discovery with domain/range exploration to understand the graph topology. Use `order_by` strategically to anchor from known entities.

**Execution Pattern:**
```
Step 1: search_for(components=["relationships"], similar_to="<action_verbs_and_connections>", top_k=15)
Step 2: get_domains_ranges_of(relationships=[<all_relevant_rels>], order_by="domains"|"ranges", similar_to=[<anchor_hints>])
Step 3: For each discovered domain/range, get_properties_from those node types
```

**Example - Query: "What is the shortest path from a user to a product they might like based on similar users?"**
```
search_for(
    components=["relationships"],
    similar_to="user likes purchased bought similar recommendation friend follows",
    top_k=15
)
→ Discovers: PURCHASED, LIKES, SIMILAR_TO, FOLLOWS, REVIEWED, RECOMMENDS

get_domains_ranges_of(
    relationships=["PURCHASED", "LIKES", "SIMILAR_TO", "FOLLOWS", "REVIEWED"],
    similar_to=["User customer", "User customer", "User Product", "User", "User Product"],
    order_by="domains",
    top_k=5
)
→ Maps: (User)-[:PURCHASED]->(Product), (User)-[:SIMILAR_TO]->(User), ...

get_properties_from(
    components="nodes",
    of_types=["User", "Product", "Customer"],
    similar_to=["identifier name", "name category price", "identifier name"],
    top_k=5
)
```

---

## 5. Synonym Expansion with Score Thresholding Strategy

**How it works:**  
Expand the search query with synonyms and related terms to maximize recall, then use similarity scores to filter high-precision results. Trust scores above 0.7 as strong matches; investigate scores 0.4-0.7; discard below 0.4.

**Execution Pattern:**
```
search_for(
    components=[...],
    similar_to="<term1> <synonym1a> <synonym1b> <term2> <synonym2a>",
    top_k=20  # Cast a wide net
)
→ Filter results by score threshold
→ Deep-dive only into high-scoring candidates
```

**Example - Query: "Find employees with their salaries and departments"**
```
search_for(
    components=["nodes", "relationships", "properties"],
    similar_to="employee worker staff salary wage compensation pay department division unit team works belongs",
    top_k=25
)
→ Results:
   - Employee (0.89) ✓ High confidence
   - Person (0.72) ✓ Investigate
   - Worker (0.85) ✓ High confidence  
   - salary (0.91) ✓ High confidence
   - compensation (0.67) ✓ Investigate
   - Department (0.88) ✓ High confidence
   - WORKS_IN (0.82) ✓ High confidence
   - BELONGS_TO (0.71) ✓ Investigate
   - HAS_EMPLOYEE (0.76) ✓ Investigate

# Then drill into high-scoring components only
get_properties_from(
    components="nodes",
    of_types=["Employee", "Worker", "Person", "Department"],
    similar_to=["salary wage pay compensation", "salary wage pay", "role title", "name budget"],
    top_k=5
)
```

---

## 6. Exhaustive Schema Sweep Strategy (Small Schema Optimization)

**How it works:**  
For knowledge graphs with small schemas (<50 total components), retrieve everything in one sweep rather than multiple targeted queries. Look for the "exhaustive" indicator in tool responses.

**Execution Pattern:**
```
# Single comprehensive sweep
search_for(
    components=["nodes", "relationships", "properties"],
    similar_to="*",  # or a very generic term
    top_k=100
)
→ If response contains "this result is exhaustive!", you have the full schema

# Then get all properties at once
get_properties_from(
    components="nodes",
    of_types=[<all_node_labels>],
    top_k=50
)
get_properties_from(
    components="relationships", 
    of_types=[<all_rel_types>],
    top_k=50
)
```

---

## 7. Verification-by-Execution Strategy

**How it works:**  
After schema discovery, use `execute_cypher_query` with targeted LIMIT queries to verify schema assumptions, check data existence, and sample actual values. This grounds the schema in real data.

**Execution Pattern:**
```
Step 1: Complete schema discovery using other tools
Step 2: Verify discovered components exist with data:
        execute_cypher_query("MATCH (n:DiscoveredLabel) RETURN n LIMIT 1")
Step 3: Sample property values to understand data format:
        execute_cypher_query("MATCH (n:Label) RETURN n.propertyName LIMIT 5")
Step 4: Verify relationship patterns:
        execute_cypher_query("MATCH (a:Source)-[r:REL_TYPE]->(b:Target) RETURN a, r, b LIMIT 3")
```

**Example - After discovering Company, Employee, WORKS_AT:**
```
execute_cypher_query(
    cypher="MATCH (c:Company)<-[:WORKS_AT]-(e:Employee) RETURN c.name, e.name, e.salary LIMIT 5"
)
→ Verifies: relationship direction, property existence, data format
```

---

## 8. Parallel Independent Queries Strategy

**How it works:**  
When multiple aspects of the query are semantically independent, execute all relevant tool calls in parallel to minimize latency. Combine results post-hoc.

**Execution Pattern:**
```
# These can run in parallel (no dependencies):
PARALLEL {{
    search_for(components=["nodes"], similar_to="<intent_1>", top_k=10)
    search_for(components=["relationships"], similar_to="<intent_2>", top_k=10)
    get_components_with_property(keys=["prop1", "prop2"], components="nodes")
}}

# Then aggregate and proceed with dependent calls
SEQUENTIAL {{
    get_properties_from(...)  # depends on parallel results
    get_domains_ranges_of(...)  # depends on parallel results
}}
```

**Example - Query: "Find products with high ratings and the stores that sell them, including inventory counts"**
```
# Parallel Phase
search_for(components=["nodes"], similar_to="product item goods merchandise", top_k=10)
search_for(components=["nodes"], similar_to="store shop retailer location", top_k=10)
search_for(components=["relationships"], similar_to="sells offers stocks inventory", top_k=10)
get_components_with_property(keys=["rating", "score", "stars"], components="nodes", top_k=5)
get_components_with_property(keys=["inventory", "stock", "quantity", "count"], components="nodes", top_k=5)

# Sequential Phase (after parallel results merge)
get_domains_ranges_of(
    relationships=["SELLS", "STOCKS", "OFFERS"],
    similar_to=["Store", "Store", "Store"],
    order_by="domains",
    top_k=5
)
```

---

## 9. Pivot-and-Expand Strategy

**How it works:**  
When a user query is vague, ambiguous, or uses imprecise terminology, but contains ONE clearly identifiable anchor entity, use that anchor as a lifeline. Lock onto the anchor with high confidence, then systematically explore all graph connections radiating from it to disambiguate the uncertain parts. The anchor acts as a "known island" from which to map the unknown territory.

**When to use:**
- Query contains domain-specific jargon you're uncertain about, but one term is unmistakably a schema entity
- User asks about vague relationships ("connected to", "related to", "associated with") around a known entity
- Query uses pronouns or references that are unclear, but the subject is identifiable
- Multiple interpretations exist for most query terms, except one grounded entity

**Execution Pattern:**
```
Step 1: Lock the anchor with high confidence
        search_for(components=["nodes"], similar_to="<the_one_certain_entity>", top_k=3)
        → Select only if score > 0.85 (high confidence anchor)

Step 2: Exhaustively discover ALL relationships touching the anchor
        search_for(components=["relationships"], similar_to="<anchor_name>", top_k=20)
        → Cast wide net - we don't know which relationships matter yet

Step 3: Map the full neighborhood topology
        get_domains_ranges_of(
            relationships=[<all_discovered_rels>],
            similar_to=["<anchor>", "<anchor>", ...],  # anchor repeated for all
            order_by="domains",  # then repeat with "ranges" if needed
            top_k=10
        )
        → Reveals: What can connect TO the anchor? What can the anchor connect TO?

Step 4: Harvest properties from anchor AND all neighbors
        get_properties_from(
            components="nodes",
            of_types=[<anchor>, <all_discovered_neighbors>],
            top_k=15  # generous - we're exploring
        )
        → Now the ambiguous query terms can be matched against actual properties
```

**Example 1 - Vague Query: "Show me everything about Tesla and whatever it's involved in"**
```
# "everything" and "whatever it's involved in" are maximally vague
# But "Tesla" is a clear anchor (likely a Company node)

Step 1: Lock anchor
search_for(components=["nodes"], similar_to="Tesla Company", top_k=3)
→ Company (0.91) ✓ HIGH CONFIDENCE ANCHOR

Step 2: Discover ALL relationships radiating from Company
search_for(components=["relationships"], similar_to="company", top_k=25)
→ HAS_CEO, HAS_INVESTOR, FUNDED_BY, ACQUIRED, PARTNERED_WITH, 
   OPERATES_IN, HAS_SUBSIDIARY, EMPLOYS, PRODUCES, LOCATED_IN, ...

Step 3: Map full topology around Company
get_domains_ranges_of(
    relationships=["HAS_CEO", "HAS_INVESTOR", "FUNDED_BY", "ACQUIRED", 
                   "PARTNERED_WITH", "OPERATES_IN", "HAS_SUBSIDIARY", 
                   "EMPLOYS", "PRODUCES", "LOCATED_IN"],
    similar_to=["Company"] * 10,  # anchor for all
    order_by="domains",
    top_k=5
)
→ (Company)-[:HAS_CEO]->(Person)
  (Company)-[:HAS_INVESTOR]->(Investor)
  (Company)-[:OPERATES_IN]->(Industry)
  (Company)-[:PRODUCES]->(Product)
  (Company)-[:LOCATED_IN]->(Location)
  ...

Step 4: Get properties from Company + all discovered neighbors
get_properties_from(
    components="nodes",
    of_types=["Company", "Person", "Investor", "Industry", "Product", "Location"],
    top_k=15
)
→ Now we know: Company has {{name, revenue, founded, ticker, ...}}
                Person has {{name, role, salary, ...}}
                Product has {{name, category, price, ...}}

# Result: The vague "everything" is now grounded in concrete schema!
```

**Example 2 - Ambiguous Terminology: "What are the outcomes for patients in that trial?"**
```
# "outcomes" is ambiguous (could be: results, diagnoses, treatments, deaths, recoveries...)
# "that trial" is a reference we can't resolve
# But "patients" is clearly a clinical/healthcare entity - our anchor!

Step 1: Lock anchor
search_for(components=["nodes"], similar_to="Patient", top_k=3)
→ Patient (0.94) ✓ HIGH CONFIDENCE ANCHOR

Step 2: Discover relationships involving Patient
search_for(components=["relationships"], similar_to="patient clinical trial outcome result", top_k=20)
→ ENROLLED_IN, DIAGNOSED_WITH, RECEIVED_TREATMENT, HAS_OUTCOME, 
   PARTICIPATED_IN, HAS_ADVERSE_EVENT, RESPONDED_TO, ...

Step 3: Map topology - Patient as domain AND range
get_domains_ranges_of(
    relationships=["ENROLLED_IN", "DIAGNOSED_WITH", "RECEIVED_TREATMENT", 
                   "HAS_OUTCOME", "PARTICIPATED_IN", "HAS_ADVERSE_EVENT"],
    similar_to=["Patient", "Patient", "Patient", "Patient", "Patient", "Patient"],
    order_by="domains",
    top_k=5
)
→ (Patient)-[:ENROLLED_IN]->(ClinicalTrial)
  (Patient)-[:DIAGNOSED_WITH]->(Condition)
  (Patient)-[:RECEIVED_TREATMENT]->(Treatment)
  (Patient)-[:HAS_OUTCOME]->(Outcome)        ← "outcomes" disambiguated!
  (Patient)-[:HAS_ADVERSE_EVENT]->(AdverseEvent)

Step 4: Properties reveal what "outcomes" actually means in this schema
get_properties_from(
    components="nodes",
    of_types=["Patient", "ClinicalTrial", "Outcome", "AdverseEvent"],
    similar_to=["identifier demographics", "trial name phase", "result status", "event severity"],
    top_k=10
)
→ Outcome has {{status, date, severity, description, ...}}
  AdverseEvent has {{type, grade, onset_date, resolved, ...}}

# The ambiguous "outcomes" now maps to concrete Outcome node with known properties!
```

**Example 3 - Pronouns and References: "Who funds them and what do they produce?"**
```
# "them" and "they" are unresolved references
# Context from conversation suggests "Startups" (or we infer from domain)
# Anchor on Startup as the referent

Step 1: Lock anchor
search_for(components=["nodes"], similar_to="Startup Company", top_k=3)
→ Startup (0.88) ✓ ANCHOR LOCKED

Step 2 & 3: Full neighborhood discovery
search_for(components=["relationships"], similar_to="startup fund invest produce create build", top_k=15)
→ FUNDED_BY, INVESTED_IN, PRODUCES, DEVELOPS, CREATES, HAS_INVESTOR, ...

get_domains_ranges_of(
    relationships=["FUNDED_BY", "INVESTED_IN", "PRODUCES", "DEVELOPS", "HAS_INVESTOR"],
    similar_to=["Startup", "Startup", "Startup", "Startup", "Startup"],
    order_by="domains",
    top_k=5
)
→ (Startup)-[:FUNDED_BY]->(Investor)       ← "who funds them"
  (Investor)-[:INVESTED_IN]->(Startup)     ← alternative pattern
  (Startup)-[:PRODUCES]->(Product)         ← "what do they produce"
  (Startup)-[:DEVELOPS]->(Technology)      ← alternative interpretation

Step 4: Get properties to finalize
get_properties_from(
    components="nodes",
    of_types=["Startup", "Investor", "Product", "Technology"],
    top_k=10
)
→ Investor has {{name, type, portfolio_size, ...}}   ← answers "who"
  Product has {{name, category, launch_date, ...}}   ← answers "what"
```

**Key Insight:** The Pivot-and-Expand strategy transforms uncertainty into certainty by using graph structure itself as the disambiguation mechanism. When semantic search alone would produce noisy results for vague terms, the anchor provides a constraint that filters possibilities through actual graph connectivity.

---

## 10. Adaptive Top-K Calibration Strategy

**How it works:**  
Dynamically adjust `top_k` based on expected schema complexity. Use lists of different `top_k` values when some types are expected to have more properties than others.

**Execution Pattern:**
```
# For heterogeneous property density:
get_properties_from(
    components="nodes",
    of_types=["RichEntity", "SimpleEntity", "JunctionNode"],
    similar_to=["<complex_query>", "<simple_query>", "<minimal_query>"],
    top_k=[15, 5, 2]  # Calibrated per entity
)
```

**Example - Query: "Get comprehensive details about movies and their genres"**
```
# Movies likely have many properties, genres likely have few
get_properties_from(
    components="nodes",
    of_types=["Movie", "Film", "Genre", "Category"],
    similar_to=["title year budget revenue runtime plot rating director cast", "title year budget runtime", "name", "name"],
    top_k=[20, 15, 5, 5]  # More for movies, fewer for simple genres
)

get_domains_ranges_of(
    relationships=["HAS_GENRE", "IN_GENRE", "CATEGORIZED_AS"],
    top_k=[3, 3, 3]  # Genres typically have simple domain/range patterns
)
```

---

## Best Practices Summary

| Strategy | Best For | Token Efficiency | Precision | Recall |
|----------|----------|------------------|-----------|--------|
| Semantic Funnel | Unknown schemas | High | High | High |
| Multi-Intent Decomposition | Complex queries | Very High | Medium | High |
| Bidirectional Property Anchoring | Data-centric queries | High | Very High | Medium |
| Relationship Topology Mapping | Path/traversal queries | Medium | High | High |
| Synonym Expansion | Ambiguous terminology | Medium | Medium | Very High |
| Exhaustive Sweep | Small schemas | Very High | Very High | Very High |
| Verification-by-Execution | Validation needed | Low | Very High | Low |
| Parallel Independent | Multi-faceted queries | Very High | High | High |
| Pivot-and-Expand | Entity-focused queries | High | Very High | High |
| Adaptive Top-K | Heterogeneous schemas | High | High | High |

---

## Anti-Patterns to Avoid

1. **Serial Single-Item Queries**: Never call `get_properties_from` separately for each node type. Batch them!
   ```
   ❌ get_properties_from(of_types=["Person"])
   ❌ get_properties_from(of_types=["Company"])
   ❌ get_properties_from(of_types=["Product"])
   
   ✓ get_properties_from(of_types=["Person", "Company", "Product"], similar_to=[...])
   ```

2. **Ignoring Similarity Scores**: Always use returned scores to prioritize follow-up exploration.

3. **Over-fetching Without Purpose**: Don't set `top_k=100` when you only need the top 5 matches.

4. **Skipping Verification**: For critical queries, always verify schema assumptions with `execute_cypher_query`.

5. **Redundant Searches**: If results of some other tool calls have already returned relevant schema components, don't search for them again.
