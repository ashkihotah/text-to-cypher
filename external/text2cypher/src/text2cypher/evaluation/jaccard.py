from collections import defaultdict
from typing import Any, Dict, Hashable, List, Set, Tuple

import json

# def make_hashable(v: Any) -> Hashable:
#     """
#     A highly optimized conversion of arbitrary data structures into hashable objects.
#     Replaces the slow try/except and recursive 'floatify' pipeline.
#     """
#     v_type = type(v)
    
#     # 1. Fast Path: Primitives are natively hashable
#     if v_type in (int, str, float, bool, type(None)):
#         return v
        
#     # 2. Fast Path: Tuples just need their contents checked
#     if v_type is tuple:
#         return tuple(make_hashable(x) for x in v)
        
#     # 3. Standardize Lists / Sets
#     if isinstance(v, (list, set)):
#         # Provide deterministic order. We use strings to avoid TypeError on mixed types.
#         try:
#             return tuple(sorted((make_hashable(x) for x in v)))
#         except TypeError:
#             return tuple(sorted((make_hashable(x) for x in v), key=str))
            
#     # 4. Standardize Dicts
#     if isinstance(v, dict):
#         # We sort the keys to guarantee dictionary matching regardless of key insertion order
#         return tuple(sorted((k, make_hashable(val)) for k, val in v.items()))
        
#     # 5. C-Optimized Fallback for weird graph objects (Dates, points, geometry, etc.)
#     try:
#         return str(v)
#     except Exception:
#         # Absolute bulletproof fallback
#         return repr(v)

def make_hashable(v: Any) -> Hashable:
    """
    A highly optimized conversion of arbitrary data structures into hashable objects.
    Replaces the slow try/except and recursive pipelines with C-optimized JSON sorting.
    """
    v_type = type(v)
    
    # 1. Fast Path: Primitives are natively hashable
    if v_type in (int, str, float, bool, type(None)):
        return v
        
    # 2. Fast Path: Tuples just need their contents checked
    if v_type is tuple:
        return tuple(make_hashable(x) for x in v)
        
    # 3. Handle complex non-primitives (Dicts, Lists, Sets) natively via C-engine
    if isinstance(v, (dict, list, set)):
        # Sets must be converted to sorted lists for deterministic json dumping
        if isinstance(v, set):
            # Sort the set contents first to ensure determinism
            try:
                v = sorted(list(v))
            except TypeError:
                v = sorted(list(v), key=str)
            
        try:
            # json.dumps runs entirely in C. 
            # sort_keys=True guarantees deterministic dictionary formatting
            return json.dumps(v, sort_keys=True)
        except TypeError:
            # If the object contains non-json-serializable graph objects (like neo4j Dates), fallback
            pass

    # 4. C-Optimized Fallback for weird graph objects (Dates, Node proxies, geometry, etc.)
    try:
        return str(v)
    except Exception:
        return repr(v)

# def make_hashable(v: Any) -> Hashable:
#     """
#     An iterative, stack-based conversion of arbitrary data structures into hashable objects.
#     Replaces recursion to prevent stack overflows and provides better space/time efficiency.
#     """
#     # 1. Fast Path: Primitives are natively hashable
#     v_type = type(v)
#     if v_type in (int, str, float, bool, type(None)):
#         return v
        
#     # Stack stores tuples of (object, is_processed_flag)
#     stack = [(v, False)]
#     results = []

#     while stack:
#         curr, processed = stack.pop()
        
#         if processed:
#             curr_type = type(curr)
#             if curr_type is tuple:
#                 length = len(curr)
#                 items = tuple(results[-length:])
#                 del results[-length:]
#                 results.append(items)
#             elif curr_type is list or curr_type is set:
#                 length = len(curr)
#                 items = results[-length:]
#                 del results[-length:]
#                 try:
#                     results.append(tuple(sorted(items)))
#                 except TypeError:
#                     results.append(tuple(sorted(items, key=lambda x: (str(type(x)), str(x)))))
#             elif isinstance(curr, dict):
#                 length = len(curr) * 2
#                 kv_pairs = results[-length:]
#                 del results[-length:]
#                 paired = [(kv_pairs[i], kv_pairs[i+1]) for i in range(0, length, 2)]
#                 try:
#                     results.append(tuple(sorted(paired)))
#                 except TypeError:
#                     results.append(tuple(sorted(paired, key=lambda x: (str(type(x[0])), str(x[0])))))
#             continue

#         curr_type = type(curr)
#         if curr_type in (int, str, float, bool, type(None)):
#             results.append(curr)
#         elif isinstance(curr, (list, tuple, set)):
#             stack.append((curr, True))
#             for item in reversed(list(curr)):
#                 stack.append((item, False))
#         elif isinstance(curr, dict):
#             stack.append((curr, True))
#             # Reverse items to maintain correct order during pop
#             for k, val in reversed(list(curr.items())):
#                 stack.append((val, False))
#                 stack.append((k, False))
#         else:
#             # Fallback for weird graph objects (Dates, Node proxies, geometry, etc.)
#             try:
#                 results.append(str(curr))
#             except Exception:
#                 results.append(repr(curr))

#     return results[0]

# def floatify(v: Any) -> Any:
#     """
#     Attempts to convert a value to a float if it is a string and represents a
#     number, or recursively apply the conversion to elements within a list or dict.
#     """
#     if isinstance(v, str):
#         return v
#     try:
#         f = float(v)
#         return f
#     except:
#         pass
#     if isinstance(v, list):
#         return [floatify(x) for x in v]
#     if isinstance(v, tuple):
#         return tuple(floatify(x) for x in v)
#     if isinstance(v, dict):
#         return {k: floatify(u) for k, u in v.items()}
#     return v

# def make_hashable(v: Any) -> Hashable:
#     """
#     Convert a value to a hashable type (needed for set operations).
#     """
#     float_v = floatify(v)
#     if not isinstance(float_v, Hashable) or isinstance(float_v, tuple):
#         return str(float_v)
#     else:
#         return float_v


def rowsim(setL: Set, setR: Set) -> float:
    """
    Calculate the similarity between two sets using Jaccard index formula.
    """
    return len(setL.intersection(setR)) / len(setL.union(setR))

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

def greedy_jaccard(dictL: List[Dict], dictR: List[Dict], list_view: bool) -> float:
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



def prepare_sorted_views(dicts: List[Dict]) -> List[Set[Hashable]]:
    """
    Deterministically sorts a list of dictionary rows based on their hashable values.
    Returns a sorted list of value sets, allowing $i$-to-$i$ zipping.
    """
    rows = []
    for row in dicts:
        # Extract and format values into a set of hashables
        hashed_vals = {make_hashable(v) for v in row.values()}
        
        # Create a stable string-based sort key for the row to safely handle 
        # mixed types (int vs str vs None) without raising TypeErrors
        sort_key = tuple(sorted(hashed_vals, key=lambda x: (str(type(x)), str(x))))
        rows.append((sort_key, hashed_vals))
    
    # Sort the rows lexicographically by their stable contents (O(N log N))
    rows.sort(key=lambda x: x[0])
    
    # Return just the raw sets, keeping the newly aligned sorted order
    return [row[1] for row in rows]

def fast_jaccard(dictL: List[Dict], dictR: List[Dict], list_view: bool) -> float:
    """
    $O(N \\log N)$ Sort-and-Zip implementation of dataframe Jaccard similarity.
    Guarantee: Exact matches naturally align and evaluate to 1.0. 
               Produces a valid lower bound of the optimal Jaccard similarity.
    """
    if list_view:
        # If ORDER BY dictates the order, skip sorting and zip in natural form
        view_L = [{make_hashable(v) for v in row.values()} for row in dictL]
        view_R = [{make_hashable(v) for v in row.values()} for row in dictR]
    else:
        # If unordered, synthetically assign an alignment via sorting
        view_L = prepare_sorted_views(dictL)
        view_R = prepare_sorted_views(dictR)

    # Flatten into sets of tuples: (row_index, cell_value)
    totalSetL = set()
    for i, s in enumerate(view_L):
        for elem in s:
            totalSetL.add((i, elem))
            
    totalSetR = set()
    for i, s in enumerate(view_R):
        for elem in s:
            totalSetR.add((i, elem))
            
    intersection = totalSetL.intersection(totalSetR)
    union = totalSetL.union(totalSetR)

    if len(union) == 0 and len(intersection) == 0:
        return 1.0
    elif len(union) == 0:
        return 0.0

    return len(intersection) / len(union)



def hash_row(row: Dict[str, Any]) -> Hashable:
    """
    Transforms a dictionary row into a fully hashable and order-invariant tuple representation.
    This effectively "hashes" the entire row into a single entity to only permit exact binary matches.
    We ignore column names (keys) entirely to accommodate predictions that use different aliases.
    """
    # Extract hashable values and sort them by type and string representation to ensure absolute determinism.
    hashed_vals = [make_hashable(v) for v in row.values()]
    return tuple(sorted(hashed_vals, key=lambda x: (str(type(x)), str(x))))

def exact_match_jaccard(dictL: List[Dict], dictR: List[Dict], list_view: bool) -> float:
    """
    $O(N)$ Exact Matching Jaccard Similarity.
    Rows are treated as atomic entities. Strict binary matching (no partial column overlap credit).
    """
    setL = set()
    setR = set()

    if list_view:
        # If ORDER BY is specified, the row index strictly defines the row's identity
        for i, row in enumerate(dictL):
            setL.add((i, hash_row(row)))
        for i, row in enumerate(dictR):
            setR.add((i, hash_row(row)))
    else:
        # If unordered, we need to treat identical rows as distinct items if they appear multiple times.
        # We pair each hashed row with an auto-incrementing frequency integer.
        countsL = defaultdict(int)
        for row in dictL:
            h = hash_row(row)
            setL.add((h, countsL[h]))
            countsL[h] += 1
            
        countsR = defaultdict(int)
        for row in dictR:
            h = hash_row(row)
            setR.add((h, countsR[h]))
            countsR[h] += 1

    intersection = setL.intersection(setR)
    union = setL.union(setR)

    if len(union) == 0:
        return 1.0

    return len(intersection) / len(union)
