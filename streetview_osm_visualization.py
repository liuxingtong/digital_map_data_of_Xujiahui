"""
Street View Image Segmentation Visualization on OSM
====================================================
徐家汇地区街景图像分割数据 → 复合指标计算 → OSM 底图可视化

用法:
    python streetview_osm_visualization.py

输出:
    - output/ 目录下的各指标 HTML 地图
    - output/indicators.csv 指标汇总表
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

# 延迟导入 folium，避免无 GUI 环境报错
try:
    import folium
    from folium.plugins import HeatMap, MarkerCluster
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

# ==================== 配置 ====================
# 默认使用 1.csv+2.csv 合并数据；可改为 "1.csv"、"2.csv" 或 "example.csv"
CSV_PATH = Path(__file__).parent / "streetview_images" / "merged.csv"
OUTPUT_DIR = Path(__file__).parent / "output"
MAP_CENTER = [31.19, 121.44]  # 徐家汇大致中心
MAP_ZOOM = 14
SAMPLE_SIZE = 3000  # 可视化采样点数，设为 None 则使用全部（24k 点可能较慢）


# ==================== PART 1: 数据加载与预处理 ====================

def load_data(csv_path: str | Path) -> pd.DataFrame:
    """加载 CSV，清理列名，移除无效行。坐标需为 WGS84（OSM 街景默认）。"""
    df = pd.read_csv(csv_path, low_memory=False)

    # 统一经度列名：lng -> lon
    if "lng" in df.columns and "lon" not in df.columns:
        df["lon"] = df["lng"]
    elif "lon" not in df.columns:
        raise ValueError("CSV 需含 lon 或 lng 列")

    # 移除可能存在的非数值列（如末尾的布尔列）
    for c in df.columns:
        if df[c].dtype == object and c not in ("image",):
            try:
                pd.to_numeric(df[c], errors="raise")
            except (ValueError, TypeError):
                df = df.drop(columns=[c])

    # 确保 lon, lat 为数值
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df = df.dropna(subset=["lon", "lat"])

    if len(df) < 100:
        print(
            f"  提示: 当前 CSV 仅 {len(df)} 条有效记录（可能含大量空行）。"
            " 可修改 CSV_PATH 为 '1.csv' 或 '2.csv' 以使用完整数据。"
        )

    return df


def define_category_groups() -> dict[str, list[str]]:
    """定义 7 大语义类别分组"""
    return {
        "nature": [
            "bird", "ground animal", "mountain", "sand", "sky", "snow",
            "terrain", "vegetation", "water",
        ],
        "built": [
            "curb", "fence", "guard rail", "barrier", "wall", "building",
            "tunnel", "bridge",
        ],
        "road": [
            "bike lane", "crosswalk-plain", "curb cut", "parking",
            "pedestrian area", "rail track", "road", "service lane", "sidewalk",
        ],
        "sign": [
            "lane marking - crosswalk", "lane marking - general",
            "traffic sign(back)", "traffic sign(front)", "traffic sign frame",
            "traffic light",
        ],
        "furniture": [
            "banner", "bench", "bike rack", "billboard", "catch basin",
            "CCTV camera", "fire hydrant", "junction box", "mailbox", "manhole",
            "phone booth", "phthole", "street light", "pole", "utility pole",
            "trash can",
        ],
        "people": ["person", "bicyclist", "motorcyclist", "other rider"],
        "vehicle": [
            "bicycle", "boat", "bus", "car", "caravan", "motorcycle",
            "on rails", "other vehicle", "trailer", "truck", "wheeled slow",
        ],
    }


def _safe_sum(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """安全地对列求和，缺失列视为 0"""
    out = pd.Series(0.0, index=df.index)
    for c in cols:
        if c in df.columns:
            out = out + df[c].fillna(0)
    return out


def compute_group_ratios(
    df: pd.DataFrame, groups: dict[str, list[str]]
) -> pd.DataFrame:
    """按大类聚合，计算各大类的像素占比"""
    out = pd.DataFrame(index=df.index)
    for name, cols in groups.items():
        out[name] = _safe_sum(df, cols)
    return out


def _normalize(s: pd.Series) -> pd.Series:
    """Min-max 归一化到 [0, 1]"""
    mn, mx = s.min(), s.max()
    if mx - mn < 1e-10:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


# ==================== PART 2: 基础指标计算 ====================

def calc_green_view_index(df: pd.DataFrame) -> pd.Series:
    """绿视率 GVI = vegetation + terrain"""
    return _safe_sum(df, ["vegetation", "terrain"])


def calc_sky_view_factor(df: pd.DataFrame) -> pd.Series:
    """天空可见度 SVF = sky"""
    return df["sky"].fillna(0) if "sky" in df.columns else pd.Series(0.0, index=df.index)


def calc_enclosure(df: pd.DataFrame) -> pd.Series:
    """围合度 = building + wall + fence + barrier"""
    return _safe_sum(df, ["building", "wall", "fence", "barrier"])


def calc_blue_view_index(df: pd.DataFrame) -> pd.Series:
    """蓝视率 BVI = water"""
    return df["water"].fillna(0) if "water" in df.columns else pd.Series(0.0, index=df.index)


# ==================== PART 3: 步行舒适度指标 ====================

def calc_pedestrian_infrastructure(df: pd.DataFrame) -> pd.Series:
    """步行基础设施"""
    return _safe_sum(df, [
        "sidewalk", "crosswalk-plain", "curb cut", "pedestrian area",
        "lane marking - crosswalk",
    ])


def calc_motor_pressure(df: pd.DataFrame) -> pd.Series:
    """机动车压力"""
    return _safe_sum(df, ["car", "bus", "truck", "motorcycle", "road"])


def calc_pedestrian_safety(df: pd.DataFrame) -> pd.Series:
    """步行安全感 = ped_infra + lights - motor_pressure，归一化"""
    ped = calc_pedestrian_infrastructure(df)
    motor = calc_motor_pressure(df)
    lights = _safe_sum(df, ["street light", "traffic light"])
    raw = ped + lights - motor
    return _normalize(raw)


def calc_shade_comfort(df: pd.DataFrame) -> pd.Series:
    """遮蔽舒适度 = vegetation + building + bridge + tunnel - sky，归一化"""
    shade = _safe_sum(df, ["vegetation", "building", "bridge", "tunnel"])
    sky = calc_sky_view_factor(df)
    raw = shade - sky
    return _normalize(raw)


# ==================== PART 4: 街道界面多样性 ====================

def calc_shannon_diversity(
    df: pd.DataFrame, groups: dict[str, list[str]]
) -> pd.Series:
    """Shannon H = -Σ(pᵢ·ln(pᵢ))"""
    grp = compute_group_ratios(df, groups)
    # 归一化使每行和为 1
    row_sum = grp.sum(axis=1).replace(0, 1)
    p = grp.div(row_sum, axis=0)
    p = p.replace(0, np.nan)
    h = -(p * np.log(p)).sum(axis=1)
    return h.fillna(0)


def calc_simpson_diversity(
    df: pd.DataFrame, groups: dict[str, list[str]]
) -> pd.Series:
    """Simpson D = 1 - Σ(pᵢ²)"""
    grp = compute_group_ratios(df, groups)
    row_sum = grp.sum(axis=1).replace(0, 1)
    p = grp.div(row_sum, axis=0)
    d = 1 - (p ** 2).sum(axis=1)
    return d


def calc_visual_complexity(
    df: pd.DataFrame, groups: dict[str, list[str]]
) -> pd.Series:
    """视觉复杂度 = 非零类别数 × Shannon H，归一化"""
    seg_cols = [
        c for c in df.columns
        if c not in ("image", "lon", "lat") and pd.api.types.is_numeric_dtype(df[c])
    ]
    if not seg_cols:
        return pd.Series(0.0, index=df.index)
    nonzero_count = (df[seg_cols] > 1e-6).sum(axis=1)
    shannon = calc_shannon_diversity(df, groups)
    raw = nonzero_count * shannon
    return _normalize(raw)


# ==================== PART 5: ART 认知恢复指标 ====================

def calc_fascination(df: pd.DataFrame) -> pd.Series:
    """魅力 = vegetation + water + terrain + 0.5 * sky"""
    v = _safe_sum(df, ["vegetation", "water", "terrain"])
    s = calc_sky_view_factor(df) * 0.5
    return v + s


def calc_being_away(df: pd.DataFrame) -> pd.Series:
    """远离 = 1 - (car + bus + truck + road + billboard + CCTV camera)"""
    cols = ["car", "bus", "truck", "road", "billboard"]
    if "CCTV camera" in df.columns:
        cols.append("CCTV camera")
    pressure = _safe_sum(df, cols)
    away = 1 - pressure
    return away.clip(0, 1)


def calc_scene_coherence(
    df: pd.DataFrame, groups: dict[str, list[str]]
) -> pd.Series:
    """延展：基于 Shannon H 的倒 U 型评分，中等多样性最优"""
    h = calc_shannon_diversity(df, groups)
    # 假设最优 H 在 1.5 附近，用正态型函数
    opt_h = 1.5
    sigma = 0.8
    coherence = np.exp(-((h - opt_h) ** 2) / (2 * sigma ** 2))
    return pd.Series(coherence, index=df.index)


def calc_ped_friendly(df: pd.DataFrame) -> pd.Series:
    """兼容 = sidewalk + bench + pedestrian area + street light - barrier - fence"""
    pos = _safe_sum(df, ["sidewalk", "bench", "pedestrian area", "street light"])
    neg = _safe_sum(df, ["barrier", "fence"])
    raw = pos - neg
    return _normalize(raw)


def calc_art_composite(
    df: pd.DataFrame,
    groups: dict[str, list[str]],
    weights: tuple[float, ...] = (0.3, 0.25, 0.2, 0.25),
) -> pd.Series:
    """ART 综合恢复潜力"""
    f = _normalize(calc_fascination(df))
    a = calc_being_away(df)
    c = calc_scene_coherence(df, groups)
    p = calc_ped_friendly(df)
    w1, w2, w3, w4 = weights
    return w1 * f + w2 * a + w3 * c + w4 * p


# ==================== PART 6: 所有指标汇总 ====================

def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有基础和复合指标"""
    groups = define_category_groups()
    out = df[["lon", "lat", "image"]].copy()

    # 基础
    out["GVI"] = calc_green_view_index(df)
    out["SVF"] = calc_sky_view_factor(df)
    out["Enclosure"] = calc_enclosure(df)
    out["BVI"] = calc_blue_view_index(df)

    # 步行舒适度
    out["Ped_Infra"] = calc_pedestrian_infrastructure(df)
    out["Motor_Pressure"] = calc_motor_pressure(df)
    out["Ped_Safety"] = calc_pedestrian_safety(df)
    out["Shade_Comfort"] = calc_shade_comfort(df)

    # 多样性
    out["Shannon_H"] = calc_shannon_diversity(df, groups)
    out["Simpson_D"] = calc_simpson_diversity(df, groups)
    out["Complexity"] = calc_visual_complexity(df, groups)

    # ART
    out["Fascination"] = calc_fascination(df)
    out["Being_Away"] = calc_being_away(df)
    out["Coherence"] = calc_scene_coherence(df, groups)
    out["Ped_Friendly"] = calc_ped_friendly(df)
    out["ART_Score"] = calc_art_composite(df, groups)

    return out


# ==================== PART 7: OSM 可视化 ====================

def _get_cmap_colors(v: float, cmap: str = "RdYlGn") -> str:
    """将 [0,1] 值映射为颜色。RdYlGn: 低=红, 高=绿"""
    v = max(0, min(1, float(v)))
    if cmap == "RdYlGn":
        if v < 0.5:
            r = 255
            g = int(255 * 2 * v)
        else:
            r = int(255 * 2 * (1 - v))
            g = 255
        b = 0
    else:
        r = int(255 * (1 - v))
        g = int(255 * v)
        b = 128
    return f"#{r:02x}{g:02x}{b:02x}"


def create_point_map(
    df: pd.DataFrame,
    indicator: str,
    colormap: str = "RdYlGn",
    title: str | None = None,
    invert: bool = False,
) -> "folium.Map | None":
    """单指标散点图：在 OSM 底图上按颜色渲染各采样点。
    invert=True 时：低值显示为绿色（适用于 Motor_Pressure 等越低越好的指标）
    """
    if not HAS_FOLIUM:
        print("folium 未安装，跳过地图生成。请运行: pip install folium")
        return None

    m = folium.Map(location=MAP_CENTER, zoom_start=MAP_ZOOM, tiles="OpenStreetMap")
    vals = df[indicator]
    vmin, vmax = vals.min(), vals.max()
    if vmax - vmin < 1e-10:
        vmax = vmin + 1
    norm_vals = (vals - vmin) / (vmax - vmin)
    if invert:
        norm_vals = 1 - norm_vals

    mc = MarkerCluster()
    for _, row in df.iterrows():
        nv = norm_vals.loc[row.name]
        color = _get_cmap_colors(nv, colormap)
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=f"{indicator}: {row[indicator]:.4f}",
        ).add_to(mc)
    mc.add_to(m)

    t = title or f"{indicator} (徐家汇街景)"
    folium.LayerControl().add_to(m)
    m.get_root().html.add_child(
        folium.Element(f"<h3 style='text-align:center'>{t}</h3>")
    )
    return m


def create_heatmap(
    df: pd.DataFrame, indicator: str, title: str | None = None
) -> "folium.Map | None":
    """单指标热力图"""
    if not HAS_FOLIUM:
        return None

    m = folium.Map(location=MAP_CENTER, zoom_start=MAP_ZOOM, tiles="OpenStreetMap")
    data = df[["lat", "lon", indicator]].values.tolist()
    HeatMap(data, min_opacity=0.3, radius=12, blur=15).add_to(m)
    t = title or f"{indicator} 热力图"
    m.get_root().html.add_child(folium.Element(f"<h3 style='text-align:center'>{t}</h3>"))
    return m


def create_bivariate_map(
    df: pd.DataFrame, ind1: str, ind2: str
) -> "folium.Map | None":
    """双变量地图：交叉分类，颜色表示组合类型"""
    if not HAS_FOLIUM:
        return None

    m = folium.Map(location=MAP_CENTER, zoom_start=MAP_ZOOM, tiles="OpenStreetMap")
    v1 = _normalize(df[ind1])
    v2 = _normalize(df[ind2])
    # 高 ind1 + 低 ind2 = 好；高 ind1 + 高 ind2 = 中等...
    combo = v1 - v2  # 正：ind1 高 ind2 低；负：反
    combo_norm = _normalize(combo)

    mc = MarkerCluster()
    for _, row in df.iterrows():
        nv = combo_norm.loc[row.name]
        color = _get_cmap_colors(nv)
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=f"{ind1}: {row[ind1]:.4f}<br>{ind2}: {row[ind2]:.4f}",
        ).add_to(mc)
    mc.add_to(m)
    m.get_root().html.add_child(
        folium.Element(
            f"<h3 style='text-align:center'>{ind1} vs {ind2} (绿=高{ind1}低{ind2})</h3>"
        )
    )
    return m


# ==================== PART 8: 主流程 ====================

def main() -> None:
    print("加载数据...")
    df = load_data(CSV_PATH)
    print(f"  共 {len(df)} 条记录")

    print("计算指标...")
    result = compute_all_indicators(df)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUTPUT_DIR / "indicators.csv"
    result.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"  指标已保存至 {out_csv}")

    if SAMPLE_SIZE and len(result) > SAMPLE_SIZE:
        sample = result.sample(n=SAMPLE_SIZE, random_state=42)
        print(f"  可视化采样 {SAMPLE_SIZE} 点")
    else:
        sample = result

    if not HAS_FOLIUM:
        print("请安装 folium: pip install folium")
        return

    print("生成地图...")

    # 基础指标
    for ind in ["GVI", "SVF", "Enclosure", "BVI"]:
        m = create_point_map(sample, ind)
        if m:
            path = OUTPUT_DIR / f"map_{ind}.html"
            m.save(str(path))
            print(f"  {path}")

    # 步行舒适度
    for ind in ["Ped_Infra", "Motor_Pressure", "Ped_Safety", "Shade_Comfort"]:
        m = create_point_map(sample, ind)
        if m:
            path = OUTPUT_DIR / f"map_{ind}.html"
            m.save(str(path))
            print(f"  {path}")

    # 多样性（Motor_Pressure 用反向色：低=绿更好）
    for ind in ["Shannon_H", "Simpson_D", "Complexity"]:
        m = create_point_map(sample, ind)
        if m:
            path = OUTPUT_DIR / f"map_{ind}.html"
            m.save(str(path))
            print(f"  {path}")

    # Motor_Pressure 低更好，反转色阶：低=绿
    m = create_point_map(sample, "Motor_Pressure", invert=True)
    if m:
        path = OUTPUT_DIR / "map_Motor_Pressure_inv.html"
        m.save(str(path))
        print(f"  {path} (低压力=绿)")

    # ART
    for ind in ["Fascination", "Being_Away", "Coherence", "Ped_Friendly", "ART_Score"]:
        m = create_point_map(sample, ind)
        if m:
            path = OUTPUT_DIR / f"map_{ind}.html"
            m.save(str(path))
            print(f"  {path}")

    # 热力图示例
    for ind in ["GVI", "ART_Score"]:
        m = create_heatmap(sample, ind)
        if m:
            path = OUTPUT_DIR / f"heatmap_{ind}.html"
            m.save(str(path))
            print(f"  {path}")

    # 双变量
    m = create_bivariate_map(sample, "GVI", "Motor_Pressure")
    if m:
        path = OUTPUT_DIR / "map_bivariate_GVI_vs_MotorPressure.html"
        m.save(str(path))
        print(f"  {path}")

    print("完成。")


if __name__ == "__main__":
    main()
