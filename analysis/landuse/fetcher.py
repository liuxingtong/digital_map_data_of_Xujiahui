"""
OSM 用地数据拉取
================
使用 osmnx.features_from_bbox 拉取徐家汇 landuse/leisure/natural 多边形，
保存 GeoJSON 和 centroid CSV。OSM 数据为 WGS84，无需纠偏。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# 徐家汇边界 (lon_min, lon_max, lat_min, lat_max)
XUJIAHUI_BOUNDS = (121.37, 121.48, 31.12, 31.23)


def fetch_landuse(
    bbox: tuple[float, float, float, float] | None = None,
    tags: dict | None = None,
) -> "geopandas.GeoDataFrame":
    """
    从 OSM 拉取用地多边形。

    Args:
        bbox: (lon_min, lon_max, lat_min, lat_max)，默认徐家汇
        tags: OSM 标签，默认 landuse + leisure + natural

    Returns:
        GeoDataFrame，含 geometry 及 landuse/leisure/natural 等属性
    """
    try:
        import osmnx as ox
        import geopandas as gpd
    except ImportError as e:
        raise ImportError("请安装 osmnx 和 geopandas: pip install osmnx geopandas") from e

    bbox = bbox or XUJIAHUI_BOUNDS
    lon_min, lon_max, lat_min, lat_max = bbox
    # osmnx features_from_bbox: (left, bottom, right, top)
    bbox_tuple = (lon_min, lat_min, lon_max, lat_max)

    if tags is None:
        tags = {
            "landuse": True,
            "leisure": True,
            "natural": True,
        }

    gdf = ox.features_from_bbox(bbox=bbox_tuple, tags=tags)
    if gdf is None or len(gdf) == 0:
        return gpd.GeoDataFrame()

    # 仅保留多边形，重置索引以保留 element_type/osmid
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    gdf = gdf.reset_index()
    return gdf


def _get_landuse_type(row) -> str:
    """从 OSM 属性提取用地类型标签。"""
    for col in ["landuse", "leisure", "natural"]:
        if col in row.index and pd.notna(row.get(col)):
            val = str(row[col]).strip()
            if val and val.lower() not in ("yes", "no"):
                return val
    return "other"


def save_landuse(
    gdf: "geopandas.GeoDataFrame",
    out_dir: str | Path,
    geojson_name: str = "landuse_xujiahui.geojson",
    csv_name: str = "landuse_centroid.csv",
) -> tuple[Path, Path]:
    """
    保存 GeoJSON 和 centroid CSV。

    Returns:
        (geojson_path, csv_path)
    """
    import geopandas as gpd

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    geojson_path = out_dir / geojson_name
    csv_path = out_dir / csv_name

    if gdf is None or len(gdf) == 0:
        import geopandas as gpd
        empty_gdf = gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:4326")
        empty_gdf.to_file(geojson_path, driver="GeoJSON")
        pd.DataFrame(columns=["lon", "lat", "landuse_type", "osm_id"]).to_csv(csv_path, index=False)
        return geojson_path, csv_path

    gdf.to_file(geojson_path, driver="GeoJSON")

    # 提取 centroid 和类型（WGS84 下 centroid 为近似，徐家汇范围可接受）
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        centroids = gdf.geometry.centroid
    rows = []
    for i in range(len(gdf)):
        row = gdf.iloc[i]
        geom = centroids.iloc[i]
        lon = float(geom.x)
        lat = float(geom.y)
        landuse_type = _get_landuse_type(row)
        et = row.get("element_type", "way")
        oid = row.get("osmid", i)
        if isinstance(oid, (list, tuple)):
            oid = "_".join(str(x) for x in oid)
        osm_id = f"{et}_{oid}"
        rows.append({"lon": lon, "lat": lat, "landuse_type": landuse_type, "osm_id": osm_id})

    centroid_df = pd.DataFrame(rows)
    centroid_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return geojson_path, csv_path


def run_fetch(
    out_dir: str | Path | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[Path, Path]:
    """
    拉取并保存用地数据。

    Returns:
        (geojson_path, csv_path)
    """
    ROOT = Path(__file__).resolve().parents[2]
    out_dir = out_dir or (ROOT / "landuse_data")
    out_dir = Path(out_dir)

    gdf = fetch_landuse(bbox=bbox)
    return save_landuse(gdf, out_dir)


if __name__ == "__main__":
    geojson_p, csv_p = run_fetch()
    print(f"GeoJSON: {geojson_p}")
    print(f"Centroid CSV: {csv_p}")
