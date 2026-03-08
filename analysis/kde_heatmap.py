"""
核密度估计（KDE）热力图模块
==========================
基于 scipy.stats.gaussian_kde，在 (lon, lat) 空间对选定指标做 KDE，
生成热力图并叠加到 OSM 底图。

输入: DataFrame 含 lon, lat 及用户选择的指标列
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


def _compute_kde_grid(
    df: pd.DataFrame,
    lon_col: str,
    lat_col: str,
    value_col: str,
    grid_resolution: int = 60,
    bandwidth: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, float, float, float]]:
    """
    在 (lon, lat) 空间对 value_col 做加权 KDE，返回网格值及边界。

    Returns:
        lons: 1D 经度网格
        lats: 1D 纬度网格
        Z: 2D KDE 值
        bounds: (lon_min, lon_max, lat_min, lat_max)
    """
    lon = df[lon_col].values.astype(float)
    lat = df[lat_col].values.astype(float)
    weights = df[value_col].values.astype(float)
    weights = np.maximum(weights, 1e-10)  # 避免零权

    data = np.vstack([lon, lat])
    kernel = gaussian_kde(data, weights=weights, bw_method=bandwidth)

    lon_min, lon_max = lon.min(), lon.max()
    lat_min, lat_max = lat.min(), lat.max()
    # 适当扩展边界
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


def create_kde_heatmap(
    df: pd.DataFrame,
    indicator: str,
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: int = 14,
    grid_resolution: int = 60,
    cmap_name: str = "RdYlGn",
    invert_colors: bool = False,
) -> "folium.Map | None":
    """
    创建 KDE 热力图并叠加到 OSM 底图。

    Args:
        df: 含 lon, lat 及 indicator 列的 DataFrame
        indicator: 用于 KDE 加权的指标列名
        map_center: 地图中心 [lat, lon]
        map_zoom: 缩放级别
        grid_resolution: 网格分辨率（越大越平滑但越慢）
        cmap_name: 色带名称 (RdYlGn / viridis 等)
        invert_colors: 是否反转色阶（低=绿）

    Returns:
        folium.Map 或 None（依赖缺失时）
    """
    if not HAS_DEPS:
        return None

    if indicator not in df.columns:
        return None

    lons, lats, Z, (lon_min, lon_max, lat_min, lat_max) = _compute_kde_grid(
        df, "lon", "lat", indicator, grid_resolution
    )

    # 归一化 Z 用于着色
    z_min, z_max = Z.min(), Z.max()
    if z_max - z_min < 1e-10:
        Z_norm = np.ones_like(Z) * 0.5
    else:
        Z_norm = (Z - z_min) / (z_max - z_min)
    if invert_colors:
        Z_norm = 1 - Z_norm

    # 用 matplotlib 生成热力图 PNG
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(8, 8), dpi=100)
    ax.set_aspect("equal")
    im = ax.imshow(
        Z_norm,
        extent=[lon_min, lon_max, lat_min, lat_max],
        origin="lower",
        cmap=cmap_name,
        alpha=0.6,
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
    bounds = [[lat_min, lon_min], [lat_max, lon_max]]
    folium.raster_layers.ImageOverlay(
        image=img_url,
        bounds=bounds,
        opacity=0.6,
        interactive=False,
    ).add_to(m)

    return m
