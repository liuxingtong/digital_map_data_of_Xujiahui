"""
CLD 因果回路图可视化
====================
生成适老化空间系统 CLD 的 Plotly 网络图，展示正负循环、节点属性等。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# 节点：编号 -> (短名, 完整名, 类型)
NODE_INFO = {
    "N01": ("社交场所", "社交场所密度", "数据可算"),
    "N02": ("老年人聚集", "老年人聚集强度", "仿真内生"),
    "N03": ("街道活跃", "街道界面活跃度", "数据可算"),
    "N04": ("路网连通", "路网连通性", "数据可算"),
    "N05": ("步行可达", "步行可达性半径", "数据可算"),
    "N06": ("土地混合", "土地混合度", "数据可算"),
    "N07": ("绿化遮阴", "绿化遮阴覆盖率", "数据可算"),
    "N09": ("街道舒适", "街道舒适度", "数据可算"),
    "N10": ("车流量", "车流量代理", "数据可算"),
    "N11": ("噪声污染", "噪声与污染暴露", "数据可算"),
    "N13": ("步行意愿", "步行意愿", "仿真内生"),
    "N14": ("认知复杂度", "空间认知复杂度", "数据可算"),
    "N15": ("认知激活", "认知储备激活潜力", "数据可算"),
    "N16": ("探索意愿", "主动探索意愿", "仿真内生"),
    "N17": ("生理压力", "环境生理压力", "数据可算"),
    "N18": ("人机干预", "N_YP→代际接触的转换器", "设计变量"),
    "N19": ("行为数据", "行为数据密度", "仿真内生"),
    "N20": ("干预优化", "干预节点优化", "仿真内生"),
    # R6 代际激活链 · 画像节点
    "N_YP": ("年轻人在场", "潜在认知资源·适度陌生来源", "外生变量"),
    "N_IG": ("代际互动", "两群人同时空做同一事的时刻", "仿真内生"),
    "N_GC": ("隔代照料", "隔代照料强度", "数据可算"),
}

# 边：(起点, 终点, 极性, 所属回路, 回路类型)
# 回路类型: R=强化, B=平衡, R_bad=恶性强化
EDGES = [
    ("N01", "N02", "+", "R1", "R"),
    ("N02", "N03", "+", "R1", "R"),
    ("N03", "N01", "+", "R1", "R"),
    ("N04", "N05", "+", "R2", "R"),
    ("N05", "N02", "+", "R2", "R"),
    ("N06", "N05", "+", "R2", "R"),
    ("N07", "N09", "+", "R3", "R"),
    ("N09", "N02", "+", "R3", "R"),
    ("N10", "N11", "+", "R_bad", "R_bad"),
    ("N11", "N13", "-", "R_bad", "R_bad"),
    ("N13", "N10", "-", "R_bad", "R_bad"),
    ("N13", "N02", "+", "R_bad", "R_bad"),
    ("N14", "N15", "+", "R4", "R"),
    ("N15", "N16", "+", "R4", "R"),
    ("N16", "N14", "+", "R4", "R"),
    ("N18", "N02", "+", "R5", "R"),
    ("N02", "N19", "+", "R5", "R"),
    ("N19", "N20", "+", "R5", "R"),
    ("N20", "N18", "+", "R5", "R"),
    ("N02", "N09", "-", "B2", "B"),
    ("N14", "N17", "+", "B3", "B"),
    ("N17", "N15", "-", "B3", "B"),
    ("N18", "N19", "-", "B4", "B"),
    # R6 代际激活链：N_YP/N18 → N_IG → N15，向 R4 注入
    ("N_YP", "N_IG", "+", "R6", "R"),
    ("N_IG", "N15", "+", "R6", "R"),
    ("N18", "N_IG", "+", "R6", "R"),
    # E44：N_YP 向 N14 注入（适度陌生：新行为模式、不同空间使用、意外视觉刺激）
    ("N_YP", "N14", "+", "R6", "R"),
    # R_bad 外部输入：年轻人通勤强化车流
    ("N_YP", "N10", "+", "R_bad", "R_bad"),
    # B5 文化摩擦：年轻人在场降低老年人舒适感
    ("N_YP", "N09", "-", "B5", "B"),
    # N_YP 支撑街道活跃度
    ("N_YP", "N03", "+", "R6", "R"),
    # N_GC 隔代照料：聚集+、探索-、驱动干预
    ("N_GC", "N02", "+", "R6", "R"),
    ("N_GC", "N16", "-", "B6", "B"),
    ("N_GC", "N18", "+", "R6", "R"),
    # N18 转换器：向 R4 注入、削弱 R_bad/B3
    ("N18", "N14", "+", "R6", "R"),
    ("N18", "N17", "-", "cross", "B"),
    ("N18", "N10", "-", "cross", "B"),
]

# 跨层边（N18 转换器对 R_bad/B3 的干预）
LOOP_META = {
    "cross": ("跨层干预", "cross", "N18 削弱 R_bad/B3"),
    "R1": ("社交活力", "R", "正向强化"),
    "R2": ("步行可达", "R", "注入链"),
    "R3": ("环境舒适", "R", "注入链"),
    "R4": ("认知恢复", "R", "正向强化"),
    "R5": ("人机共生", "R", "正向强化"),
    "R6": ("代际激活", "R", "注入链"),
    "R_bad": ("交通诱导", "R_bad", "恶性强化"),
    "B2": ("拥挤调节", "B", "平衡回路"),
    "B3": ("认知超载", "B", "平衡回路"),
    "B4": ("干预疲劳", "B", "平衡回路"),
    "B5": ("文化摩擦", "B", "抑制链"),
    "B6": ("隔代锁定", "B", "抑制链"),
}

# 颜色：按回路类型
COLOR_R = "#22c55e"      # 绿 - 正向强化
COLOR_B = "#0ea5e9"      # 青 - 平衡
COLOR_R_BAD = "#dc2626"  # 红 - 恶性
COLOR_INJECT = "#84cc16" # 黄绿 - 注入链

LOOP_COLORS = {
    "cross": "#64748b",
    "R1": COLOR_R,
    "R2": COLOR_INJECT,
    "R3": COLOR_INJECT,
    "R4": "#3b82f6",     # 蓝
    "R5": "#8b5cf6",     # 紫
    "R6": "#fbbf24",     # 黄 - 代际激活
    "R_bad": COLOR_R_BAD,
    "B2": COLOR_B,
    "B3": COLOR_B,
    "B4": COLOR_B,
    "B5": COLOR_B,
    "B6": COLOR_B,
}

# 节点按类型着色
NODE_TYPE_COLORS = {
    "数据可算": "#e0f2fe",
    "仿真内生": "#fef3c7",
    "设计变量": "#ddd6fe",
    "外生变量": "#fed7aa",
}


def create_cld_figure() -> "plotly.graph_objects.Figure | None":
    """生成 CLD 因果回路图（Plotly），含正负循环、节点属性、箭头、极性标注。"""
    try:
        import plotly.graph_objects as go
        import numpy as np
    except ImportError:
        return None

    nodes = list(set(n for e in EDGES for n in (e[0], e[1])))
    node_to_idx = {n: i for i, n in enumerate(nodes)}

    # 布局
    pos = {
        "N02": (0, 0),
        "N01": (-1.6, 1.3),
        "N03": (-1.6, -1.3),
        "N14": (2.0, 1.3),
        "N15": (2.0, 0),
        "N16": (2.0, -1.3),
        "N18": (1.3, -1.7),
        "N19": (0.5, -2.0),
        "N20": (0.9, -2.0),
        "N10": (-2.0, -1.3),
        "N11": (-2.0, 0),
        "N13": (-2.0, 1.3),
        "N04": (-0.9, 1.9),
        "N05": (0, 1.6),
        "N06": (0.5, 1.9),
        "N07": (-0.6, 1.7),
        "N09": (0.2, 1.3),
        "N17": (1.4, 0.7),
        # R6 画像节点
        "N_YP": (-1.2, -1.8),
        "N_IG": (0.8, -0.8),
        "N_GC": (-0.4, 1.0),
    }
    for n in nodes:
        if n not in pos:
            pos[n] = (0, 0)

    x_nodes = [pos[n][0] for n in nodes]
    y_nodes = [pos[n][1] for n in nodes]
    def _node_info(n):
        info = NODE_INFO.get(n, (n, n, ""))
        return info[0], info[1], info[2]

    node_colors = [NODE_TYPE_COLORS.get(_node_info(n)[2], "#f1f5f9") for n in nodes]
    def _border(t):
        if t == "设计变量": return "#0ea5e9"
        if t == "外生变量": return "#ea580c"
        return "#64748b"
    node_border = [_border(_node_info(n)[2]) for n in nodes]
    hover_texts = [f"<b>{n}</b> {_node_info(n)[1]}<br>类型: {_node_info(n)[2]}" for n in nodes]

    # 节点
    node_trace = go.Scatter(
        x=x_nodes,
        y=y_nodes,
        mode="markers+text",
        marker=dict(
            size=36,
            color=node_colors,
            line=dict(width=2, color=node_border),
            symbol="square",
        ),
        text=[_node_info(n)[0] for n in nodes],
        textposition="middle center",
        textfont=dict(size=10, color="#1e293b"),
        hoverinfo="text",
        hovertext=hover_texts,
        name="节点",
    )

    # 边：带箭头、极性标注
    shapes = []
    annotations = []
    arrow_scale = 0.12  # 箭头缩短，避免重叠节点

    for u, v, polarity, loop, loop_type in EDGES:
        i, j = node_to_idx[u], node_to_idx[v]
        x0, y0 = x_nodes[i], y_nodes[i]
        x1, y1 = x_nodes[j], y_nodes[j]
        color = LOOP_COLORS.get(loop, "#94a3b8")
        dash = "solid" if polarity == "+" else "dot"
        lw = 2.5 if loop_type == "R_bad" else 2

        # 线段（缩短以留出箭头空间）
        dx, dy = x1 - x0, y1 - y0
        dist = (dx**2 + dy**2) ** 0.5 or 0.01
        shrink = 1 - arrow_scale
        x0s, y0s = x0 + dx * (1 - shrink) / 2, y0 + dy * (1 - shrink) / 2
        x1s, y1s = x1 - dx * (1 - shrink) / 2, y1 - dy * (1 - shrink) / 2

        shapes.append(dict(
            type="line",
            x0=x0s, y0=y0s, x1=x1s, y1=y1s,
            line=dict(color=color, width=lw, dash=dash),
        ))

        # 箭头（从 85% 到 100%）
        ax = x0 + dx * 0.85
        ay = y0 + dy * 0.85
        annotations.append(dict(
            ax=ax, ay=ay, x=x1, y=y1,
            axref="x", ayref="y", xref="x", yref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.2,
            arrowwidth=1.5,
            arrowcolor=color,
        ))

        # 极性标注
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        pol_text = "(+)" if polarity == "+" else "(-)"
        annotations.append(dict(
            x=mx, y=my, text=pol_text,
            showarrow=False,
            font=dict(size=10, color=color),
            xanchor="center", yanchor="middle",
        ))

    fig = go.Figure(data=[node_trace])
    fig.update_layout(
        title=dict(
            text="适老化空间 CLD · 徐家汇代际认知恢复",
            font=dict(size=18),
        ),
        showlegend=False,
        xaxis=dict(visible=False, range=[-2.6, 2.6]),
        yaxis=dict(visible=False, range=[-2.3, 2.3], scaleanchor="x"),
        plot_bgcolor="#f8fafc",
        paper_bgcolor="white",
        margin=dict(l=20, r=20, t=60, b=100),
        height=620,
        shapes=shapes,
        annotations=annotations,
    )

    # 图例区
    legend_items = [
        "<b>统一叙事</b> 两群人+一堵墙 → N18把墙变成门 → 年轻人流动=认知恢复能量",
        "",
        "<b>回路类型</b>",
        "🟢 <b>R</b> 正向强化 (R1/R4/R5)",
        "🟡 <b>R6</b> 代际激活·向R4注入 (N_YP经N18→N_IG→N15)",
        "🔴 <b>R_bad</b> 恶性强化 (交通诱导)",
        "🔵 <b>B</b> 平衡回路 (B2/B3/B4/B5/B6)",
        "⚫ <b>cross</b> N18削弱R_bad/B3",
        "",
        "<b>N18 转换器</b> 制造代际接触时刻；R5=优化触发效率",
        "<b>N_YP</b> 潜在认知资源；N_IG 需N18调节才能充分实现",
        "",
        "<b>边极性</b> (+) 正向  (-) 负向",
        "<b>节点类型</b> 浅蓝=数据可算 浅黄=仿真内生 浅紫=设计变量 浅橙=外生",
    ]
    fig.add_annotation(
        text="<br>".join(legend_items),
        xref="paper", yref="paper",
        x=0.5, y=0.02,
        xanchor="center", yanchor="top",
        showarrow=False,
        font=dict(size=10),
        align="center",
        bgcolor="rgba(248,250,252,0.9)",
        bordercolor="#e2e8f0",
        borderwidth=1,
        borderpad=8,
    )

    return fig
