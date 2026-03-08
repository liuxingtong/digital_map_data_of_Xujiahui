"""
地图 + 雷达图联动仪表盘
======================
创建可点击的 Plotly 散点地图，配合雷达图展示单点指标。
与 Streamlit 的 st.plotly_chart(..., on_select="rerun") 配合使用。

输入: DataFrame 含 lon, lat 及多指标列
输出: Plotly Figure（scatter_mapbox）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    pass

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def create_clickable_map(
    df: pd.DataFrame,
    indicator: str,
    map_center: tuple[float, float] = (31.19, 121.44),
    map_zoom: float = 13,
    invert_colors: bool = False,
) -> "go.Figure | None":
    """
    创建可点击的 Plotly 散点地图。
    每个点的 customdata 存储行索引，供 selection 回调使用。

    Args:
        df: 含 lon, lat 及 indicator
        indicator: 用于着色的指标
        map_center: [lat, lon]
        map_zoom: 缩放
        invert_colors: 是否反转色阶

    Returns:
        plotly Figure 或 None
    """
    if not HAS_PLOTLY:
        return None

    vals = df[indicator].values.astype(float)
    vmin, vmax = vals.min(), vals.max()
    if vmax - vmin < 1e-10:
        vmax = vmin + 1
    norm = (vals - vmin) / (vmax - vmin)
    if invert_colors:
        norm = 1 - norm

    # 颜色：RdYlGn
    colors = []
    for v in norm:
        v = max(0, min(1, v))
        if v < 0.5:
            r, g = 255, int(255 * 2 * v)
        else:
            r, g = int(255 * 2 * (1 - v)), 255
        colors.append(f"rgb({r},{g},0)")

    # customdata: [row_index, indicator_value] 供 hover 与 selection 使用
    customdata = np.column_stack([np.arange(len(df)), df[indicator].values])

    fig = go.Figure()
    fig.add_trace(
        go.Scattermapbox(
            lat=df["lat"],
            lon=df["lon"],
            mode="markers",
            marker=dict(
                size=8,
                color=colors,
                opacity=0.7,
            ),
            customdata=customdata,
            hovertemplate=(
                f"<b>{indicator}</b>: %{{customdata[1]:.4f}}<br>"
                "经度: %{lon:.5f}<br>纬度: %{lat:.5f}<br>"
                "<extra></extra>"
            ),
            name="",
        )
    )

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=map_center[0], lon=map_center[1]),
            zoom=map_zoom,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=550,
        showlegend=False,
        clickmode="event+select",
        dragmode="zoom",
    )

    return fig
