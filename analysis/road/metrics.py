"""
路网图论指标
============
N04 路网连通性、N13 空间认知复杂度等。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx


def compute_n04_connectivity(G: "nx.DiGraph") -> dict:
    """
    N04 路网连通性指标。

    Returns:
        alpha: α 指数 (实际环数/最大可能环数)
        beta: β 指数 (边数/节点数)
        gamma: γ 指数 (实际边数/最大可能边数)
        avg_edge_length: 平均路段长度(m)
        intersection_density: 交叉口密度 (度>=3 的节点数/km²，需面积)
    """
    try:
        import networkx as nx
    except ImportError:
        return {}

    n = G.number_of_nodes()
    e = G.number_of_edges()
    if n < 2:
        return {"alpha": 0, "beta": 0, "gamma": 0, "avg_edge_length": 0}

    # 无向边数（每条有向边算 0.5 对无向）
    e_undir = e / 2 if G.is_directed() else e
    max_edges = n * (n - 1) / 2
    gamma = e_undir / max_edges if max_edges > 0 else 0
    beta = e / n if n > 0 else 0

    # α: 环数/最大环数。(e-n+1)/(2n-5) 平面图近似
    max_cycles = max(0, 2 * n - 5)
    actual_cycles = max(0, e_undir - n + 1)
    alpha = min(1.0, actual_cycles / max_cycles) if max_cycles > 0 else 0

    # 平均路段长度
    lengths = [d.get("length", 0) for _, _, d in G.edges(data=True)]
    avg_len = sum(lengths) / len(lengths) if lengths else 0

    # 交叉口：度>=3 的节点
    if G.is_directed():
        deg = G.out_degree  # 或 in_degree，交叉口看连接数
        intersection_count = sum(1 for _, d in deg() if d >= 3)
    else:
        intersection_count = sum(1 for _, d in G.degree() if d >= 3)

    return {
        "alpha": round(alpha, 4),
        "beta": round(beta, 4),
        "gamma": round(gamma, 4),
        "avg_edge_length_m": round(avg_len, 2),
        "intersection_count": intersection_count,
        "n_nodes": n,
        "n_edges": e,
    }


def compute_intersection_density(
    G: "nx.DiGraph",
    area_km2: float,
) -> float:
    """
    交叉口密度 (个/km²)，N13 第一项。
    """
    m = compute_n04_connectivity(G)
    cnt = m.get("intersection_count", 0)
    return cnt / area_km2 if area_km2 > 0 else 0


def compute_road_summary_stats(G: "nx.DiGraph") -> dict:
    """
    路网汇总统计：步行专用路比例、机动车干道比例、平均路段长度、lanes 覆盖率。
    """
    if G is None or G.number_of_edges() == 0:
        return {}

    MOTOR_TYPES = {"primary", "secondary", "trunk", "primary_link", "secondary_link", "trunk_link"}
    PEDESTRIAN_TYPES = {"footway", "path", "steps", "pedestrian"}

    edges = list(G.edges(data=True))
    n_edges = len(edges)
    n_unique = n_edges // 2 if G.is_directed() else n_edges  # 无向边数

    motor_count = 0
    pedestrian_count = 0
    total_length = 0.0
    lanes_count = 0

    seen = set()
    for u, v, d in edges:
        if u > v:
            u, v = v, u
        if (u, v) in seen:
            continue
        seen.add((u, v))

        hw = str(d.get("highway_type", "")).lower()
        if isinstance(d.get("highway_type"), list):
            hw = str(d.get("highway_type", "")).lower()
        if any(t in hw for t in MOTOR_TYPES):
            motor_count += 1
        if any(t in hw for t in PEDESTRIAN_TYPES):
            pedestrian_count += 1

        total_length += float(d.get("length", 0))
        lanes_val = d.get("lanes")
        if lanes_val is not None and lanes_val != 0:
            lanes_count += 1

    avg_length = total_length / len(seen) if seen else 0
    lanes_coverage = (lanes_count / len(seen) * 100) if seen else 0

    return {
        "n_edges_unique": len(seen),
        "pedestrian_ratio_pct": round(pedestrian_count / len(seen) * 100, 1) if seen else 0,
        "motor_ratio_pct": round(motor_count / len(seen) * 100, 1) if seen else 0,
        "avg_edge_length_m": round(avg_length, 2),
        "lanes_coverage_pct": round(lanes_coverage, 1),
    }


def compute_betweenness_centrality(
    G: "nx.DiGraph",
    weight: str = "length",
) -> dict[int, float]:
    """
    边介数中心性（或节点介数）。
    """
    try:
        import networkx as nx
    except ImportError:
        return {}
    return nx.edge_betweenness_centrality(G, weight=weight)
