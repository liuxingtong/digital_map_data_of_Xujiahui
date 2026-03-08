"""
路网数据加载器
==============
从 Excel 加载徐家汇路网边列表，用 OSMnx 补全节点坐标，构建 NetworkX 图。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    import networkx as nx

# 徐家汇边界 (lon_min, lon_max, lat_min, lat_max)
XUJIAHUI_BOUNDS = (121.37, 121.48, 31.12, 31.23)

# Excel 列名（按位置，兼容编码问题）
EDGE_COLUMNS = [
    "start_node_id",
    "end_node_id",
    "street_name",
    "highway_type",
    "direction",
    "lanes",
    "length_m",
    "speed_limit",
    "osm_highway",
]


def load_road_edges(excel_path: str | Path) -> pd.DataFrame:
    """
    加载路网 Excel 边列表。
    列顺序：起始节点_ID, 终止节点_ID, 地址名称, 道路功能分类, 行进方向, 车道数, 长度(米), 限速, OSM原始标签

    Returns:
        DataFrame 含 start_node_id, end_node_id, length_m, direction, highway_type 等
    """
    path = Path(excel_path)
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_excel(path)
    # 按位置重命名（兼容编码）
    n = min(len(EDGE_COLUMNS), len(df.columns))
    df = df.rename(columns={df.columns[i]: EDGE_COLUMNS[i] for i in range(n)})

    df["length_m"] = pd.to_numeric(df["length_m"], errors="coerce")
    df = df.dropna(subset=["start_node_id", "end_node_id", "length_m"])
    df["start_node_id"] = df["start_node_id"].astype(int)
    df["end_node_id"] = df["end_node_id"].astype(int)
    return df.reset_index(drop=True)


def fetch_node_coordinates_osmnx(
    bbox: tuple[float, float, float, float] | None = None,
    node_ids: set[int] | None = None,
) -> dict[int, tuple[float, float]]:
    """
    用 OSMnx 下载徐家汇路网，提取节点坐标。

    Args:
        bbox: (lon_min, lon_max, lat_min, lat_max)，默认徐家汇
        node_ids: 若指定，只返回这些节点的坐标（未找到的会缺失）

    Returns:
        {node_id: (lon, lat), ...}
    """
    try:
        import osmnx as ox
    except ImportError:
        raise ImportError("请安装 osmnx: pip install osmnx")

    bbox = bbox or XUJIAHUI_BOUNDS
    lon_min, lon_max, lat_min, lat_max = bbox
    # OSMnx v2+: bbox=(left, bottom, right, top) = (lon_min, lat_min, lon_max, lat_max)
    bbox_tuple = (lon_min, lat_min, lon_max, lat_max)

    G = ox.graph_from_bbox(bbox=bbox_tuple, network_type="walk")
    coords = {}
    for nid, data in G.nodes(data=True):
        x = data.get("x")
        y = data.get("y")
        if x is not None and y is not None:
            coords[int(nid)] = (float(x), float(y))

    if node_ids:
        return {n: coords[n] for n in node_ids if n in coords}
    return coords


def build_networkx_graph(
    edges_df: pd.DataFrame,
    node_coords: dict[int, tuple[float, float]] | None = None,
) -> "nx.DiGraph":
    """
    从边列表构建 NetworkX 有向图。

    Args:
        edges_df: 含 start_node_id, end_node_id, length_m, direction
        node_coords: 节点坐标 {node_id: (lon, lat)}，可选

    Returns:
        NetworkX DiGraph，边属性含 length, highway_type 等
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("请安装 networkx: pip install networkx")

    G = nx.DiGraph()

    for _, row in edges_df.iterrows():
        u = int(row["start_node_id"])
        v = int(row["end_node_id"])
        length = float(row["length_m"])
        highway = str(row.get("highway_type", ""))
        osm_highway = str(row.get("osm_highway", ""))
        # 步行网络：默认双向可达（行人可逆行机动车单行道）
        G.add_edge(u, v, length=length, highway_type=highway, osm_highway=osm_highway)
        G.add_edge(v, u, length=length, highway_type=highway, osm_highway=osm_highway)

    if node_coords:
        for nid in G.nodes():
            if nid in node_coords:
                lon, lat = node_coords[nid]
                G.nodes[nid]["lon"] = lon
                G.nodes[nid]["lat"] = lat
                G.nodes[nid]["x"] = lon
                G.nodes[nid]["y"] = lat

    return G


def load_road_network_from_osmnx(
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple["nx.DiGraph", pd.DataFrame]:
    """
    当 Excel 不存在时，直接用 OSMnx 从 OpenStreetMap 下载徐家汇步行路网。

    Returns:
        (G, edges_df) - 图与边 DataFrame
    """
    try:
        import networkx as nx
        import osmnx as ox
    except ImportError as e:
        raise ImportError("请安装 osmnx 和 networkx: pip install osmnx networkx") from e

    bbox = bbox or XUJIAHUI_BOUNDS
    lon_min, lon_max, lat_min, lat_max = bbox
    # OSMnx v2+: bbox=(left, bottom, right, top)
    bbox_tuple = (lon_min, lat_min, lon_max, lat_max)
    G_osm = ox.graph_from_bbox(bbox=bbox_tuple, network_type="walk")

    def _parse_maxspeed(v):
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        m = re.search(r"(\d+)", s)
        return int(m.group(1)) if m else None

    def _parse_lanes(v):
        if v is None:
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            s = str(v)
            m = re.search(r"(\d+)", s)
            return int(m.group(1)) if m else None

    # 转为 DiGraph，边属性含 length, highway_type, name, maxspeed, lanes, oneway
    G = nx.DiGraph()
    for u, v, d in G_osm.edges(data=True):
        length = float(d.get("length", 0))
        highway = d.get("highway", "")
        if isinstance(highway, list):
            highway = highway[0] if highway else ""
        highway = str(highway)
        name = d.get("name") or ""
        if isinstance(name, list):
            name = name[0] if name else ""
        name = str(name)
        maxspeed = _parse_maxspeed(d.get("maxspeed"))
        lanes = _parse_lanes(d.get("lanes"))
        oneway = bool(d.get("oneway", False))
        G.add_edge(
            u, v,
            length=length,
            highway_type=highway,
            osm_highway=highway,
            name=name,
            maxspeed=maxspeed,
            lanes=lanes,
            oneway=oneway,
        )
        G.add_edge(
            v, u,
            length=length,
            highway_type=highway,
            osm_highway=highway,
            name=name,
            maxspeed=maxspeed,
            lanes=lanes,
            oneway=oneway,
        )

    for nid, data in G_osm.nodes(data=True):
        if nid in G.nodes:
            x, y = data.get("x"), data.get("y")
            if x is not None and y is not None:
                G.nodes[nid]["lon"] = float(x)
                G.nodes[nid]["lat"] = float(y)
                G.nodes[nid]["x"] = float(x)
                G.nodes[nid]["y"] = float(y)

    edges_list = []
    for u, v, d in G.edges(data=True):
        if u < v:  # 避免重复（双向边只记一条）
            edges_list.append({
                "start_node_id": u,
                "end_node_id": v,
                "length_m": d.get("length", 0),
                "highway_type": d.get("highway_type", ""),
                "name": d.get("name", ""),
                "maxspeed": d.get("maxspeed"),
                "lanes": d.get("lanes"),
                "oneway": d.get("oneway", False),
            })
    edges_df = pd.DataFrame(edges_list) if edges_list else pd.DataFrame(
        columns=["start_node_id", "end_node_id", "length_m", "highway_type", "name", "maxspeed", "lanes", "oneway"]
    )
    return G, edges_df


# 本地 GraphML 文件名（与 Excel 同目录）
GRAPHML_FILENAME = "xujiahui_walk.graphml"


def load_road_network_from_graphml(graphml_path: str | Path) -> tuple["nx.DiGraph", pd.DataFrame]:
    """
    从本地 GraphML 文件加载路网（无需联网）。

    Returns:
        (G, edges_df) - 图与边 DataFrame
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("请安装 networkx: pip install networkx")

    path = Path(graphml_path)
    if not path.exists():
        raise FileNotFoundError(f"路网文件不存在: {path}")

    G = nx.read_graphml(str(path), node_type=int)
    if not G.is_directed():
        G = G.to_directed()

    # GraphML 将属性存为字符串，需转回数值
    for nid in G.nodes():
        for attr in ("x", "y", "lon", "lat"):
            if attr in G.nodes[nid] and G.nodes[nid][attr] is not None:
                try:
                    G.nodes[nid][attr] = float(G.nodes[nid][attr])
                except (ValueError, TypeError):
                    pass
    for u, v, d in G.edges(data=True):
        if "length" in d and d["length"] is not None:
            try:
                d["length"] = float(d["length"])
            except (ValueError, TypeError):
                d["length"] = 0
        if "maxspeed" in d and d["maxspeed"] is not None:
            try:
                d["maxspeed"] = int(float(d["maxspeed"]))
            except (ValueError, TypeError):
                d["maxspeed"] = None
        if "lanes" in d and d["lanes"] is not None:
            try:
                d["lanes"] = int(float(d["lanes"]))
            except (ValueError, TypeError):
                d["lanes"] = None
        if "oneway" in d:
            ov = d["oneway"]
            d["oneway"] = str(ov).lower() in ("true", "1", "yes")

    edges_list = []
    for u, v, d in G.edges(data=True):
        if u < v:
            edges_list.append({
                "start_node_id": u,
                "end_node_id": v,
                "length_m": d.get("length", 0),
                "highway_type": str(d.get("highway_type", "")),
                "name": str(d.get("name", "")),
                "maxspeed": d.get("maxspeed"),
                "lanes": d.get("lanes"),
                "oneway": d.get("oneway", False),
            })
    edges_df = pd.DataFrame(edges_list) if edges_list else pd.DataFrame(
        columns=["start_node_id", "end_node_id", "length_m", "highway_type", "name", "maxspeed", "lanes", "oneway"]
    )
    return G, edges_df


def save_road_network_to_graphml(G: "nx.DiGraph", graphml_path: str | Path) -> None:
    """将路网保存为本地 GraphML 文件。GraphML 不支持 None，需替换为可序列化值。"""
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("请安装 networkx: pip install networkx")

    path = Path(graphml_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    G_out = G.copy()
    for u, v, d in G_out.edges(data=True):
        if d.get("maxspeed") is None:
            d["maxspeed"] = 0
        if d.get("lanes") is None:
            d["lanes"] = 0
        if d.get("name") is None:
            d["name"] = ""
    nx.write_graphml(G_out, str(path))


def load_road_network(
    excel_path: str | Path,
    with_coordinates: bool = True,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple["nx.DiGraph", pd.DataFrame]:
    """
    一站式加载：优先本地 GraphML → Excel 边列表 + OSMnx 补全坐标 → OSMnx 在线下载。
    本地文件 xujiahui_walk.graphml 存在时直接加载，无需联网。

    Returns:
        (G, edges_df) - 图与边 DataFrame（含坐标的边会保留）
    """
    path = Path(excel_path)
    base_dir = path.parent
    graphml_path = base_dir / GRAPHML_FILENAME

    # 优先加载本地 GraphML（执行 python fetch_road_network.py 后生成）
    if graphml_path.exists():
        return load_road_network_from_graphml(graphml_path)

    if not path.exists():
        return load_road_network_from_osmnx(bbox=bbox)

    edges = load_road_edges(excel_path)
    if edges.empty:
        return load_road_network_from_osmnx(bbox=bbox)

    node_coords = None
    if with_coordinates:
        node_ids = set(edges["start_node_id"]) | set(edges["end_node_id"])
        node_coords = fetch_node_coordinates_osmnx(bbox=bbox, node_ids=node_ids)

    G = build_networkx_graph(edges, node_coords)
    return G, edges
