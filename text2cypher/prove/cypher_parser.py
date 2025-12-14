import tree_sitter_cypher
from tree_sitter import Language, Parser

CYPHER_LANG = Language(tree_sitter_cypher.language())
parser = Parser(CYPHER_LANG)

query = "MATCH (p:Person)-[:ACTED_IN]->(m:Movie) RETURN p.name"

# Tree-sitter requires bytes
source_bytes = bytes(query, "utf8")
tree = parser.parse(source_bytes)