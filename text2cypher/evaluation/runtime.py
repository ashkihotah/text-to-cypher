from typing import Any, Dict, Hashable, List, Set, Tuple

from langchain_neo4j import Neo4jGraph
from neo4j import GraphDatabase, Query
from neo4j.exceptions import (
    CypherSyntaxError,
    DatabaseError,
    CypherTypeError,
    ClientError,
)

def rowsim(setL: Set, setR: Set) -> float:
    """
    Calculate the similarity between two sets using Jaccard index formula.
    """
    return len(setL.intersection(setR)) / len(setL.union(setR))

def floatify(v: Any) -> Any:
    """
    Attempts to convert a value to a float if it is a string and represents a
    number, or recursively apply the conversion to elements within a list or dict.
    """
    if isinstance(v, str):
        return v
    try:
        f = float(v)
        return f
    except:
        pass
    if isinstance(v, list):
        return [floatify(x) for x in v]
    if isinstance(v, tuple):
        return tuple(floatify(x) for x in v)
    if isinstance(v, dict):
        return {k: floatify(u) for k, u in v.items()}
    return v

def make_hashable(v: Any) -> Hashable:
    """
    Convert a value to a hashable type (needed for set operations).
    """
    float_v = floatify(v)
    if not isinstance(float_v, Hashable) or isinstance(float_v, tuple):
        return str(float_v)
    else:
        return float_v

def make_alignment(dictL: List[Dict], dictR: List[Dict]) -> Tuple[List[Set], List[Set]]:
    """
    Align rows from two lists of dictionaries based on their similarity.
    """
    swap = len(dictL) > len(dictR)

    # Forming set views from the list of dictionaries.
    setViewsL = [{make_hashable(v) for k, v in row.items()} for row in dictL]
    setViewsR = [{make_hashable(v) for k, v in row.items()} for row in dictR]
    if swap:
        setViewsL, setViewsR = setViewsR, setViewsL

    for i in range(len(setViewsL)):
        max_sim = -1
        max_j = -1
        for j in range(i, len(setViewsR)):
            sim = rowsim(setViewsL[i], setViewsR[j])
            if sim > max_sim:
                max_j = j
                max_sim = sim
        tmp = setViewsR[i]
        setViewsR[i] = setViewsR[max_j]
        setViewsR[max_j] = tmp
    if swap:
        setViewsL, setViewsR = setViewsR, setViewsL
    return setViewsL, setViewsR

def df_sim(dictL: List[Dict], dictR: List[Dict], list_view: bool) -> float:
    """
    Calculate the data frame similarity based on either the original row order or an alignment.
    """
    if list_view:
        # Original row order for lists of dictionaries
        view_L = [row.values() for row in dictL]
        view_R = [row.values() for row in dictR]
    else:
        view_L, view_R = make_alignment(dictL, dictR)

    totalSetL = set()
    for i, s in enumerate(view_L):
        for elem in s:
            totalSetL.add((i, make_hashable(elem)))
    totalSetR = set()
    for i, s in enumerate(view_R):
        for elem in s:
            totalSetR.add((i, make_hashable(elem)))
    intersection = totalSetL.intersection(totalSetR)
    union = totalSetL.union(totalSetR)

    if len(union) == 0 and len(intersection) == 0:
        return 1.0
    elif len(union) == 0:
        return 0.0

    return len(intersection) / len(union)

def df_sim_pair(pair_L, pair_R):
    """
    Compute the Jaccard similarity of two data frames (lists of dictionaries),
    taking into account the order of rows if indicated by the involved Cypher queries.
    """
    cypher_L, dict_L = pair_L
    cypher_R, dict_R = pair_R

    return df_sim(dict_L, dict_R, "order by" in f"{cypher_L} {cypher_R}".lower())

def jaccard(query_L: str, query_R: str, neo4j: Neo4jGraph) -> float:
    """
    Compute the Jaccard similarity between the results of two Cypher queries.
    """
    try:
        dict_L = neo4j.query(query_L)
        dict_R = neo4j.query(query_R)
    except Exception as e:
        print(f'When evaluating jaccard encountered exception: {e}')
        return 0.0
    return df_sim(dict_L, dict_R, "order by" in f"{query_L} {query_R}".lower())


def check_validity(query: str, neo4j_driver: GraphDatabase, database: str, timeout: int = 120) -> Tuple[bool, Any]:
    is_executable = True
    is_result_empty = None
    try:
        with neo4j_driver.session(database=database) as session:
            query = Query(query, timeout=timeout)
            result = session.run(query)
            records = list(result)
            if len(records) == 0:
                is_result_empty = True
            else:
                is_result_empty = False
    except (
        CypherSyntaxError,
        DatabaseError,
        CypherTypeError,
        ClientError,
    ) as _:
        is_executable = False
    return is_executable, is_result_empty