"""
等值线图（Contour Map）模块
==========================
基于 KDE 网格或插值，在 (lon, lat) 空间绘制等值线，
叠加到 OSM 底图。

输入: DataFrame 含 lon, lat 及选定指标
输出: folium.Map 或 None
"""

from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    pass

try:
    import folium
    from scipy.stats import gaussian_kde
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


def _compute_contour_grid(
    df: pd.DataFrame,
    lon_col: str,
    lat_col: str,
    value_col: str,
    grid_resolution: int = 60,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, float, float, float]]:
    """
    在 (lon, lat) 空间对 value_col 做加权 KDE，得到等值线所需的网格。

    Returns:
        lons, lats, Z, (lon_min, lon_max, lat_min, lat_max)
    """
    lon = df[lon_col].values.astype(float)
    lat = df[lat_col].values.astype(float)
    weights = df[value_col].values.astype(float)
    weights = np.maximum(weights, 1e-10)

    data = np.vstack([lon, lat])
    kernel = gaussian_kde(data, weights=weights)

    lon_min, lon_max = lon.min(), lon.max()
    lat_min, lat_max = lat.min(), lat.max()
    lon_margin = max(0.001, (lon_max - lon_min) * 0.05)
    lat_margin = max(0.001, (lat_max - lat_min) * 0.05)
    lon_min -= lon_margin
    lon_max += lon_margin
    lat_min -= lat_margin
    lat_max += lat_margin

    lons = np.linspace(lon_min, lon_max, grid_resolution)
    lats = np.linspace(lat_min, lat_max, grid_resolution)
    X, Y = np.meshgrid(lons, lats)
    positions = np.vstack([X.ravel(), Y.ravel()])
    Z = kernel(positions).reshape(X.shape)
    Z = np.maximum(Z, 0)

    return lons, lats, Z, (lon_min, lon_max, lat_min, lat_max)


def create_contour_map(
    df: pd.DataFrame,
    indicator: str,
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: int = 14,
    grid_resolution: int = 60,
    n_contours: int = 10,
    cmap_name: str = "RdYlGn",
    invert_colors: bool = False,
) -> "folium.Map | None":
    """
    创建等值线图并叠加到 OSM 底图。

    Args:
        df: 含 lon, lat 及 indicator 的 DataFrame
        indicator: 指标列名
        map_center: 地图中心
        map_zoom: 缩放级别
        grid_resolution: 网格分辨率
        n_contours: 等值线数量
        cmap_name: 色带
        invert_colors: 是否反转色阶

    Returns:
        folium.Map 或 None
    """
    if not HAS_DEPS:
        return None

    if indicator not in df.columns:
        return None

    lons, lats, Z, (lon_min, lon_max, lat_min, lat_max) = _compute_contour_grid(
        df, "lon", "lat", indicator, grid_resolution
    )

    z_min, z_max = Z.min(), Z.max()
    if z_max - z_min < 1e-10:
        Z_norm = np.ones_like(Z) * 0.5
    else:
        Z_norm = (Z - z_min) / (z_max - z_min)
    if invert_colors:
        Z_norm = 1 - Z_norm

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
    ax.set_aspect("equal")
    levels = np.linspace(0, 1, n_contours + 1)
    cf = ax.contourf(
        lons,
        lats,
        Z_norm,
        levels=levels,
        cmap=cmap_name,
        alpha=0.6,
        vmin=0,
        vmax=1,
    )
    ax.contour(
        lons,
        lats,
        Z_norm,
        levels=levels,
        colors="k",
        linewidths=0.3,
        alpha=0.5,
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
    bounds = [[lat_min, lon_min], [lat_max, lon_max]]
    folium.raster_layers.ImageOverlay(
        image=img_url,
        bounds=bounds,
        opacity=0.6,
        interactive=False,
    ).add_to(m)

    return m
