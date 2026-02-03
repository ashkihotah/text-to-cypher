Examples
--------

### Example 1: Multi-Entity Query with Parallel Discovery

**User Query:**
"Find all movies directed by someone who also acted in them, showing the budget and box office revenue"

**Reasoning:**
To answer this query, I need to identify schema components for four independent information needs:
1. Movies/films entities
2. Directors and their relationships
3. Actors and their relationships  
4. Financial data (budget, revenue)

I'll use `search_for` in parallel for each information need to maximize recall and discover all possible schema representations.

**Action:**
```python
# Parallel calls for simultaneously comprehensive schema discovery
search_for(
    components=["nodes"],
    similar_to="movie film production media", # (1) movies
    top_k=5
)
search_for(
    components=["nodes", "relationships", "properties"],
    similar_to="director person directed manages leads", # (2) directors
    top_k=10
)
search_for(
    components=["nodes", "relationships", "properties"],
    similar_to="actor person acted_in performed starred cast", # (3) actors
    top_k=10
)
search_for(
    components=["nodes", "relationships", "properties"],
    similar_to="budget revenue earned cost", # (4) financial data
    top_k=10
)
```

---

### Example 2: Complex Social Network Analysis

**User Query:**
"Show me people who work at companies that have received funding from venture capital firms, including when they joined and how much funding was raised"

**Reasoning:**
This query involves five distinct information needs:
1. People/person entities
2. Companies/organizations
3. Employment relationships and timing
4. Investors/venture capital firms
5. Funding relationships and amounts

Each needs comprehensive discovery through parallel `search_for` calls.

**Actions:**
```python
# All executed in parallel
search_for(
    components=["nodes"],
    similar_to="person people employee individual human worker",
    top_k=8
)

search_for(
    components=["nodes"],
    similar_to="company organization business corporation firm enterprise startup",
    top_k=8
)

search_for(
    components=["relationships", "properties"],
    similar_to="employment works_at employed hired joined job position since date",
    top_k=12
)

search_for(
    components=["nodes", "relationships"],
    similar_to="investor venture_capital vc funding investment fund capital",
    top_k=10
)

search_for(
    components=["relationships", "properties"],
    similar_to="investment funded financing raised round amount money capital series",
    top_k=12
)
```

---

### Example 3: Product Recommendation System

**User Query:**
"Find users who purchased products in the same category, their ratings, and recommend similar items based on previous purchases"

**Reasoning:**
Breaking down into information needs:
1. User/customer entities
2. Product/item entities
3. Purchase/transaction relationships
4. Categories and classification
5. Ratings and reviews
6. Similarity/recommendation patterns

Parallel discovery ensures we find all relevant schema components.

**Actions:**
```python
# Parallel execution for comprehensive coverage
search_for(
    components=["nodes"],
    similar_to="user customer buyer account member consumer shopper",
    top_k=6
)

search_for(
    components=["nodes"],
    similar_to="product item merchandise goods article commodity",
    top_k=8
)

search_for(
    components=["relationships", "properties"],
    similar_to="purchase bought ordered transaction sale bought_date timestamp",
    top_k=10
)

search_for(
    components=["nodes", "relationships", "properties"],
    similar_to="category type class genre group classification taxonomy",
    top_k=10
)

search_for(
    components=["properties"],
    similar_to="rating review score stars feedback evaluation assessment",
    top_k=8
)

search_for(
    components=["relationships"],
    similar_to="similar recommend related suggested comparable analogous",
    top_k=8
)
```

---
