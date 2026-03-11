"""
用地高级指标
============
Shannon 多样性熵、绿地率、混合用途比例。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import geopandas as gpd
    import pandas as pd

from utils.coord import ANALYSIS_CRS, STORAGE_CRS

# 绿地类型（OSM landuse/leisure/natural 标签）
GREEN_TYPES = {
    "park", "grass", "meadow", "forest", "garden", "wood", "scrub",
    "recreation_ground", "playground", "pitch", "nature_reserve",
    "allotments", "woodland", "greenfield",
}

# 混合用途：商业+居住+休闲中至少两类
COMMERCIAL_TYPES = {"commercial", "retail", "office"}
RESIDENTIAL_TYPES = {"residential"}
LEISURE_TYPES = {"park", "leisure", "recreation_ground", "playground", "sports_centre", "pitch", "garden"}


def _get_landuse_type(row) -> str:
    """从 OSM 属性提取用地类型。"""
    import pandas as pd
    for col in ["landuse", "leisure", "natural"]:
        if col in row.index and pd.notna(row.get(col)):
            val = str(row[col]).strip()
            if val and val.lower() not in ("yes", "no"):
                return val.lower()
    return "other"


def compute_landuse_advanced_metrics(
    gdf: "gpd.GeoDataFrame | None",
    grid_size_m: float = 250.0,
) -> dict:
    """
    计算用地高级指标：Shannon 熵、绿地率、混合用途比例。

    Args:
        gdf: 用地 GeoDataFrame（含 geometry）
        grid_size_m: 混合用途分析的网格边长（米）

    Returns:
        {
            "shannon_entropy": float,
            "green_space_rate_pct": float,
            "mixed_use_ratio_pct": float,
        }
    """
    if gdf is None or len(gdf) == 0:
        return {
            "shannon_entropy": 0.0,
            "green_space_rate_pct": 0.0,
            "mixed_use_ratio_pct": 0.0,
        }

    try:
        import geopandas as gpd
    except ImportError:
        return {"shannon_entropy": 0.0, "green_space_rate_pct": 0.0, "mixed_use_ratio_pct": 0.0}

    gdf = gdf.copy()
    if "landuse_type" not in gdf.columns:
        gdf["landuse_type"] = gdf.apply(_get_landuse_type, axis=1)

    # 投影到 UTM 以计算面积（平方米）
    if gdf.crs is None:
        gdf.set_crs(STORAGE_CRS, inplace=True)
    gdf_utm = gdf.to_crs(ANALYSIS_CRS)
    gdf_utm["_area"] = gdf_utm.geometry.area

    total_area = gdf_utm["_area"].sum()
    if total_area <= 0:
        return {"shannon_entropy": 0.0, "green_space_rate_pct": 0.0, "mixed_use_ratio_pct": 0.0}

    # 1. Shannon 熵：H = -sum(p_i * log(p_i))，p_i = area_i / total_area
    area_by_type = gdf_utm.groupby("landuse_type")["_area"].sum()
    p = area_by_type / total_area
    p = p[p > 0]
    shannon = -sum(pi * math.log(pi) for pi in p)
    shannon = round(shannon, 4)

    # 2. 绿地率：绿地面积 / 总面积
    green_area = gdf_utm[
        gdf_utm["landuse_type"].str.lower().isin(GREEN_TYPES)
    ]["_area"].sum()
    green_rate = float(round(green_area / total_area * 100, 2))

    # 3. 混合用途比例：250m 网格中，至少含 2 类用地的网格占比
    from shapely.geometry import box
    bounds = gdf_utm.total_bounds
    xmin, ymin, xmax, ymax = bounds

    cells = []
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            cells.append(box(x, y, x + grid_size_m, y + grid_size_m))
            y += grid_size_m
        x += grid_size_m

    cells_gdf = gpd.GeoDataFrame(
        {"geometry": cells},
        crs=ANALYSIS_CRS,
    )
    # 空间连接：每个网格与哪些用地相交
    joined = gpd.sjoin(cells_gdf, gdf_utm[["landuse_type", "geometry"]], how="inner", predicate="intersects")
    # 每个网格内不同用地类型数
    n_types_per_cell = joined.groupby(joined.index)["landuse_type"].nunique()
    cells_with_landuse = len(n_types_per_cell)
    cells_mixed = (n_types_per_cell >= 2).sum()
    mixed_ratio = float(round(cells_mixed / cells_with_landuse * 100, 2)) if cells_with_landuse > 0 else 0.0

    return {
        "shannon_entropy": shannon,
        "green_space_rate_pct": green_rate,
        "mixed_use_ratio_pct": mixed_ratio,
    }


def compute_landuse_grid_metrics(
    gdf: "gpd.GeoDataFrame | None",
    grid_size_m: float = 250.0,
) -> "pd.DataFrame | None":
    """
    计算每个网格的 Shannon 熵、绿地率、混合用途（类型数），返回含 lon, lat, shannon, green_rate, n_types 的 DataFrame。
    供与街景模块相同的高级分析（散点图、热力图、KDE、等值线、雷达图）使用。

    Returns:
        DataFrame 含 lon, lat, shannon, green_rate, n_types 列，或 None
    """
    import pandas as pd

    if gdf is None or len(gdf) == 0:
        return None

    try:
        import geopandas as gpd
        from shapely.geometry import box
        from utils.coord import transform_to_wgs84
    except ImportError:
        return None

    gdf = gdf.copy()
    if "landuse_type" not in gdf.columns:
        gdf["landuse_type"] = gdf.apply(_get_landuse_type, axis=1)

    if gdf.crs is None:
        gdf.set_crs(STORAGE_CRS, inplace=True)
    gdf_utm = gdf.to_crs(ANALYSIS_CRS)

    bounds = gdf_utm.total_bounds
    xmin, ymin, xmax, ymax = bounds

    cells = []
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            cells.append(box(x, y, x + grid_size_m, y + grid_size_m))
            y += grid_size_m
        x += grid_size_m

    cells_gdf = gpd.GeoDataFrame({"geometry": cells}, crs=ANALYSIS_CRS)
    joined = gpd.sjoin(cells_gdf, gdf_utm[["landuse_type", "geometry"]], how="inner", predicate="intersects")

    # 每个网格内：按类型计数
    type_counts = joined.groupby(joined.index)["landuse_type"].value_counts()
    rows = []
    for idx in joined.index.unique():
        counts = type_counts.loc[idx]
        total = counts.sum()
        if total <= 0:
            continue
        types_in_cell = counts.index.tolist()
        n_types = len(types_in_cell)

        # Shannon
        p = counts / total
        p = p[p > 0]
        shannon = -sum(pi * math.log(pi) for pi in p)

        # 绿地率（该网格内绿地类型占比）
        green_count = sum(counts[t] for t in GREEN_TYPES if t in counts.index)
        green_rate = green_count / total * 100

        cell = cells_gdf.loc[idx, "geometry"]
        cx, cy = cell.centroid.x, cell.centroid.y
        lon, lat = transform_to_wgs84(cx, cy)
        rows.append({
            "lon": lon,
            "lat": lat,
            "shannon": round(shannon, 4),
            "green_rate": round(green_rate, 2),
            "n_types": n_types,
        })

    if not rows:
        return None
    return pd.DataFrame(rows)


def compute_grid_shannon_entropy(
    gdf: "gpd.GeoDataFrame | None",
    grid_size_m: float = 250.0,
) -> "pd.DataFrame | None":
    """
    兼容接口：返回含 lon, lat, shannon 的 DataFrame。
    建议使用 compute_landuse_grid_metrics 获取完整指标。
    """
    df = compute_landuse_grid_metrics(gdf, grid_size_m)
    if df is None:
        return None
    return df[["lon", "lat", "shannon"]].copy()
