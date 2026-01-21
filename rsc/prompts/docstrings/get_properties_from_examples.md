Examples
--------

### Example 1: Multi-Entity Property Discovery

**User Query:**
"Show me employee information including their skills, and company details including their industry sector"

**Reasoning:**
After used `search_for` and identified that the schema has `Person`, `Company`, and `Skill` nodes, I need to find:
1. Properties of Person nodes relevant to employee information
2. Properties of Company nodes relevant to company details
3. Properties of Skill nodes

I'll batch these requests together for efficiency.

**Actions:**
```python
# Single batched call instead of 3 separate calls
get_properties_from(
    components=["nodes", "nodes", "nodes"],
    of_types=["Person", "Company", "Skill"],
    similar_to=[
        "employee name email position title salary department contact",
        "company industry sector revenue founded headquarters location",
        "skill expertise competency level proficiency"
    ],
    top_k=[10, 10, 8]
)
```

---

### Example 2: Relationship Properties Batching

**User Query:**
"Find when people joined companies and when funding rounds occurred"

**Reasoning:**
I've identified `WORKS_AT` and `FUNDED` relationships. Now I need temporal properties from both, plus any additional metadata. Batching these together is more efficient.

**Actions:**
```python
# Batch relationship property queries
get_properties_from(
    components=["relationships", "relationships"],
    of_types=["WORKS_AT", "FUNDED"],
    similar_to=[
        "date joined started hired since beginning employment_date",
        "date round series amount funding_date invested when"
    ],
    top_k=[8, 10]
)
```

---

### Example 3: Mixed Node and Relationship Properties

**User Query:**
"Get transaction details with timestamps, product specifications, and user preferences"

**Reasoning:**
After schema discovery, I identified:
- `PURCHASED` relationship (needs timestamp/amount properties)
- `Product` node (needs specification properties)
- `User` node (needs preference properties)

Batching all three in one call is optimal.

**Actions:**
```python
# Mixed batching: 2 nodes + 1 relationship
get_properties_from(
    components=["relationships", "nodes", "nodes"],
    of_types=["PURCHASED", "Product", "User"],
    similar_to=[
        "timestamp date time amount price quantity when payment",
        "specifications specs features attributes dimensions weight capacity model",
        "preferences settings favorites interests choices options configuration"
    ],
    top_k=[10, 12, 10]
)
```

---

### Example 4: Large-Scale Schema Exploration

**User Query:**
"Explore all core entities in the social network: users, posts, comments, groups, and events"

**Reasoning:**
Perfect, i correctly identified `User`, `Post`, `Comment`, `Group`, and `Event` nodes.
Now for broad schema exploration, I need properties from multiple node types. Instead of 5 separate calls, one batched call is far more efficient.

**Actions:**
```python
# Batch 5 node types in single call
get_properties_from(
    components=["nodes", "nodes", "nodes", "nodes", "nodes"],
    of_types=["User", "Post", "Comment", "Group", "Event"],
    similar_to=[
        "user profile username bio location followers interests",
        "post content title body author timestamp likes views",
        "comment text message reply author created_at likes",
        "group name description category members visibility privacy",
        "event title description location date attendees organizer"
    ],
    top_k=15  # Same top_k for all
)
```

---
