Examples
--------

### Example 1: Chained Relationship Exploration

**User Query:**
"Find people who invested in companies that were later acquired, showing the investment amount and acquisition price"

**Reasoning**:
This query involves a chain: Person → Investment → Company → Acquisition. 
I need to understand the connection patterns for both investment and acquisition relationships.

Actions:
```python
    search_for(
        components=["relationships", "relationships"],
        similar_to=["invested in investment funding", "acquired acquisition purchase buyout"],
        top_k=5
    )
    # -> Returns relationship types: ['HAS_INVESTOR', 'INVESTED_IN', 'ACQUIRED', ...]

    get_domains_ranges_of(
        relationships=["HAS_INVESTOR", "INVESTED_IN", "ACQUIRED"],
        similar_to=[
            "person investor individual",
            "company startup acquired target",
            "company acquirer buyer corporation"
        ],
        order_by=["domains", "ranges", "domains"],
        top_k=[5, 3, 3]
    )
```

### Example 2: Understanding Multiple Relationship Patterns

**User Query:**
"What types of entities can be authors, investors, and members in this knowledge graph?"

**Reasoning:**
I need to understand the domain and range constraints for three relationships:
- `AUTHORED` - who can author what?
- `INVESTED_IN` - who can invest in what?
- `MEMBER_OF` - who can be members of what?

Batching these queries reveals the graph's structural patterns efficiently.

**Actions:**
```python
# Batch multiple relationships to understand entity patterns
get_domains_ranges_of(
    relationships=["AUTHORED", "INVESTED_IN", "MEMBER_OF"],
    similar_to=[
        "person author writer creator individual",
        "investor venture_capital institution fund",
        "person user individual member participant"
    ],
    order_by=["domains", "domains", "domains"],
    top_k=[5, 5, 5]
)
```

---

### Example 3: Range-Focused Discovery

**User Query:**
"What can be purchased, reviewed, and recommended? I need to find all product-like entities"

**Reasoning:**
I want to focus on the target entities (ranges) of these relationships to identify all product-type nodes in the schema. Using `order_by="ranges"` helps prioritize this information.

**Actions:**
```python
# Focus on ranges to find product-like entities
get_domains_ranges_of(
    relationships=["PURCHASED", "REVIEWED", "RECOMMENDS"],
    similar_to=[
        "product item merchandise goods",
        "product item service offering",
        "product similar_item alternative"
    ],
    order_by=["ranges", "ranges", "ranges"],
    top_k=10  # Same for all
)
```

---

### Example 4: Employment and Management Hierarchy

**User Query:**
"Map out the organizational structure: employment, management, and ownership relationships"

**Reasoning:**
Understanding corporate hierarchies requires knowing:
- `WORKS_AT`: who works where
- `MANAGES`: who manages what/whom
- `OWNS`: who owns what
- `REPORTS_TO`: who reports to whom

Batching these shows the complete organizational graph structure.

**Actions:**
```python
# Comprehensive organizational relationship mapping
get_domains_ranges_of(
    relationships=["WORKS_AT", "MANAGES", "OWNS", "REPORTS_TO"],
    similar_to=[
        "person employee worker",
        "manager supervisor director",
        "owner shareholder investor",
        "employee subordinate direct_report"
    ],
    order_by=["domains", "domains", "domains", "ranges"],
    top_k=[8, 8, 6, 6]
)
```

---

### Example 5: Content Creation and Interaction Network

**User Query:**
"Show me all content creation and interaction patterns: who creates, likes, shares, and comments on what?"

**Reasoning:**
Social media graphs have multiple interaction types. Understanding all at once requires batching:
- Creation relationships (CREATED, POSTED, PUBLISHED)
- Engagement relationships (LIKED, SHARED, COMMENTED_ON)

**Actions:**
```python
# Batch all content interaction relationships
get_domains_ranges_of(
    relationships=["CREATED", "POSTED", "LIKED", "SHARED", "COMMENTED_ON", "FOLLOWS"],
    similar_to=[
        "creator author user",
        "poster publisher user",
        "liker user person",
        "sharer user person",
        "commenter user person",
        "follower user subscriber"
    ],
    order_by=["domains", "domains", "domains", "domains", "domains", "ranges"],
    top_k=8  # Uniform across all
)
```

---
