"""
人口栅格地图叠加
================
将人口数据渲染为热力图叠加到 OSM 底图。
"""

from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False


def create_population_map(
    data: np.ndarray,
    bounds: tuple[float, float, float, float],
    nodata: float | None,
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: int = 14,
    cmap_name: str = "YlOrRd",
    opacity: float = 0.55,
) -> "folium.Map | None":
    """
    创建人口分布地图（栅格叠加到 OSM）。

    Args:
        data: 2D 人口栅格
        bounds: (lon_min, lon_max, lat_min, lat_max)
        nodata: 无数据值
        map_center: 地图中心
        map_zoom: 缩放
        cmap_name: 色带（YlOrRd / Blues / RdPu 等）
        opacity: 叠加透明度

    Returns:
        folium.Map 或 None
    """
    if not HAS_FOLIUM:
        return None

    lon_min, lon_max, lat_min, lat_max = bounds
    arr = data.astype(float)
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)

    # 归一化到 [0, 1] 用于着色
    vmin, vmax = np.nanmin(arr), np.nanmax(arr)
    if vmax - vmin < 1e-10:
        norm = np.ones_like(arr) * 0.5
    else:
        norm = (arr - vmin) / (vmax - vmin)
    norm = np.nan_to_num(norm, nan=0)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
    ax.set_aspect("equal")
    ax.imshow(
        norm,
        extent=[lon_min, lon_max, lat_min, lat_max],
        origin="upper",
        cmap=cmap_name,
        alpha=0.85,
        vmin=0,
        vmax=1,
    )
    ax.axis("off")
    plt.tight_layout(pad=0)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, dpi=100)
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode()
    img_url = f"data:image/png;base64,{img_b64}"

    m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="OpenStreetMap")
    folium.raster_layers.ImageOverlay(
        image=img_url,
        bounds=[[lat_min, lon_min], [lat_max, lon_max]],
        opacity=opacity,
        interactive=False,
    ).add_to(m)

    return m


def add_population_overlay(
    folium_map: "folium.Map",
    data: np.ndarray,
    bounds: tuple[float, float, float, float],
    nodata: float | None,
    cmap_name: str = "YlOrRd",
    opacity: float = 0.5,
) -> None:
    """
    将人口栅格叠加到已有的 folium 地图上（原地修改）。

    Args:
        folium_map: 已有的 folium.Map
        data, bounds, nodata: 同 create_population_map
        cmap_name: 色带
        opacity: 透明度
    """
    if not HAS_FOLIUM:
        return

    lon_min, lon_max, lat_min, lat_max = bounds
    arr = data.astype(float)
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)
    vmin, vmax = np.nanmin(arr), np.nanmax(arr)
    if vmax - vmin < 1e-10:
        norm = np.ones_like(arr) * 0.5
    else:
        norm = (arr - vmin) / (vmax - vmin)
    norm = np.nan_to_num(norm, nan=0)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
    ax.set_aspect("equal")
    ax.imshow(
        norm,
        extent=[lon_min, lon_max, lat_min, lat_max],
        origin="upper",
        cmap=cmap_name,
        alpha=0.9,
        vmin=0,
        vmax=1,
    )
    ax.axis("off")
    plt.tight_layout(pad=0)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, dpi=100)
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode()
    img_url = f"data:image/png;base64,{img_b64}"

    folium.raster_layers.ImageOverlay(
        image=img_url,
        bounds=[[lat_min, lon_min], [lat_max, lon_max]],
        opacity=opacity,
        interactive=False,
    ).add_to(folium_map)
