"""
POI 地图叠加
============
将 POI 点数据以标记形式叠加到 OSM 底图。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

try:
    import folium
    from folium.plugins import MarkerCluster
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False


# 徐家汇边界（与人口裁剪一致）
XUJIAHUI_BOUNDS = (121.37, 121.48, 31.12, 31.23)


def create_poi_map(
    df: pd.DataFrame,
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: int = 14,
    cluster: bool = True,
    color_by_group: bool = False,
) -> "folium.Map | None":
    """
    创建 POI 分布地图（标记叠加到 OSM）。

    Args:
        df: 含 lon/lng, lat, name 的 DataFrame，可选 group, address, rating
        map_center: 地图中心 [lat, lon]
        map_zoom: 缩放级别
        cluster: 是否使用 MarkerCluster 聚合
        color_by_group: 是否按 group 着色（需有 group 列）

    Returns:
        folium.Map 或 None
    """
    if not HAS_FOLIUM:
        return None

    if df is None or len(df) == 0:
        return None

    lon_col = "lon" if "lon" in df.columns else "lng"
    if lon_col not in df.columns:
        return None

    m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="OpenStreetMap")

    # 按 group 分配颜色（若有）
    group_colors = {}
    if color_by_group and "group" in df.columns:
        groups = df["group"].dropna().unique()
        colors = ["red", "blue", "green", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen"]
        for i, g in enumerate(groups):
            group_colors[str(g).split("|")[0]] = colors[i % len(colors)]

    def _make_popup(row) -> str:
        parts = [f"<b>{row.get('name', '')}</b>"]
        if "group" in row and pd.notna(row.get("group")):
            parts.append(f"<br>类型: {row['group']}")
        if "address" in row and pd.notna(row.get("address")):
            parts.append(f"<br>地址: {row['address']}")
        if "rating" in row and pd.notna(row.get("rating")):
            parts.append(f"<br>评分: {row['rating']}")
        return "".join(parts)

    if cluster:
        marker_cluster = MarkerCluster(name="POI").add_to(m)
        for _, row in df.iterrows():
            lat, lon = row["lat"], row[lon_col]
            color = None
            if color_by_group and "group" in row and pd.notna(row.get("group")):
                g0 = str(row["group"]).split("|")[0]
                color = group_colors.get(g0, "blue")
            folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                popup=folium.Popup(_make_popup(row), max_width=280),
                color=color or "blue",
                fill=True,
                fillOpacity=0.7,
            ).add_to(marker_cluster)
    else:
        for _, row in df.iterrows():
            lat, lon = row["lat"], row[lon_col]
            color = "blue"
            if color_by_group and "group" in row and pd.notna(row.get("group")):
                g0 = str(row["group"]).split("|")[0]
                color = group_colors.get(g0, "blue")
            folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                popup=folium.Popup(_make_popup(row), max_width=280),
                color=color,
                fill=True,
                fillOpacity=0.7,
            ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


def add_poi_overlay(
    folium_map: "folium.Map",
    df: pd.DataFrame,
    cluster: bool = True,
    color_by_group: bool = False,
) -> None:
    """
    将 POI 标记叠加到已有的 folium 地图上（原地修改）。

    Args:
        folium_map: 已有的 folium.Map
        df: POI DataFrame
        cluster: 是否使用 MarkerCluster
        color_by_group: 是否按 group 着色
    """
    if not HAS_FOLIUM or df is None or len(df) == 0:
        return

    lon_col = "lon" if "lon" in df.columns else "lng"
    if lon_col not in df.columns:
        return

    group_colors = {}
    if color_by_group and "group" in df.columns:
        groups = df["group"].dropna().unique()
        colors = ["red", "blue", "green", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen"]
        for i, g in enumerate(groups):
            group_colors[str(g).split("|")[0]] = colors[i % len(colors)]

    def _make_popup(row) -> str:
        parts = [f"<b>{row.get('name', '')}</b>"]
        if "group" in row and pd.notna(row.get("group")):
            parts.append(f"<br>类型: {row['group']}")
        if "address" in row and pd.notna(row.get("address")):
            parts.append(f"<br>地址: {row['address']}")
        if "rating" in row and pd.notna(row.get("rating")):
            parts.append(f"<br>评分: {row['rating']}")
        return "".join(parts)

    if cluster:
        marker_cluster = MarkerCluster(name="POI").add_to(folium_map)
        target = marker_cluster
    else:
        target = folium_map

    for _, row in df.iterrows():
        lat, lon = row["lat"], row[lon_col]
        color = "blue"
        if color_by_group and "group" in row and pd.notna(row.get("group")):
            g0 = str(row["group"]).split("|")[0]
            color = group_colors.get(g0, "blue")
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            popup=folium.Popup(_make_popup(row), max_width=280),
            color=color,
            fill=True,
            fillOpacity=0.6,
        ).add_to(target)
