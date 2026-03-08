"""
用地多边形地图叠加
==================
将 OSM 用地多边形以 GeoJson 形式叠加到 folium 地图。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import geopandas as gpd

try:
    import folium
    from folium.plugins import MarkerCluster
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

XUJIAHUI_BOUNDS = (121.37, 121.48, 31.12, 31.23)

# 用地类型 -> 颜色
LANDUSE_COLORS = {
    "residential": "#8B4513",
    "commercial": "#FF6347",
    "retail": "#FF4500",
    "industrial": "#696969",
    "park": "#228B22",
    "grass": "#90EE90",
    "meadow": "#98FB98",
    "forest": "#006400",
    "water": "#4169E1",
    "school": "#9370DB",
    "university": "#4B0082",
    "leisure": "#32CD32",
    "garden": "#3CB371",
    "playground": "#00FA9A",
    "sports_centre": "#00CED1",
    "pitch": "#20B2AA",
    "recreation_ground": "#2E8B57",
    "office": "#6495ED",
    "pitch": "#20B2AA",
    "military": "#2F4F4F",
    "brownfield": "#8B7355",
    "greenfield": "#9ACD32",
    "other": "#808080",
}


def _get_landuse_type(row) -> str:
    """从 OSM 属性提取用地类型。"""
    for col in ["landuse", "leisure", "natural"]:
        if col in row.index and row.get(col) is not None:
            val = str(row[col]).strip()
            if val and val.lower() not in ("yes", "no"):
                return val
    return "other"


def _get_color(landuse_type: str) -> str:
    """根据用地类型返回颜色。"""
    key = str(landuse_type).lower()
    return LANDUSE_COLORS.get(key, "#808080")


def create_landuse_map(
    gdf: "gpd.GeoDataFrame",
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: int = 14,
) -> "folium.Map | None":
    """
    创建用地多边形地图（GeoJson 叠加到 OSM 底图）。
    按 landuse/leisure/natural 类型着色。
    """
    if not HAS_FOLIUM:
        return None

    if gdf is None or len(gdf) == 0:
        return None

    # 确保有 landuse_type 列
    if "landuse_type" not in gdf.columns:
        gdf = gdf.copy()
        gdf["landuse_type"] = gdf.apply(_get_landuse_type, axis=1)

    m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="OpenStreetMap")

    # 按类型分组，每个类型一个 GeoJson 层
    for landuse_type, group in gdf.groupby("landuse_type"):
        color = _get_color(landuse_type)
        features = []
        for _, row in group.iterrows():
            if row.geometry is not None and not row.geometry.is_empty:
                features.append({
                    "type": "Feature",
                    "geometry": row.geometry.__geo_interface__,
                    "properties": {"landuse_type": landuse_type},
                })
        if not features:
            continue
        geojson_data = {"type": "FeatureCollection", "features": features}
        folium.GeoJson(
            geojson_data,
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": c,
                "weight": 2,
                "fillOpacity": 0.4,
            },
            tooltip=folium.Tooltip(f"用地类型: {landuse_type}"),
            name=landuse_type,
        ).add_to(m)

    folium.LayerControl().add_to(m)
    return m
