"""
路网边权重挂载
==============
将街景、POI、人口等多维数据挂到路网边上。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import networkx as nx
    import pandas as pd


def get_edge_midpoint(G: "nx.DiGraph", u: int, v: int) -> tuple[float, float] | None:
    """获取边 (u,v) 中点经纬度。"""
    if u not in G.nodes or v not in G.nodes:
        return None
    lon_u = G.nodes[u].get("lon") or G.nodes[u].get("x")
    lat_u = G.nodes[u].get("lat") or G.nodes[u].get("y")
    lon_v = G.nodes[v].get("lon") or G.nodes[v].get("x")
    lat_v = G.nodes[v].get("lat") or G.nodes[v].get("y")
    if lon_u is None or lat_u is None or lon_v is None or lat_v is None:
        return None
    return ((lon_u + lon_v) / 2, (lat_u + lat_v) / 2)


def attach_streetview_scores(
    G: "nx.DiGraph",
    streetview_df: "pd.DataFrame",
    indicator: str = "ART_Score",
) -> None:
    """
    将街景指标挂到边上：取最近街景点的值。
    使用 haversine 距离（米），坐标需为 WGS84。
    原地修改 G 的边属性。
    """
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from utils.coord import haversine_meters

    if "lon" not in streetview_df.columns:
        streetview_df = streetview_df.rename(columns={"lng": "lon"})
    pts = streetview_df[["lon", "lat", indicator]].dropna().values
    if len(pts) == 0:
        return

    # 粗筛半径约 500m（度）
    rough_deg = 500.0 / 111000.0

    for u, v, d in G.edges(data=True):
        mid = get_edge_midpoint(G, u, v)
        if mid is None:
            continue
        lon_m, lat_m = mid
        rough = (
            (pts[:, 0] >= lon_m - rough_deg) & (pts[:, 0] <= lon_m + rough_deg)
            & (pts[:, 1] >= lat_m - rough_deg) & (pts[:, 1] <= lat_m + rough_deg)
        )
        idx_cand = np.where(rough)[0]
        if len(idx_cand) == 0:
            idx_cand = np.arange(len(pts))
        best_idx = idx_cand[0]
        best_dist = haversine_meters(lon_m, lat_m, float(pts[best_idx, 0]), float(pts[best_idx, 1]))
        for i in idx_cand[1:]:
            d_m = haversine_meters(lon_m, lat_m, float(pts[i, 0]), float(pts[i, 1]))
            if d_m < best_dist:
                best_dist = d_m
                best_idx = i
        d[f"streetview_{indicator}"] = float(pts[best_idx, 2])


def attach_poi_density(
    G: "nx.DiGraph",
    poi_df: "pd.DataFrame",
    radius_m: float = 100.0,
) -> None:
    """
    将 POI 密度挂到边上：边中点半径内的 POI 数量。
    使用 haversine 距离（米），坐标需为 WGS84。

    Args:
        radius_m: 半径（米），默认 100m
    """
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from utils.coord import haversine_meters

    lon_col = "lon" if "lon" in poi_df.columns else "lng"
    pois = poi_df[[lon_col, "lat"]].values
    # 粗筛用度（100m ≈ 0.001 度）
    radius_deg = radius_m / 111000.0

    for u, v, d in G.edges(data=True):
        mid = get_edge_midpoint(G, u, v)
        if mid is None:
            continue
        lon_m, lat_m = mid
        rough = (
            (pois[:, 0] >= lon_m - radius_deg) & (pois[:, 0] <= lon_m + radius_deg)
            & (pois[:, 1] >= lat_m - radius_deg) & (pois[:, 1] <= lat_m + radius_deg)
        )
        idx = np.where(rough)[0]
        count = 0
        for i in idx:
            if haversine_meters(lon_m, lat_m, float(pois[i, 0]), float(pois[i, 1])) <= radius_m:
                count += 1
        d["poi_count"] = count


def attach_population(
    G: "nx.DiGraph",
    population_raster_path: str | Path,
) -> None:
    """
    将人口栅格值挂到边中点。
    """
    try:
        import rasterio
    except ImportError:
        return

    path = Path(population_raster_path)
    if not path.exists():
        return

    with rasterio.open(path) as src:
        for u, v, d in G.edges(data=True):
            mid = get_edge_midpoint(G, u, v)
            if mid is None:
                continue
            lon_m, lat_m = mid
            try:
                row, col = src.index(lon_m, lat_m)
                if 0 <= row < src.height and 0 <= col < src.width:
                    val = float(src.read(1)[row, col])
                    if src.nodata is not None and val == src.nodata:
                        val = 0
                    d["population"] = max(0, val)
            except Exception:
                pass
