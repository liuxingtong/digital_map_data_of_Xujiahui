"""
路网边权重挂载
==============
将街景、POI、人口、用地等多维数据挂到路网边上。
供 CLD 平台集成与改造优先级计算使用。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import networkx as nx
    import pandas as pd

# CLD 街景指标：供 attach_streetview_scores_multi 批量挂载
STREETVIEW_CLD_INDICATORS = [
    "GVI", "Shade_Comfort", "ART_Score", "Shannon_H", "Complexity", "Motor_Pressure",
    "Ped_Friendly",
]


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


def attach_streetview_scores_multi(
    G: "nx.DiGraph",
    streetview_df: "pd.DataFrame",
    indicators: list[str] | None = None,
) -> None:
    """
    批量将多个街景指标挂到边上，取最近街景点的值。
    原地修改 G 的边属性，写入 streetview_{indicator}。
    """
    indicators = indicators or STREETVIEW_CLD_INDICATORS
    for ind in indicators:
        if ind in streetview_df.columns:
            attach_streetview_scores(G, streetview_df, indicator=ind)


def attach_poi_by_category(
    G: "nx.DiGraph",
    poi_df: "pd.DataFrame",
    radius_m: float = 100.0,
    category_col: str = "group",
) -> None:
    """
    按类别将 POI 数量挂到边上：边中点半径内的 POI 数量。
    写入 poi_social, poi_medical, poi_culture, poi_total。
    若 poi_df 无 category_col，则仅 poi_total。
    """
    import sys
    import pandas as pd
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from utils.coord import haversine_meters

    lon_col = "lon" if "lon" in poi_df.columns else "lng"
    if "lon" not in poi_df.columns and "lng" in poi_df.columns:
        poi_df = poi_df.copy()
        poi_df["lon"] = poi_df["lng"]

    radius_deg = radius_m / 111000.0

    # 社交/医疗/文化映射：POI 文件名或 group 字段
    SOCIAL_KEYWORDS = {"社交餐饮", "社交", "餐饮"}
    MEDICAL_KEYWORDS = {"医疗保健", "医疗"}
    CULTURE_KEYWORDS = {"文化地标", "文化"}
    def _group_key(g) -> str:
        if pd.isna(g):
            return "other"
        g = str(g).strip()
        for k in SOCIAL_KEYWORDS:
            if k in g:
                return "social"
        for k in MEDICAL_KEYWORDS:
            if k in g:
                return "medical"
        for k in CULTURE_KEYWORDS:
            if k in g:
                return "culture"
        return "other"

    has_category = category_col in poi_df.columns
    if has_category:
        poi_df = poi_df.copy()
        poi_df["_clade_key"] = poi_df[category_col].apply(_group_key)

    poi_coords = poi_df[[lon_col, "lat"]].values
    poi_keys = poi_df["_clade_key"].values if has_category else None

    for u, v, d in G.edges(data=True):
        mid = get_edge_midpoint(G, u, v)
        if mid is None:
            continue
        lon_m, lat_m = mid
        rough = (
            (poi_coords[:, 0] >= lon_m - radius_deg) & (poi_coords[:, 0] <= lon_m + radius_deg)
            & (poi_coords[:, 1] >= lat_m - radius_deg) & (poi_coords[:, 1] <= lat_m + radius_deg)
        )
        idx = np.where(rough)[0]
        social = medical = culture = total = 0
        for i in idx:
            if haversine_meters(lon_m, lat_m, float(poi_coords[i, 0]), float(poi_coords[i, 1])) <= radius_m:
                total += 1
                if has_category and poi_keys is not None:
                    k = poi_keys[i]
                    if k == "social":
                        social += 1
                    elif k == "medical":
                        medical += 1
                    elif k == "culture":
                        culture += 1
        d["poi_total"] = total
        if has_category:
            d["poi_social"] = social
            d["poi_medical"] = medical
            d["poi_culture"] = culture


def attach_landuse(
    G: "nx.DiGraph",
    landuse_grid_df: "pd.DataFrame",
) -> None:
    """
    将用地网格指标挂到边上：边中点取最近网格的 shannon, green_rate, n_types。
    landuse_grid_df 需含 lon, lat, shannon, green_rate, n_types 列。
    """
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from utils.coord import haversine_meters

    lon_col = "lon" if "lon" in landuse_grid_df.columns else "lng"
    if lon_col != "lon":
        landuse_grid_df = landuse_grid_df.copy()
        landuse_grid_df["lon"] = landuse_grid_df[lon_col]
    pts = landuse_grid_df[["lon", "lat", "shannon", "green_rate", "n_types"]].dropna().values
    if len(pts) == 0:
        return

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
            dm = haversine_meters(lon_m, lat_m, float(pts[i, 0]), float(pts[i, 1]))
            if dm < best_dist:
                best_dist = dm
                best_idx = i
        d["landuse_shannon"] = float(pts[best_idx, 2])
        d["landuse_green_rate"] = float(pts[best_idx, 3])
        d["landuse_n_types"] = int(pts[best_idx, 4]) if not np.isnan(pts[best_idx, 4]) else 0


def attach_population_multiage(
    G: "nx.DiGraph",
    population_raster_paths: dict[str, str | Path],
) -> None:
    """
    将多年龄段人口栅格挂到边中点。
    population_raster_paths: {"pop_65plus": path, "pop_15_59": path, "pop_0_14": path}
    写入 pop_65plus, pop_15_59, pop_0_14。
    """
    try:
        import rasterio
    except ImportError:
        return

    for key, path in population_raster_paths.items():
        path = Path(path)
        if not path.exists():
            continue
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
                        d[key] = max(0, val)
                except Exception:
                    pass


MOTOR_HIGHWAY_TYPES = {
    "primary", "secondary", "tertiary", "trunk", "motorway",
    "primary_link", "secondary_link", "tertiary_link", "trunk_link", "motorway_link",
}


def compute_edge_traffic_pressure(G: "nx.DiGraph") -> None:
    """
    计算边级车流量/噪声代理（N09/N11），写入 edge_traffic_pressure。
    公式：motor_flag × (lanes/4) × (maxspeed/60)，归一化至 [0,1]。
    """
    values = []
    for u, v, d in G.edges(data=True):
        hw = str(d.get("highway_type", "") or d.get("osm_highway", "")).lower()
        motor = 1.0 if any(t in hw for t in MOTOR_HIGHWAY_TYPES) else 0.0
        lanes = d.get("lanes")
        lanes = int(lanes) if lanes is not None else 2
        lanes = max(1, min(lanes, 8))
        maxspeed = d.get("maxspeed")
        maxspeed = int(maxspeed) if maxspeed is not None else 30
        maxspeed = max(10, min(maxspeed, 120))
        raw = motor * (lanes / 4.0) * (maxspeed / 60.0)
        values.append((u, v, raw))

    if not values:
        return
    raw_vals = [v[2] for v in values]
    vmin, vmax = min(raw_vals), max(raw_vals)
    span = vmax - vmin if vmax > vmin else 1.0
    for u, v, raw in values:
        norm = (raw - vmin) / span
        G.edges[u, v]["edge_traffic_pressure"] = float(norm)
