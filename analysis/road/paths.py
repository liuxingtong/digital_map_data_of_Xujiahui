"""
路网最短路径与等时圈
====================
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx


def shortest_path(
    G: "nx.DiGraph",
    source: int,
    target: int,
    weight: str = "length",
) -> list[int]:
    """
    返回最短路径节点序列。
    """
    try:
        import networkx as nx
    except ImportError:
        return []
    try:
        return nx.shortest_path(G, source, target, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def isochrone_nodes(
    G: "nx.DiGraph",
    source: int,
    max_cost: float,
    weight: str = "length",
) -> set[int]:
    """
    从 source 出发，cost 不超过 max_cost 的节点集合。
    max_cost 单位与 weight 一致（如 length 为米，则 max_cost=500 表示 500m）。
    """
    try:
        import networkx as nx
    except ImportError:
        return set()

    lengths = nx.single_source_dijkstra_path_length(G, source, weight=weight)
    return {n for n, c in lengths.items() if c <= max_cost}


def isochrone_edges(
    G: "nx.DiGraph",
    source: int,
    max_cost: float,
    weight: str = "length",
) -> set[tuple[int, int]]:
    """
    从 source 出发，cost 不超过 max_cost 的边集合。
    """
    nodes = isochrone_nodes(G, source, max_cost, weight)
    edges = set()
    for u, v in G.edges():
        if u in nodes and v in nodes:
            edges.add((u, v))
    return edges
