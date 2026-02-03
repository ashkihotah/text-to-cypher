Examples
--------

## Example 1: Temporal Pattern Discovery

### User Query
"Which entities and relationships in the database have temporal information like creation dates or timestamps?"

### Reasoning Trace
**Query Decomposition:**
1. Temporal information is typically stored in properties like: `created_at`, `timestamp`, `date`, `updated_at`, `since`, `until`, `year`
2. Both nodes and relationships can have temporal properties
3. Need to batch search for multiple temporal property keys at once

**Tool Calls Plan:**
- Use `get_components_with_property` with multiple temporal property keys in a single call
- Search in "both" components to check nodes and relationships simultaneously
- Use similarity matching to find the most relevant entities/relationships for each temporal concept

### Action Trace
```python
get_components_with_property(
    keys=["created_at", "timestamp", "date", "since", "year"],
    components=["both", "both", "both", "relationships", "both"],
    similar_to=["recent new", "event time", "publication temporal", "employment duration", "temporal period"],
    top_k=5
)
```

**Expected Output:**
- `created_at` property: Found in Article, Post, Comment (nodes) sorted by relevance to "recent new"
- `timestamp` property: Found in Event, Transaction (nodes) sorted by relevance to "event time"
- `date` property: Found in Publication, Article (nodes) sorted by relevance to "publication temporal"
- `since` property: Found in WORKS_AT, EMPLOYED_BY (relationships) sorted by relevance to "employment duration"
- `year` property: Found in Movie, Publication (nodes) sorted by relevance to "temporal period"

---

## Example 2: Identity Property Mapping

### User Query
"I need to find all entities that have identifiers or names - specifically looking for things that represent people, organizations, and unique IDs."

### Reasoning Trace
**Query Decomposition:**
1. Identity properties include: `name`, `title`, `id`, `uuid`, `email`, `username`
2. Different properties might be more relevant for different entity types
3. Need to batch all identity property searches together for efficiency

**Tool Calls Plan:**
- Single batched call to `get_components_with_property` with all identity-related keys
- Focus on nodes only (entities rather than relationships)
- Use targeted similarity queries: names for people/orgs, technical terms for IDs

### Action Trace
```python
get_components_with_property(
    keys=["name", "title", "id", "email", "username", "uuid"],
    components=["nodes", "nodes", "nodes", "nodes", "nodes", "nodes"],
    similar_to=["person organization", "publication position", "unique identifier", "contact person", "user account", "technical identifier"],
    top_k=[8, 6, 10, 5, 5, 5]
)
```

**Expected Output:**
- `name` property: Person, Organization, Company, Product, Location, Author, Institution, City (8 results)
- `title` property: Article, Publication, Book, Position, Role, Job (6 results)
- `id` property: All major entities with unique identifiers (10 results)
- `email` property: Person, User, Contact, Author, Researcher (5 results)
- `username` property: User, Account, Profile, Member, Author (5 results)
- `uuid` property: Transaction, Entity, Record, Document, Session (5 results)

---
