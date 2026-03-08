"""
用地数据加载器
==============
从 landuse_data 加载 GeoJSON 或 centroid CSV。
OSM 数据为 WGS84，无需纠偏。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    import geopandas as gpd

# 徐家汇边界 (lon_min, lon_max, lat_min, lat_max)
XUJIAHUI_BOUNDS = (121.37, 121.48, 31.12, 31.23)

# 用地类型中文映射
LANDUSE_LABELS = {
    "residential": "居住",
    "commercial": "商业",
    "retail": "零售",
    "industrial": "工业",
    "park": "公园",
    "grass": "草地",
    "meadow": "草地",
    "forest": "林地",
    "water": "水体",
    "school": "学校",
    "university": "大学",
    "college": "学院",
    "hospital": "医院",
    "cemetery": "墓地",
    "construction": "施工",
    "recreation_ground": "休闲用地",
    "allotments": " allotments",
    "farmland": "农田",
    "garages": "车库",
    "depot": "仓库",
    "port": "港口",
    "railway": "铁路",
    "religious": "宗教",
    "sports_centre": "体育中心",
    "pitch": "运动场",
    "playground": "游乐场",
    "garden": "花园",
    "nature_reserve": "自然保护区",
    "scrub": "灌木",
    "wood": "林地",
    "beach": "沙滩",
    "wetland": "湿地",
    "other": "其他",
}


def load_landuse_geojson(geojson_path: str | Path) -> "gpd.GeoDataFrame | None":
    """加载用地 GeoJSON。"""
    try:
        import geopandas as gpd
    except ImportError:
        return None

    path = Path(geojson_path)
    if not path.exists():
        return None
    try:
        return gpd.read_file(path)
    except Exception:
        return None


def load_landuse_centroid(csv_path: str | Path) -> pd.DataFrame | None:
    """加载用地 centroid CSV，供点图/KDE 等使用。"""
    path = Path(csv_path)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="gbk")
    if df.empty or "lon" not in df.columns or "lat" not in df.columns:
        return None
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df = df.dropna(subset=["lon", "lat"])
    return df.reset_index(drop=True)


def load_landuse(
    data_dir: str | Path,
    format: str = "auto",
) -> tuple["gpd.GeoDataFrame | None", pd.DataFrame | None]:
    """
    加载用地数据。

    Args:
        data_dir: landuse_data 目录
        format: "geojson" | "csv" | "auto"（两者都加载）

    Returns:
        (gdf, centroid_df)，若某格式不存在则对应为 None
    """
    data_dir = Path(data_dir)
    gdf = None
    centroid_df = None

    if format in ("geojson", "auto"):
        gdf = load_landuse_geojson(data_dir / "landuse_xujiahui.geojson")
    if format in ("csv", "auto"):
        centroid_df = load_landuse_centroid(data_dir / "landuse_centroid.csv")

    return gdf, centroid_df


def prepare_landuse_for_viz(df: pd.DataFrame) -> pd.DataFrame:
    """为可视化准备用地 centroid 数据，添加 density、label 列。"""
    if df is None or len(df) == 0:
        return df
    out = df.copy()
    out["density"] = 1.0
    if "landuse_type" in out.columns:
        out["label"] = out["landuse_type"].map(
            lambda x: LANDUSE_LABELS.get(str(x).lower(), str(x))
        )
    return out


def get_landuse_stats(gdf: "gpd.GeoDataFrame | None", centroid_df: pd.DataFrame | None) -> dict:
    """用地数据基本统计。"""
    stats = {"polygon_count": 0, "centroid_count": 0, "types": []}
    if gdf is not None and len(gdf) > 0:
        stats["polygon_count"] = len(gdf)
        if "landuse" in gdf.columns:
            stats["types"] = gdf["landuse"].dropna().unique().tolist()[:15]
    if centroid_df is not None and len(centroid_df) > 0:
        stats["centroid_count"] = len(centroid_df)
        if "landuse_type" in centroid_df.columns and not stats["types"]:
            stats["types"] = centroid_df["landuse_type"].unique().tolist()[:15]
    return stats
