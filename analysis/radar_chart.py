"""
雷达图（蜘蛛网图）模块
======================
展示多指标综合对比，适用于区域聚合或单点指标概览。

输入: DataFrame 含多指标列
输出: Plotly Figure（可用 st.plotly_chart 渲染）
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


def _normalize_series(s: pd.Series) -> pd.Series:
    """Min-max 归一化到 [0, 1]"""
    mn, mx = s.min(), s.max()
    if mx - mn < 1e-10:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


def create_radar_chart(
    df: pd.DataFrame,
    indicators: list[str],
    title: str = "指标雷达图",
    aggregation: str = "mean",
    normalize: bool = True,
    row_index: int | None = None,
) -> "go.Figure | None":
    """
    创建雷达图。

    Args:
        df: 含各指标列的 DataFrame
        indicators: 要展示的指标列名列表（建议 4–8 个）
        title: 图表标题
        aggregation: 聚合方式 ("mean" / "median" / "max" / "min")，单点时忽略
        normalize: 是否对聚合值做 [0,1] 归一化
        row_index: 若指定，则显示该行的单点数据；否则按 aggregation 聚合

    Returns:
        plotly Figure 或 None
    """
    if not HAS_PLOTLY:
        return None

    valid = [c for c in indicators if c in df.columns]
    if not valid:
        return None

    if row_index is not None and 0 <= row_index < len(df):
        values = df[valid].iloc[row_index]
    elif aggregation == "mean":
        values = df[valid].mean()
    elif aggregation == "median":
        values = df[valid].median()
    elif aggregation == "max":
        values = df[valid].max()
    elif aggregation == "min":
        values = df[valid].min()
    else:
        values = df[valid].mean()

    values = pd.Series(values).astype(float)
    if normalize:
        values = _normalize_series(values)

    theta = list(values.index)
    r = list(values.values)

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=r,
            theta=theta,
            fill="toself",
            name="聚合值",
            line=dict(color="rgb(31, 119, 180)", width=2),
            fillcolor="rgba(31, 119, 180, 0.3)",
        )
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1.05]),
            angularaxis=dict(tickfont=dict(size=10)),
        ),
        title=title,
        showlegend=False,
        height=450,
        margin=dict(l=80, r=80, t=60, b=40),
    )
    return fig
