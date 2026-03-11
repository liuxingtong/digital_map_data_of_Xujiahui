"""
CLD 边级变量计算与改造优先级
============================
按 CLD 平台集成优化方案，计算 N01–N17、N_YP、N_GC 的边级值，
并输出改造优先级排序。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx
    import pandas as pd


def _safe_get(d: dict, key: str, default: float = 0.0) -> float:
    v = d.get(key)
    if v is None or (isinstance(v, float) and (v != v)):  # NaN
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _minmax_norm(values: list[float]) -> list[float]:
    """Min-max 归一化至 [0,1]。"""
    if not values:
        return []
    vmin, vmax = min(values), max(values)
    span = vmax - vmin if vmax > vmin else 1.0
    return [(v - vmin) / span for v in values]


def compute_edge_cld_values(G: "nx.DiGraph") -> None:
    """
    计算边级 CLD 变量 N01–N17、N_YP、N_GC，写入边属性。
    需先调用 weights 中的 attach_* 和 compute_edge_traffic_pressure。
    """
    edges = list(G.edges(data=True))
    if not edges:
        return

    # 收集原始值用于归一化
    n01_raw, n02_raw, n03_raw, n06_raw, n07_raw, n08_raw = [], [], [], [], [], []
    n14_raw, n15_raw, n17_raw, n_yp_raw, n_gc_raw = [], [], [], [], []

    for u, v, d in edges:
        # N01 社交场所密度: poi_social + poi_culture + 0.8*poi_medical
        s = _safe_get(d, "poi_social", _safe_get(d, "poi_total", 0) / 3)
        c = _safe_get(d, "poi_culture", 0)
        m = _safe_get(d, "poi_medical", 0)
        n01_raw.append(s + c + 0.8 * m)

        # N02 老年人聚集强度 proxy: pop_65plus
        n02_raw.append(_safe_get(d, "pop_65plus", _safe_get(d, "population", 0)))

        # N03 街道界面活跃度: Shannon_H + Complexity + poi_total
        sh = _safe_get(d, "streetview_Shannon_H", 0)
        cp = _safe_get(d, "streetview_Complexity", 0)
        pt = _safe_get(d, "poi_total", 0)
        n03_raw.append(sh + cp + pt)

        # N06 土地混合度: landuse_shannon
        n06_raw.append(_safe_get(d, "landuse_shannon", 0))

        # N07 绿化遮阴: GVI + Shade_Comfort, 0.6:0.4
        gvi = _safe_get(d, "streetview_GVI", 0)
        sc = _safe_get(d, "streetview_Shade_Comfort", 0)
        n07_raw.append(0.6 * gvi + 0.4 * sc)

        # N08 街道舒适度: GVI + Shade + Ped_Friendly, 0.4:0.3:0.3
        pf = _safe_get(d, "streetview_Ped_Friendly", 0)
        n08_raw.append(0.4 * gvi + 0.3 * sc + 0.3 * pf)

        # N14 空间认知复杂度: Complexity + shannon + poi_total, 0.4:0.35:0.25
        lu_sh = _safe_get(d, "landuse_shannon", 0)
        n14_raw.append(0.4 * cp + 0.35 * lu_sh + 0.25 * pt)

        # N15 认知储备激活: ART_Score
        n15_raw.append(_safe_get(d, "streetview_ART_Score", 0))

        # N17 环境生理压力: Motor_Pressure + edge_traffic_pressure, 0.5:0.5
        mp = _safe_get(d, "streetview_Motor_Pressure", 0)
        tp = _safe_get(d, "edge_traffic_pressure", 0)
        n17_raw.append(0.5 * mp + 0.5 * tp)

        # N_YP 年轻人密度
        n_yp_raw.append(_safe_get(d, "pop_15_59", 0))

        # N_GC 隔代照料: pop_65plus * pop_0_14
        p65 = _safe_get(d, "pop_65plus", 0)
        p014 = _safe_get(d, "pop_0_14", 0)
        n_gc_raw.append(p65 * p014)

    # 归一化
    n01_norm = _minmax_norm(n01_raw)
    n02_norm = _minmax_norm(n02_raw)
    n03_norm = _minmax_norm(n03_raw)
    n06_norm = _minmax_norm(n06_raw)
    n07_norm = _minmax_norm(n07_raw)
    n08_norm = _minmax_norm(n08_raw)
    n14_norm = _minmax_norm(n14_raw)
    n15_norm = _minmax_norm(n15_raw)
    n17_norm = _minmax_norm(n17_raw)
    n_yp_norm = _minmax_norm(n_yp_raw)
    n_gc_norm = _minmax_norm(n_gc_raw)

    for i, (u, v, d) in enumerate(edges):
        d["N01"] = n01_norm[i] if i < len(n01_norm) else 0
        d["N02"] = n02_norm[i] if i < len(n02_norm) else 0
        d["N03"] = n03_norm[i] if i < len(n03_norm) else 0
        d["N06"] = n06_norm[i] if i < len(n06_norm) else 0
        d["N07"] = n07_norm[i] if i < len(n07_norm) else 0
        d["N08"] = n08_norm[i] if i < len(n08_norm) else 0
        d["N14"] = n14_norm[i] if i < len(n14_norm) else 0
        d["N15"] = n15_norm[i] if i < len(n15_norm) else 0
        d["N17"] = n17_norm[i] if i < len(n17_norm) else 0
        d["N_YP"] = n_yp_norm[i] if i < len(n_yp_norm) else 0
        d["N_GC"] = n_gc_norm[i] if i < len(n_gc_norm) else 0


def compute_edge_intervention_priority(
    G: "nx.DiGraph",
    w_n15: float = 0.35,
    w_n02: float = 0.30,
    w_n17_inv: float = 0.25,
    w_betweenness: float = 0.10,
) -> None:
    """
    计算改造优先级：高 N15 + 高 N02 + 低 N17 + 高介数。
    写入 edge_intervention_priority。
    """
    try:
        import networkx as nx
    except ImportError:
        return

    # 节点介数中心性
    betweenness = nx.betweenness_centrality(G, weight="length")
    vmin_b, vmax_b = min(betweenness.values()), max(betweenness.values())
    span_b = vmax_b - vmin_b if vmax_b > vmin_b else 1.0

    for u, v, d in G.edges(data=True):
        n15 = _safe_get(d, "N15", 0)
        n02 = _safe_get(d, "N02", 0)
        n17 = _safe_get(d, "N17", 0)
        b_u = (betweenness.get(u, 0) - vmin_b) / span_b
        b_v = (betweenness.get(v, 0) - vmin_b) / span_b
        b_edge = (b_u + b_v) / 2
        # 低 N17 为优：用 (1 - N17)
        priority = (
            w_n15 * n15
            + w_n02 * n02
            + w_n17_inv * (1 - n17)
            + w_betweenness * b_edge
        )
        d["edge_intervention_priority"] = max(0, min(1, priority))


def edges_to_priority_dataframe(G: "nx.DiGraph") -> "pd.DataFrame":
    """
    将边列表导出为含 CLD 变量与优先级的 DataFrame。
    """
    import pandas as pd

    rows = []
    for u, v, d in G.edges(data=True):
        mid = None
        try:
            from .weights import get_edge_midpoint
            mid = get_edge_midpoint(G, u, v)
        except Exception:
            pass
        lon_m = mid[0] if mid else None
        lat_m = mid[1] if mid else None
        rows.append({
            "u": u,
            "v": v,
            "lon": lon_m,
            "lat": lat_m,
            "length": d.get("length"),
            "N01": d.get("N01"),
            "N02": d.get("N02"),
            "N03": d.get("N03"),
            "N06": d.get("N06"),
            "N07": d.get("N07"),
            "N08": d.get("N08"),
            "N14": d.get("N14"),
            "N15": d.get("N15"),
            "N17": d.get("N17"),
            "N_YP": d.get("N_YP"),
            "N_GC": d.get("N_GC"),
            "priority": d.get("edge_intervention_priority"),
        })
    return pd.DataFrame(rows)
