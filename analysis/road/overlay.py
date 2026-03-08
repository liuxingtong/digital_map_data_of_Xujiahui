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


def create_road_map(
    G: "nx.DiGraph",
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: int = 14,
    viz_mode: str = "highway",
    color: str = "#2563eb",
    weight: int = 2,
    opacity: float = 0.8,
) -> "folium.Map | None":
    """
    将路网边绘制到 OSM 底图上，支持多种着色模式。

    Args:
        G: 含节点坐标 (lon, lat 或 x, y) 的 NetworkX 图
        map_center: 地图中心 [lat, lon]
        map_zoom: 缩放级别
        viz_mode: 着色模式 - highway | lanes | maxspeed | length
        color: 单色模式下的边颜色（viz_mode 为单色时）
        weight: 边线宽
        opacity: 边透明度

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
