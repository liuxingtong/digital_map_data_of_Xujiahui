"""
路网 OSM 地图叠加
================
将 NetworkX 路网绘制到 Folium OSM 底图上，支持按 highway/lanes/maxspeed/length 着色。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

# highway 类型 → 颜色（CLD：机动车干道=红，步行=绿）
HIGHWAY_COLORS = {
    "primary": "#dc2626",
    "primary_link": "#dc2626",
    "secondary": "#ea580c",
    "secondary_link": "#ea580c",
    "tertiary": "#f59e0b",
    "tertiary_link": "#f59e0b",
    "trunk": "#b91c1c",
    "trunk_link": "#b91c1c",
    "residential": "#eab308",
    "living_street": "#84cc16",
    "unclassified": "#a3a3a3",
    "service": "#737373",
    "footway": "#22c55e",
    "path": "#16a34a",
    "steps": "#15803d",
    "pedestrian": "#4ade80",
}
DEFAULT_EDGE_COLOR = "#6b7280"


def _get_highway_color(highway_type: str) -> str:
    hw = str(highway_type).lower()
    if "primary" in hw or "trunk" in hw:
        return HIGHWAY_COLORS.get("primary", "#dc2626")
    if "secondary" in hw:
        return HIGHWAY_COLORS.get("secondary", "#ea580c")
    if "tertiary" in hw:
        return HIGHWAY_COLORS.get("tertiary", "#f59e0b")
    if "residential" in hw or "living" in hw:
        return HIGHWAY_COLORS.get("residential", "#eab308")
    if "footway" in hw or "path" in hw or "steps" in hw or "pedestrian" in hw:
        return HIGHWAY_COLORS.get("footway", "#22c55e")
    if "service" in hw:
        return HIGHWAY_COLORS.get("service", "#737373")
    return DEFAULT_EDGE_COLOR


def _get_lanes_color(lanes: int | None, default: str = "#6b7280") -> str:
    if lanes is None or lanes == 0:
        return default
    if lanes >= 4:
        return "#dc2626"
    if lanes >= 3:
        return "#ea580c"
    if lanes >= 2:
        return "#f59e0b"
    return "#22c55e"


def _get_maxspeed_color(maxspeed: int | None, default: str = "#6b7280") -> str:
    if maxspeed is None or maxspeed == 0:
        return default
    if maxspeed >= 60:
        return "#dc2626"
    if maxspeed >= 50:
        return "#ea580c"
    if maxspeed >= 40:
        return "#f59e0b"
    if maxspeed >= 30:
        return "#eab308"
    return "#22c55e"


def _get_length_color(length: float, min_len: float, max_len: float, default: str = "#6b7280") -> str:
    if max_len <= min_len:
        return default
    t = (length - min_len) / (max_len - min_len)
    if t < 0.33:
        return "#22c55e"
    if t < 0.66:
        return "#eab308"
    return "#dc2626"


def _get_priority_color(priority: float, default: str = "#6b7280") -> str:
    """改造优先级：高=红（优先改造），低=灰。固定阈值。"""
    if priority is None or (isinstance(priority, float) and priority != priority):
        return default
    p = max(0, min(1, float(priority)))
    if p >= 0.8:
        return "#dc2626"
    if p >= 0.6:
        return "#ea580c"
    if p >= 0.4:
        return "#eab308"
    if p >= 0.2:
        return "#84cc16"
    return "#6b7280"


def _get_priority_color_by_percentile(
    priority: float,
    p10: float,
    p25: float,
    p50: float,
    p75: float,
    p90: float,
    default: str = "#6b7280",
) -> str:
    """
    按百分位着色，使红/橙/黄/绿/灰分布更均匀。
    高优先级=红，低优先级=灰。
    """
    if priority is None or (isinstance(priority, float) and priority != priority):
        return default
    p = float(priority)
    if p >= p90:
        return "#b91c1c"   # 深红（Top 10%）
    if p >= p75:
        return "#dc2626"   # 红
    if p >= p50:
        return "#ea580c"   # 橙
    if p >= p25:
        return "#eab308"   # 黄
    if p >= p10:
        return "#84cc16"   # 绿
    return "#6b7280"       # 灰（Bottom 10%）


def create_road_map(
    G: "nx.DiGraph",
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: int = 14,
    viz_mode: str = "highway",
    color: str = "#2563eb",
    weight: int = 2,
    opacity: float = 0.8,
    max_edges: int | None = None,
) -> "folium.Map | None":
    """
    将路网边绘制到 OSM 底图上，支持多种着色模式。

    Args:
        G: 含节点坐标 (lon, lat 或 x, y) 的 NetworkX 图
        map_center: 地图中心 [lat, lon]
        map_zoom: 缩放级别
        viz_mode: 着色模式 - highway | lanes | maxspeed | length | priority
        color: 单色模式下的边颜色（viz_mode 为单色时）
        weight: 边线宽
        opacity: 边透明度
        max_edges: 最大渲染边数，None 表示全部。用于分级渲染，减少卡顿。priority 模式按优先级取高，其他按长度取长。

    Returns:
        folium.Map 或 None（folium 未安装时）
    """
    if not HAS_FOLIUM:
        return None

    if G is None or G.number_of_edges() == 0:
        return None

    m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="OpenStreetMap")

    edges_with_coords = []
    drawn = set()
    for u, v in G.edges():
        if u > v:
            u, v = v, u
        if (u, v) in drawn:
            continue
        drawn.add((u, v))

        nu = G.nodes.get(u, {})
        nv = G.nodes.get(v, {})
        lat_u = nu.get("lat") or nu.get("y")
        lon_u = nu.get("lon") or nu.get("x")
        lat_v = nv.get("lat") or nv.get("y")
        lon_v = nv.get("lon") or nv.get("x")

        if lat_u is None or lon_u is None or lat_v is None or lon_v is None:
            continue

        d = G.edges[u, v]
        edges_with_coords.append(([float(lat_u), float(lon_u)], [float(lat_v), float(lon_v)], d))

    # 分级渲染：限制边数以减少卡顿
    if max_edges is not None and max_edges > 0 and len(edges_with_coords) > max_edges:
        if viz_mode == "priority":
            edges_with_coords.sort(key=lambda x: x[2].get("edge_intervention_priority") or 0, reverse=True)
        else:
            edges_with_coords.sort(key=lambda x: x[2].get("length") or 0, reverse=True)
        edges_with_coords = edges_with_coords[:max_edges]

    if viz_mode == "highway":
        for p1, p2, d in edges_with_coords:
            hw = d.get("highway_type", "")
            edge_color = _get_highway_color(hw)
            name = d.get("name", "")
            length = d.get("length", 0)
            tooltip = f"{hw}" + (f" · {name}" if name else "") + f" · {length:.0f}m"
            folium.PolyLine(
                locations=[p1, p2],
                color=edge_color,
                weight=weight,
                opacity=opacity,
                tooltip=tooltip,
            ).add_to(m)
    elif viz_mode == "lanes":
        for p1, p2, d in edges_with_coords:
            lanes = d.get("lanes")
            edge_color = _get_lanes_color(lanes)
            name = d.get("name", "")
            tooltip = f"lanes={lanes}" + (f" · {name}" if name else "")
            folium.PolyLine(
                locations=[p1, p2],
                color=edge_color,
                weight=weight,
                opacity=opacity,
                tooltip=tooltip,
            ).add_to(m)
    elif viz_mode == "maxspeed":
        for p1, p2, d in edges_with_coords:
            ms = d.get("maxspeed")
            edge_color = _get_maxspeed_color(ms)
            name = d.get("name", "")
            tooltip = f"maxspeed={ms} km/h" + (f" · {name}" if name else "")
            folium.PolyLine(
                locations=[p1, p2],
                color=edge_color,
                weight=weight,
                opacity=opacity,
                tooltip=tooltip,
            ).add_to(m)
    elif viz_mode == "length":
        lengths = [d.get("length", 0) for _, _, d in edges_with_coords]
        min_len = min(lengths) if lengths else 0
        max_len = max(lengths) if lengths else 1
        for p1, p2, d in edges_with_coords:
            ln = float(d.get("length", 0))
            edge_color = _get_length_color(ln, min_len, max_len)
            name = d.get("name", "")
            tooltip = f"{ln:.0f}m" + (f" · {name}" if name else "")
            folium.PolyLine(
                locations=[p1, p2],
                color=edge_color,
                weight=weight,
                opacity=opacity,
                tooltip=tooltip,
            ).add_to(m)
    elif viz_mode == "priority":
        prio_vals = []
        for _, _, d in edges_with_coords:
            p = d.get("edge_intervention_priority")
            if p is not None and not (isinstance(p, float) and p != p):
                prio_vals.append(float(p))
        if prio_vals:
            try:
                import numpy as np
                arr = np.array(prio_vals)
                p10 = float(np.percentile(arr, 10))
                p25 = float(np.percentile(arr, 25))
                p50 = float(np.percentile(arr, 50))
                p75 = float(np.percentile(arr, 75))
                p90 = float(np.percentile(arr, 90))
            except ImportError:
                s = sorted(prio_vals)
                n = len(s)
                idx = lambda q: min(int(n * q / 100), n - 1) if n else 0
                p10 = s[idx(10)] if n else 0.5
                p25 = s[idx(25)] if n else 0.5
                p50 = s[idx(50)] if n else 0.5
                p75 = s[idx(75)] if n else 0.5
                p90 = s[idx(90)] if n else 0.5
        else:
            p10 = p25 = p50 = p75 = p90 = 0.5
        for p1, p2, d in edges_with_coords:
            prio = d.get("edge_intervention_priority")
            edge_color = _get_priority_color_by_percentile(prio, p10, p25, p50, p75, p90)
            name = d.get("name", "")
            n15 = d.get("N15", 0)
            n02 = d.get("N02", 0)
            n17 = d.get("N17", 0)
            tooltip = f"优先级={prio:.2f}" + (f" · {name}" if name else "")
            tooltip += f" · N15={n15:.2f} N02={n02:.2f} N17={n17:.2f}"
            folium.PolyLine(
                locations=[p1, p2],
                color=edge_color,
                weight=weight,
                opacity=opacity,
                tooltip=tooltip,
            ).add_to(m)
    else:
        for p1, p2, d in edges_with_coords:
            folium.PolyLine(
                locations=[p1, p2],
                color=color,
                weight=weight,
                opacity=opacity,
            ).add_to(m)

    folium.LayerControl().add_to(m)
    return m
