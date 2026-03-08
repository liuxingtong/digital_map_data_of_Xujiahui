"""
小区地图叠加
============
将小区点数据以标记形式叠加到 OSM 底图。
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

XUJIAHUI_BOUNDS = (121.37, 121.48, 31.12, 31.23)


def _make_house_popup(row: pd.Series) -> str:
    parts = [f"<b>{row.get('name', '')}</b>"]
    if "address" in row and pd.notna(row.get("address")) and str(row["address"]).strip():
        parts.append(f"<br>地址: {row['address']}")
    if "unit_price" in row and pd.notna(row.get("unit_price")):
        parts.append(f"<br>均价: {row['unit_price']:,.0f} 元/㎡")
    if "plot_ratio" in row and pd.notna(row.get("plot_ratio")):
        parts.append(f"<br>容积率: {row['plot_ratio']}")
    if "greening_rate" in row and pd.notna(row.get("greening_rate")):
        parts.append(f"<br>绿化率: {row['greening_rate']*100:.0f}%")
    if "completion_year" in row and pd.notna(row.get("completion_year")):
        parts.append(f"<br>竣工: {int(row['completion_year'])}年")
    return "".join(parts)


def create_house_map(
    df: pd.DataFrame,
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: int = 14,
    cluster: bool = True,
    color_by: str | None = None,
) -> "folium.Map | None":
    """
    创建小区分布地图（标记叠加到 OSM）。

    Args:
        df: 含 lon, lat, name 的 DataFrame，可选 address, unit_price, plot_ratio, greening_rate, completion_year
        map_center: 地图中心 [lat, lon]
        map_zoom: 缩放级别
        cluster: 是否使用 MarkerCluster 聚合
        color_by: 按某指标着色，如 "unit_price", "plot_ratio", "greening_rate"

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

    if color_by and color_by in df.columns:
        vals = pd.to_numeric(df[color_by], errors="coerce").fillna(0)
        vmin, vmax = vals.min(), vals.max()
        if vmax - vmin < 1e-10:
            vmax = vmin + 1
        norm = (vals - vmin) / (vmax - vmin)

    def _get_color(idx: int) -> str:
        if not color_by or color_by not in df.columns:
            return "blue"
        nv = float(norm.iloc[idx])
        # 绿->黄->红：低到高 (RdYlGn 风格)
        if nv < 0.5:
            t = nv * 2
            r, g, b = int(255 * t), 255, int(255 * (1 - t))
        else:
            t = (nv - 0.5) * 2
            r, g, b = 255, int(255 * (1 - t)), 0
        return f"#{r:02x}{g:02x}{b:02x}"

    if cluster:
        marker_cluster = MarkerCluster(name="小区").add_to(m)
        target = marker_cluster
    else:
        target = m

    for idx, row in df.iterrows():
        lat, lon = row["lat"], row[lon_col]
        color = _get_color(idx)
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            popup=folium.Popup(_make_house_popup(row), max_width=320),
            color=color,
            fill=True,
            fillOpacity=0.7,
        ).add_to(target)

    folium.LayerControl().add_to(m)
    return m


def add_house_overlay(
    folium_map: "folium.Map",
    df: pd.DataFrame,
    cluster: bool = True,
) -> None:
    """将小区标记叠加到已有的 folium 地图上（原地修改）。"""
    if not HAS_FOLIUM or df is None or len(df) == 0:
        return

    lon_col = "lon" if "lon" in df.columns else "lng"
    if lon_col not in df.columns:
        return

    if cluster:
        marker_cluster = MarkerCluster(name="小区").add_to(folium_map)
        target = marker_cluster
    else:
        target = folium_map

    for _, row in df.iterrows():
        lat, lon = row["lat"], row[lon_col]
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            popup=folium.Popup(_make_house_popup(row), max_width=320),
            color="blue",
            fill=True,
            fillOpacity=0.6,
        ).add_to(target)
