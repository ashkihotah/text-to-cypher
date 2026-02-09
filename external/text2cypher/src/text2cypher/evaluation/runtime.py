from itertools import product
from collections import defaultdict
import random
import time
import neo4j

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

"""
Some code are adapted from https://github.com/taoyds/test-suite-sql-eval
"""

def to_hashable(obj, unorder_list=True):
    """
    Recursively transforms a list, dictionary, or set into a hashable object.
    Lists and sets are converted to tuples. Dictionaries are converted to tuples of sorted (key, value) pairs.

    Args:
    obj: The object to be transformed into a hashable form.

    Returns:
    A hashable version of the input object.
    """
    if isinstance(obj, (int, float, str, bool, type(None))):
        # These are already hashable
        return obj
    elif isinstance(obj, neo4j.time.Date):
        return obj.iso_format()
    elif isinstance(obj, neo4j.time.DateTime):
        return obj.iso_format()
    elif isinstance(obj, dict):
        # Convert dict to a tuple of sorted key-value pairs
        return tuple(sorted((to_hashable(k, unorder_list=False), to_hashable(v, unorder_list=False)) for k, v in obj.items()))
    elif isinstance(obj, (list, set)):
        # Convert list/set to a tuple
        converted = tuple(to_hashable(item, unorder_list=False) for item in obj)
        if unorder_list:
            try:
                return tuple(sorted(converted))
            except TypeError:
                # If items can't be sorted (mixed types), convert to string for sorting
                return tuple(sorted(converted, key=lambda x: (str(type(x)), str(x))))
        return converted
    elif isinstance(obj, tuple):
        # Keep tuple as is, just convert contents
        return tuple(to_hashable(item, unorder_list=False) for item in obj)
    else:
        # For other types, raise an error or handle as needed
        raise TypeError(f"Unhashable type: {type(obj)}")

def execution_accuracy(
    pred_cypher: str,
    target_cypher: str,
    neo4j_connector: Neo4jGraph,
    timeout: int = 120
) -> float:
    """Execution accuracy for two cypher queries"""
    if pred_cypher == target_cypher:
        return 1.0
    t0 = time.time()
    target_executed = neo4j_connector.query(target_cypher) # , timeout=timeout
    target_seconds = time.time() - t0
    if target_seconds > timeout:
        print(f"Warning: Execution of target cypher query {target_cypher} took longer than {timeout} seconds")
    try:
        pred_executed = neo4j_connector.query(pred_cypher) # , timeout=timeout
        pred_executed = [{k: to_hashable(v) for k, v in record.items()} for record in pred_executed]
    except (
            neo4j.exceptions.CypherSyntaxError,
            neo4j.exceptions.DatabaseError,
            neo4j.exceptions.CypherTypeError,
            neo4j.exceptions.ClientError,
    ) as e:
        return 0.0
    except TypeError as e:
        # TODO: For some queries (e.g. queries that bind the path to a variable), the result is not hashable
        # However, currently we don't have such queries in the benchmark
        # So this exception indicates the predicted Cypher query is incorrect
        return 0.0
    except Exception as e:
        print(f"Warning: Exception {e} occurred while executing the predicted Cypher query {pred_cypher}")
        return 0.0

    target_executed = [{k: to_hashable(v) for k, v in record.items()} for record in target_executed]
    return _compare_execution(
        pred_executed=pred_executed,
        target_executed=target_executed,
        order_matters='order by' in target_cypher.lower()
    )

def permute_tuple(element: Tuple, perm: Tuple) -> Tuple:
    assert len(element) == len(perm)
    return tuple([element[i] for i in perm])

def unorder_row(row: Tuple) -> Tuple:
    return tuple(sorted(row, key=lambda x: str(x) + str(type(x))))

# unorder each row in the table
# [result_1 and result_2 has the same bag of unordered row]
# is a necessary condition of
# [result_1 and result_2 are equivalent in denotation]
def quick_rej(result1: List[Tuple], result2: List[Tuple], order_matters: bool) -> bool:
    s1 = [unorder_row(row) for row in result1]
    s2 = [unorder_row(row) for row in result2]
    if order_matters:
        return s1 == s2
    else:
        return set(s1) == set(s2)

# return whether two bag of relations are equivalent
def multiset_eq(l1: List, l2: List) -> bool:
    if len(l1) != len(l2):
        return False
    d = defaultdict(int)
    for e in l1:
        d[e] = d[e] + 1
    for e in l2:
        d[e] = d[e] - 1
        if d[e] < 0:
            return False
    return True

def get_constraint_permutation(tab1_sets_by_columns: List[Set], result2: List[Tuple]):
    num_cols = len(result2[0])
    perm_constraints = [{i for i in range(num_cols)} for _ in range(num_cols)]
    if num_cols <= 3:
        return product(*perm_constraints)

    # we sample 20 rows and constrain the space of permutations
    for _ in range(20):
        random_tab2_row = random.choice(result2)

        for tab1_col in range(num_cols):
            for tab2_col in set(perm_constraints[tab1_col]):
                if random_tab2_row[tab2_col] not in tab1_sets_by_columns[tab1_col]:
                    perm_constraints[tab1_col].remove(tab2_col)
    return product(*perm_constraints)

# check whether two denotations are correct
def result_eq(result1: List[Tuple], result2: List[Tuple], order_matters: bool) -> bool:
    if len(result1) == 0 and len(result2) == 0:
        return True

    # if length is not the same, then they are definitely different bag of rows
    if len(result1) != len(result2):
        return False

    num_cols = len(result1[0])

    # if the results do not have the same number of columns, they are different
    if len(result2[0]) != num_cols:
        return False

    # unorder each row and compare whether the denotation is the same
    # this can already find most pair of denotations that are different
    if not quick_rej(result1, result2, order_matters):
        return False

    # the rest of the problem is in fact more complicated than one might think
    # we want to find a permutation of column order and a permutation of row order,
    # s.t. result_1 is the same as result_2
    # we return true if we can find such column & row permutations
    # and false if we cannot
    tab1_sets_by_columns = [{row[i] for row in result1} for i in range(num_cols)]

    # on a high level, we enumerate all possible column permutations that might make result_1 == result_2
    # we decrease the size of the column permutation space by the function get_constraint_permutation
    # if one of the permutation make result_1, result_2 equivalent, then they are equivalent
    for perm in get_constraint_permutation(tab1_sets_by_columns, result2):
        if len(perm) != len(set(perm)):
            continue
        if num_cols == 1:
            result2_perm = result2
        else:
            result2_perm = [permute_tuple(element, perm) for element in result2]
        if order_matters:
            if result1 == result2_perm:
                return True
        else:
            # in fact the first condition must hold if the second condition holds
            # but the first is way more efficient implementation-wise
            # and we use it to quickly reject impossible candidates
            if set(result1) == set(result2_perm) and multiset_eq(result1, result2_perm):
                return True
    return False

def to_tuples(result: List[Dict]) -> List[Tuple]:
    keys = list(result[0].keys())
    for row in result:
        assert set(row.keys()) == set(keys)
    return [tuple([row[key] for key in keys]) for row in result] # the table header is removed

def _compare_execution(
        pred_executed: list[dict], target_executed: list[dict], order_matters: bool
) -> float:
    """Execution match considering same order of the output"""
    if not pred_executed and not target_executed:
        return 1.0
    elif not pred_executed or not target_executed:
        return 0.0

    gold_tuples = to_tuples(target_executed)
    pred_tuples = to_tuples(pred_executed)
    return float(result_eq(gold_tuples, pred_tuples, order_matters=order_matters))
