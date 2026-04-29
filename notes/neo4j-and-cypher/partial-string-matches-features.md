Neo4j Community Edition provides robust options for partial string matching, but they are split across **three different layers**:
1.  **Native Cypher Operators** (Basic patterns)
2.  **APOC Library** (Advanced string similarity & distance algorithms)
3.  **Full-Text Search Indexes** (Lucene-based fuzzy matching)

To get the most "complete" matching capabilities, you **must** install the **APOC** (Awesome Procedures on Cypher) plugin, which is the standard utility library for Neo4j.

Here is the complete list of available partial matching features:

### 1. Advanced Similarity & Distance (via APOC)
These functions are essential for "fuzzy" matching, spell checking, and finding similar strings based on edit distance.
*   **Levenshtein Distance:** Calculates the number of single-character edits (insertions, deletions, or substitutions) required to change one string into the other.
    *   `apoc.text.distance(text1, text2)` → Returns matching distance (Integer).
    *   `apoc.text.levenshteinDistance(text1, text2)` → Alias for the above.
    *   `apoc.text.levenshteinSimilarity(text1, text2)` → Returns a normalized similarity score between 0.0 and 1.0.
*   **Fuzzy Match (Boolean):** A simplified boolean check based on Levenshtein distance. It automatically adjusts the tolerance based on string length.
    *   `apoc.text.fuzzyMatch(text1, text2)` → Returns `true` or `false`.
*   **Jaro-Winkler Distance:** Often better for short strings (like names) as it gives more weight to the beginning of the string.
    *   `apoc.text.jaroWinklerDistance(text1, text2)` → Returns a similarity score between 0.0 and 1.0.
*   **Sørensen–Dice Coefficient:** A statistic used for comparing the similarity of two samples.
    *   `apoc.text.sorensenDiceSimilarity(text1, text2)` → Returns a similarity score.
*   **Hamming Distance:** Measures the distance between two strings of **equal length**.
    *   `apoc.text.hammingDistance(text1, text2)`
*   **Double Metaphone / Phonetic:** Matches strings based on how they **sound** (e.g., "Smith" vs. "Smythe").
    *   `apoc.text.phonetic(text)` → Returns the US_ENGLISH Soundex encoding.
    *   `apoc.text.doubleMetaphone(text)` → Returns the Double Metaphone encoding (more accurate than Soundex).
    *   `apoc.text.phoneticDelta(text1, text2)` → Returns the difference between the soundex encodings.

### 2. Native Cypher Partial Matches
These are built-in operators available in standard Cypher without any plugins.
*   **Prefix Match:** `STARTS WITH` (e.g., `WHERE n.name STARTS WITH 'Neo'`)
*   **Suffix Match:** `ENDS WITH` (e.g., `WHERE n.name ENDS WITH '4j'`)
*   **Substring Match:** `CONTAINS` (e.g., `WHERE n.name CONTAINS 'eo4'`)
*   **Regular Expressions:** Full Regex support for complex patterns.
    *   `=~` operator (e.g., `WHERE n.name =~ '(?i).*neo.*'`) - *(Note: `(?i)` makes it case-insensitive)*

### 3. Full-Text Search Index (Lucene-based)
For searching across millions of nodes efficiently, you should use **Full-Text Indexes**. This uses the Apache Lucene engine under the hood.
*   **Fuzzy Search (`~`):** You can use the tilde `~` symbol to find words with similar spelling.
    *   *Query:* `CALL db.index.fulltext.queryNodes("myIndex", "name:Neo4j~")`
    *   *Result:* Matches "Neo4j", "Ne04j", "Nio4j", etc.
*   **Wildcard Search (`*` and `?`):**
    *   `*` matches multiple characters (e.g., `Neo*`).
    *   `?` matches a single character (e.g., `Te?t`).

### 4. Text Cleaning & Normalization (Helper Functions)
Sometimes "matching" requires cleaning the data first to ignore messy characters.
*   **Clean Text:** Strips all non-alphanumeric characters and converts to lowercase.
    *   `apoc.text.clean(text)` → Useful for comparing "Ph.D." and "phd".
*   **Compare Cleaned:**
    *   `apoc.text.compareCleaned(text1, text2)` → Returns `true` if they match after cleaning.
*   **Regex Replace:**
    *   `apoc.text.replace(text, regex, replacement)`

### 5. Longest Common Substring (LCS)
*   **Status:** There is **no direct function** named `longestCommonSubstring` in standard Cypher or the APOC core library.
*   **Workaround:** You generally have to solve this by generating all substrings or using a custom user-defined function (UDF) in Java.
    *   *Note:* If you need **Longest Common Subsequence** (not substring), you can sometimes approximate this using the *edit distance* (since edit distance effectively measures the characters they *don't* have in common).

### Summary Table for Quick Selection

| Goal | Best Tool | Function / Operator |
| :--- | :--- | :--- |
| **Exact Substring** | Native Cypher | `CONTAINS` |
| **Prefix / Suffix** | Native Cypher | `STARTS WITH` / `ENDS WITH` |
| **Typos / Spelling** | APOC | `apoc.text.distance` or `apoc.text.fuzzyMatch` |
| **Name Similarity** | APOC | `apoc.text.jaroWinklerDistance` |
| **Sound / Phonetic** | APOC | `apoc.text.doubleMetaphone` |
| **Search Engine Style** | Full-Text Index | `~` (Fuzzy) or `*` (Wildcard) |