"""
徐家汇空间规划一张图
==================
街景指标 · 人口 · POI · 房价 · 用地 · 路网，模块化低耦合设计。

启动: streamlit run streetview_dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streetview_osm_visualization import (
    load_data,
    compute_all_indicators,
    create_point_map,
    create_heatmap,
    create_bivariate_map,
    MAP_CENTER,
    MAP_ZOOM,
)
from analysis import (
    create_kde_heatmap,
    create_contour_map,
    create_radar_chart,
    create_clickable_map,
)
from analysis.population import (
    load_population_raster,
    create_population_map,
    add_population_overlay,
    get_population_stats,
    raster_to_dataframe,
    load_combined_population,
    POPULATION_FILES,
)
from analysis.poi import (
    load_poi_data,
    create_poi_map,
    add_poi_overlay,
    get_poi_stats,
    prepare_poi_for_viz,
    aggregate_poi_by_category_near,
    POI_FILES,
    XUJIAHUI_BOUNDS,
)
from analysis.road import (
    load_road_network,
    load_road_edges,
    compute_n04_connectivity,
    compute_intersection_density,
    compute_road_summary_stats,
    create_road_map,
    run_cld_pipeline,
    XUJIAHUI_BOUNDS as ROAD_BOUNDS,
)
from analysis.house import (
    load_house_data,
    create_house_map,
    add_house_overlay,
    get_house_stats,
    prepare_house_for_viz,
    HOUSE_FILES,
    XUJIAHUI_BOUNDS as HOUSE_BOUNDS,
)
from analysis.landuse import (
    load_landuse,
    create_landuse_map,
    prepare_landuse_for_viz,
    get_landuse_stats,
    compute_landuse_advanced_metrics,
    compute_landuse_grid_metrics,
    LANDUSE_LABELS,
    XUJIAHUI_BOUNDS as LANDUSE_BOUNDS,
)

# ==================== 配置 ====================
DATA_DIR = (ROOT / "streetview_images").resolve()
POPULATION_DIR = (ROOT / "population").resolve()
POI_DIR = (ROOT / "poi_data").resolve()
ROAD_DIR = (ROOT / "road").resolve()
HOUSE_DIR = (ROOT / "house_data").resolve()
LANDUSE_DIR = (ROOT / "landuse_data").resolve()
CACHE_DIR = (ROOT / "cache").resolve()
CLD_CACHE_PATH = CACHE_DIR / "cld_priority.pkl"


def _resolve_population_path(filename: str) -> Path:
    """解析人口文件路径，优先使用项目目录，不存在时尝试 cwd 下的 population"""
    p = POPULATION_DIR / filename
    if p.exists():
        return p
    fallback = Path.cwd() / "population" / filename
    if fallback.exists():
        return fallback.resolve()
    return p  # 返回原路径，由调用方处理不存在的情况


def _load_cld_cache() -> tuple | None:
    """从本地加载适老化改造优先级缓存，返回 (G, df_prio) 或 None。"""
    if not CLD_CACHE_PATH.exists():
        return None
    try:
        import pickle
        with open(CLD_CACHE_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _save_cld_cache(G, df_prio) -> None:
    """将适老化改造优先级结果保存到本地缓存。"""
    if G is None:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        import pickle
        with open(CLD_CACHE_PATH, "wb") as f:
            pickle.dump((G, df_prio), f)
    except Exception:
        pass


def _resolve_poi_path(filename: str) -> Path:
    """解析 POI 文件路径"""
    p = POI_DIR / filename
    if p.exists():
        return p
    fallback = Path.cwd() / "poi_data" / filename
    if fallback.exists():
        return fallback.resolve()
    return p


def _resolve_house_path(filename: str) -> Path:
    """解析房价文件路径"""
    p = HOUSE_DIR / filename
    if p.exists():
        return p
    fallback = Path.cwd() / "house_data" / filename
    if fallback.exists():
        return fallback.resolve()
    return p


def _resolve_landuse_path(filename: str) -> Path:
    """解析用地数据路径"""
    p = LANDUSE_DIR / filename
    if p.exists():
        return p
    fallback = Path.cwd() / "landuse_data" / filename
    if fallback.exists():
        return fallback.resolve()
    return p


CSV_OPTIONS = ["merged.csv", "1.csv", "2.csv", "example.csv"]
HOUSE_INDICATORS = {
    "unit_price": "小区均价(元/㎡)",
    "plot_ratio": "容积率",
    "greening_rate": "绿化率",
    "completion_year": "竣工年份",
    "density": "密度(点数)",
}
POP_FILE_OPTIONS = list(POPULATION_FILES.keys())

INDICATOR_GROUPS = {
    "基础环境": ["GVI", "SVF", "Enclosure", "BVI"],
    "步行舒适度": ["Ped_Infra", "Motor_Pressure", "Ped_Safety", "Shade_Comfort"],
    "街道多样性": ["Shannon_H", "Simpson_D", "Complexity"],
    "ART 认知恢复": ["Fascination", "Being_Away", "Coherence", "Ped_Friendly", "ART_Score"],
}
INVERT_INDICATORS = {"Motor_Pressure"}

# ==================== 自定义样式 ====================
st.markdown("""
<style>
    /* 主标题 */
    .main-title {
        font-size: 1.75rem;
        font-weight: 600;
        color: #1e3a5f;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    .main-subtitle {
        font-size: 0.9rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    /* 模块卡片 */
    .module-card {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .module-card-population {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 20%, #fef9c3 100%);
        border: 1px solid #fcd34d;
    }
    .module-card-poi {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 20%, #e0e7ff 100%);
        border: 1px solid #93c5fd;
    }
    .module-card-house {
        background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 20%, #fdf2f8 100%);
        border: 1px solid #f9a8d4;
    }
    .module-card-landuse {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 20%, #ecfdf5 100%);
        border: 1px solid #34d399;
    }
    /* 指标说明 */
    .indicator-caption {
        font-size: 0.85rem;
        color: #475569;
        padding: 0.5rem 0;
        border-left: 3px solid #3b82f6;
        padding-left: 0.75rem;
        margin: 0.5rem 0;
        background: #f8fafc;
        border-radius: 0 6px 6px 0;
    }
    /* 统计卡片 */
    .stat-card {
        background: white;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e293b;
    }
    .stat-label {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 0.25rem;
    }
    /* Tab 样式增强 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #f1f5f9;
        padding: 6px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: white !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    }
</style>
""", unsafe_allow_html=True)

# ==================== 缓存 ====================

@st.cache_data(ttl=600)
def cached_load_and_compute(csv_name: str):
    path = DATA_DIR / csv_name
    if not path.exists():
        return None, f"文件不存在: {path}"
    df = load_data(path)
    if len(df) == 0:
        return None, "无有效数据"
    result = compute_all_indicators(df)
    return result, None


@st.cache_data(ttl=3600)
def cached_load_population(tif_path: str | Path):
    path = Path(tif_path)
    if not path.exists():
        return None, None, None, None
    data, bounds, nodata = load_population_raster(path)
    if data is None:
        return None, None, None, None
    stats = get_population_stats(data, nodata)
    return data, bounds, nodata, stats


@st.cache_data(ttl=3600)
def cached_population_dataframe(tif_path: str | Path, subsample: int = 2):
    return raster_to_dataframe(tif_path, value_col="population", subsample=subsample)


@st.cache_data(ttl=3600)
def cached_combined_population(subsample: int = 2):
    return load_combined_population(POPULATION_DIR, subsample=subsample)


@st.cache_data(ttl=3600)
def cached_load_poi(csv_name: str, clip_bounds: bool = True):
    path = _resolve_poi_path(csv_name)
    bounds = XUJIAHUI_BOUNDS if clip_bounds else None
    return load_poi_data(path, bounds=bounds)


@st.cache_data(ttl=3600)
def cached_load_house(filename: str, clip_bounds: bool = True, convert_gcj02_to_wgs84: bool = False):
    path = _resolve_house_path(filename)
    bounds = HOUSE_BOUNDS if clip_bounds else None
    return load_house_data(path, bounds=bounds, convert_gcj02_to_wgs84=convert_gcj02_to_wgs84)


@st.cache_data(ttl=3600)
def cached_load_landuse():
    """加载用地数据（GeoJSON + centroid CSV）。"""
    return load_landuse(LANDUSE_DIR, format="auto")


@st.cache_data(ttl=3600)
def cached_landuse_grid_metrics(data_dir: Path):
    """加载用地并计算网格指标（Shannon、绿地率、混合用途）。"""
    gdf, _ = load_landuse(data_dir, format="geojson")
    return compute_landuse_grid_metrics(gdf)


@st.cache_data(ttl=3600)
def cached_load_road_network(with_coords: bool = True):
    """加载路网：优先 Excel，不存在则用 OSMnx 从 OpenStreetMap 下载。"""
    excel_path = ROAD_DIR / "Xuhui_Road_Network_Data_Fixed.xlsx"
    try:
        G, edges = load_road_network(excel_path, with_coordinates=with_coords, bbox=ROAD_BOUNDS)
        if G is not None and G.number_of_nodes() > 0:
            return G, edges
        return None, None
    except Exception:
        return None, None


# ==================== 页面配置 ====================

st.set_page_config(
    page_title="徐家汇空间规划一张图",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown('<p class="main-title">🗺️ 徐家汇空间规划一张图</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="main-subtitle">街景指标 · 人口分布 · POI · 房价小区 · 用地类型 · 路网 · 多源空间数据融合</p>',
    unsafe_allow_html=True,
)

# ==================== 模块选择 ====================
module = st.radio(
    "当前模块",
    ["📊 街景指标", "👥 人口分布", "📍 POI 分布", "🏠 房价小区", "🗺️ 用地类型", "🛣️ 路网", "🔧 适老化改造优先级", "📐 CLD 回路"],
    horizontal=True,
    key="module",
)

# ==================== 侧边栏：根据模块显示不同内容 ====================
with st.sidebar:
    st.markdown("---")
    if module == "📊 街景指标":
        st.header("📂 街景模块")
        csv_name = st.selectbox("数据文件", CSV_OPTIONS, index=0)
        compute_clicked = st.button("🔄 计算并可视化", type="primary", use_container_width=True)
        st.divider()
        st.subheader("选择指标")
        viz_type = st.radio(
            "可视化类型",
            [
                "单指标散点图",
                "单指标热力图",
                "双变量对比",
                "KDE 热力图",
                "等值线图",
                "点选雷达图分析区域",
            ],
            index=0,
        )
        all_indicators = [x for g in INDICATOR_GROUPS.values() for x in g]
        indicator = indicator2 = None
        if viz_type == "双变量对比":
            indicator = st.selectbox("指标 1", all_indicators, key="ind1")
            indicator2 = st.selectbox("指标 2", all_indicators, key="ind2")
        elif viz_type in ("KDE 热力图", "等值线图"):
            g = st.selectbox("指标分类", list(INDICATOR_GROUPS.keys()), key="kde_group")
            indicator = st.selectbox("指标", INDICATOR_GROUPS[g], key="kde_ind")
        elif viz_type == "点选雷达图分析区域":
            g = st.selectbox("地图着色指标分类", list(INDICATOR_GROUPS.keys()), key="pick_group")
            indicator = st.selectbox("地图着色指标", INDICATOR_GROUPS[g], key="pick_ind")
        else:
            g = st.selectbox("指标分类", list(INDICATOR_GROUPS.keys()))
            indicator = st.selectbox("指标", INDICATOR_GROUPS[g])
        st.divider()
        st.subheader("雷达图")
        radar_indicators = st.multiselect(
            "雷达图指标",
            all_indicators,
            default=["GVI", "SVF", "Ped_Safety", "ART_Score"],
            key="radar_inds",
        )
        st.divider()
        overlay_population = st.checkbox("叠加人口图层", value=False, key="overlay_pop")
        sample_size = st.slider("采样点数", 500, 10000, 3000, 500, key="sample")
    elif module == "👥 人口分布":
        st.header("👥 人口模块")
        pop_file_labels = [POPULATION_FILES[k] for k in POP_FILE_OPTIONS]
        pop_file_idx = st.selectbox(
            "人口数据文件",
            range(len(POP_FILE_OPTIONS)),
            format_func=lambda i: pop_file_labels[i],
            key="pop_file",
        )
        pop_viz_type = st.radio(
            "可视化类型",
            ["栅格热力图", "KDE 热力图", "等值线图", "点选雷达图分析区域"],
            index=0,
            key="pop_viz",
        )
        if pop_viz_type == "点选雷达图分析区域":
            st.caption("需加载多年龄段数据，点击地图更新雷达图")
        pop_subsample = st.slider("点数据采样", 1, 4, 2, 1, key="pop_subsample")
    elif module == "📍 POI 分布":
        st.header("📍 POI 模块")
        poi_file_options = list(POI_FILES.keys())
        poi_file_labels = [POI_FILES[k] for k in poi_file_options]
        poi_file_idx = st.selectbox(
            "POI 数据文件",
            range(len(poi_file_options)),
            format_func=lambda i: poi_file_labels[i],
            key="poi_file",
        )
        poi_viz_type = st.radio(
            "可视化类型",
            ["标记点图", "单指标散点图", "单指标热力图", "KDE 热力图", "等值线图", "点选雷达图分析区域"],
            index=0,
            key="poi_viz",
        )
        if poi_viz_type in ("单指标散点图", "单指标热力图", "KDE 热力图", "等值线图"):
            poi_indicator = st.selectbox(
                "着色/加权指标",
                ["rating_numeric", "density"],
                format_func=lambda x: "评分" if x == "rating_numeric" else "密度(点数)",
                key="poi_indicator",
            )
        elif poi_viz_type == "点选雷达图分析区域":
            st.caption("点击地图更新右侧类别雷达图")
        if poi_viz_type == "标记点图":
            poi_cluster = st.checkbox("标记聚合", value=True, key="poi_cluster")
            poi_color_by_group = st.checkbox("按类型着色", value=False, key="poi_color_group")
        poi_clip_bounds = st.checkbox("裁剪到徐家汇范围", value=True, key="poi_clip")
    elif module == "🏠 房价小区":
        st.header("🏠 房价模块")
        house_file_options = list(HOUSE_FILES.keys())
        house_file_labels = [HOUSE_FILES[k] for k in house_file_options]
        house_file_idx = st.selectbox(
            "房价数据文件",
            range(len(house_file_options)),
            format_func=lambda i: house_file_labels[i],
            key="house_file",
        )
        house_viz_type = st.radio(
            "可视化类型",
            ["标记点图", "单指标散点图", "单指标热力图", "KDE 热力图", "等值线图", "点选雷达图分析区域"],
            index=0,
            key="house_viz",
        )
        if house_viz_type in ("单指标散点图", "单指标热力图", "KDE 热力图", "等值线图"):
            house_indicator = st.selectbox(
                "着色/加权指标",
                list(HOUSE_INDICATORS.keys()),
                format_func=lambda x: HOUSE_INDICATORS[x],
                key="house_indicator",
            )
        elif house_viz_type == "点选雷达图分析区域":
            st.caption("点击地图更新右侧多指标雷达图")
        if house_viz_type == "标记点图":
            house_cluster = st.checkbox("标记聚合", value=True, key="house_cluster")
            house_color_by = st.selectbox(
                "按指标着色",
                ["无"] + list(HOUSE_INDICATORS.keys()),
                format_func=lambda x: "无" if x == "无" else HOUSE_INDICATORS[x],
                key="house_color",
            )
        house_clip_bounds = st.checkbox("裁剪到徐家汇范围", value=True, key="house_clip")
        house_convert_gcj = st.checkbox(
            "坐标纠偏 (GCJ→WGS84)",
            value=False,
            key="house_convert_gcj",
            help="若房价数据来源为高德/GCJ-02，请勾选",
        )
    elif module == "🗺️ 用地类型":
        st.header("🗺️ 用地模块")
        st.subheader("选择指标")
        landuse_indicator = st.radio(
            "指标",
            ["Shannon 熵", "绿地率", "混合用途（类型数）", "多边形地图"],
            index=0,
            key="landuse_indicator",
        )
        landuse_indicator_map = {
            "Shannon 熵": "shannon",
            "绿地率": "green_rate",
            "混合用途（类型数）": "n_types",
        }
        if landuse_indicator != "多边形地图":
            st.subheader("可视化类型")
            landuse_viz_type = st.radio(
                "可视化类型",
                [
                    "单指标散点图",
                    "单指标热力图",
                    "双变量对比",
                    "KDE 热力图",
                    "等值线图",
                    "点选雷达图分析区域",
                    "类别统计",
                ],
                index=0,
                key="landuse_viz",
            )
            if landuse_viz_type == "双变量对比":
                landuse_indicator2 = st.selectbox(
                    "指标 2",
                    ["Shannon 熵", "绿地率", "混合用途（类型数）"],
                    key="landuse_ind2",
                )
            st.divider()
            st.subheader("雷达图")
            landuse_radar_indicators = st.multiselect(
                "雷达图指标",
                ["shannon", "green_rate", "n_types"],
                default=["shannon", "green_rate", "n_types"],
                format_func=lambda x: {"shannon": "Shannon 熵", "green_rate": "绿地率", "n_types": "混合用途"}[x],
                key="landuse_radar",
            )
        st.caption("数据来自 OSM，需先运行 python fetch_landuse.py 拉取")
    elif module == "🛣️ 路网":
        st.header("🛣️ 路网模块")
        road_viz_type = st.radio(
            "可视化类型",
            ["道路类型 (highway)", "车道数 (lanes)", "限速 (maxspeed)", "路段长度 (length)"],
            index=0,
            key="road_viz",
        )
        road_viz_map = {
            "道路类型 (highway)": "highway",
            "车道数 (lanes)": "lanes",
            "限速 (maxspeed)": "maxspeed",
            "路段长度 (length)": "length",
        }
        road_max_edges = st.select_slider(
            "地图显示边数（分级渲染，减少卡顿）",
            options=[100, 300, 500, 1000, 2000, 0],
            value=500,
            format_func=lambda x: f"{x}" if x > 0 else "全部",
            key="road_max_edges",
        )
        road_max_edges = None if road_max_edges == 0 else road_max_edges
        st.caption("数据来自 road/xujiahui_walk.graphml，需先运行 python fetch_road_network.py")
    elif module == "🔧 适老化改造优先级":
        st.header("🔧 CLD 改造优先级")
        st.caption("基于街景、POI、用地、人口、路网，计算人机共生适老化改造优先路段")
        cld_map_edges = st.select_slider(
            "地图显示边数（分级渲染）",
            options=[100, 300, 500, 1000, 2000, 0],
            value=500,
            format_func=lambda x: f"{x}" if x > 0 else "全部",
            key="cld_map_edges",
        )
        cld_run_clicked = st.button("🔄 计算改造优先级", type="primary", use_container_width=True, key="cld_run_btn")
        if cld_run_clicked:
            if "cld_result" in st.session_state:
                del st.session_state["cld_result"]
            st.session_state["cld_run_requested"] = True
    elif module == "📐 CLD 回路":
        st.header("📐 系统动力学")
        st.caption("适老化空间因果回路图（CLD）结构说明")
    st.markdown("---")

# ==================== 主内容区 ====================
if module == "📊 街景指标":
    if compute_clicked or "result" not in st.session_state or st.session_state.get("csv_name") != csv_name:
        with st.spinner("加载街景数据..."):
            result, err = cached_load_and_compute(csv_name)
            if err:
                st.error(err)
            else:
                st.session_state["result"] = result
                st.session_state["csv_name"] = csv_name

    result = st.session_state.get("result")
    if result is None:
        st.info("👈 选择数据文件并点击「计算并可视化」")
    else:
        df = result if len(result) <= sample_size else result.sample(n=sample_size, random_state=42)
        indicator_desc = {
            "GVI": "绿视率", "SVF": "天空可见度", "Enclosure": "围合度", "BVI": "蓝视率",
            "Ped_Infra": "步行基础设施", "Motor_Pressure": "机动车压力", "Ped_Safety": "步行安全感",
            "Shade_Comfort": "遮蔽舒适度", "Shannon_H": "Shannon 多样性", "Simpson_D": "Simpson 多样性",
            "Complexity": "视觉复杂度", "Fascination": "ART 魅力", "Being_Away": "ART 远离",
            "Coherence": "ART 延展", "Ped_Friendly": "ART 兼容", "ART_Score": "ART 综合恢复潜力",
        }
        invert = indicator in INVERT_INDICATORS if indicator else False
        m = map_fig = None

        with st.container():
            cols = st.columns(3)
            with cols[0]:
                st.metric("数据文件", st.session_state.get("csv_name", csv_name))
            with cols[1]:
                st.metric("有效记录", f"{len(result):,}")
            with cols[2]:
                st.metric("显示点数", f"{len(df):,}")
            if indicator and indicator in indicator_desc:
                st.markdown(
                    f'<p class="indicator-caption"><b>{indicator}</b>: {indicator_desc[indicator]}</p>',
                    unsafe_allow_html=True,
                )

        try:
            if viz_type == "单指标散点图":
                m = create_point_map(df, indicator, invert=invert)
            elif viz_type == "点选雷达图分析区域":
                map_fig = create_clickable_map(df, indicator, map_center=MAP_CENTER, invert_colors=invert)
            elif viz_type == "单指标热力图":
                m = create_heatmap(df, indicator)
            elif viz_type == "双变量对比" and indicator2 and indicator != indicator2:
                m = create_bivariate_map(df, indicator, indicator2)
            elif viz_type == "KDE 热力图":
                m = create_kde_heatmap(df, indicator, map_center=MAP_CENTER, map_zoom=MAP_ZOOM, invert_colors=invert)
            elif viz_type == "等值线图":
                m = create_contour_map(df, indicator, map_center=MAP_CENTER, map_zoom=MAP_ZOOM, invert_colors=invert)
        except Exception as e:
            st.error(f"生成地图时出错: {e}")

        col_map, col_radar = st.columns([1.5, 1])
        map_click_event = None

        with col_map:
            if map_fig is not None:
                map_click_event = st.plotly_chart(
                    map_fig, key="map_click", on_select="rerun", selection_mode="points", use_container_width=True
                )
                st.caption("👆 点击地图上的点可更新右侧雷达图")
            elif m:
                try:
                    from streamlit_folium import folium_static
                    folium_static(m, width=900, height=600)
                except ImportError:
                    import streamlit.components.v1 as components
                    components.html(m._repr_html_(), height=600, scrolling=True)
            else:
                st.warning("无法生成地图")
            if overlay_population and m is not None:
                overlay_tif = POPULATION_DIR / "population_age65above.tif"
                pop_data, pop_bounds, pop_nodata, _ = cached_load_population(overlay_tif)
                if pop_data is not None:
                    add_population_overlay(m, pop_data, pop_bounds, pop_nodata, opacity=0.45)
                    st.caption("已叠加 65+ 人口图层（半透明）")

        with col_radar:
            with st.expander("📊 雷达图", expanded=True):
                if radar_indicators and len(radar_indicators) >= 2:
                    row_idx = None
                    if map_fig and map_click_event:
                        sel = getattr(map_click_event, "selection", None) or (map_click_event.get("selection") if isinstance(map_click_event, dict) else None)
                        if sel:
                            idx = getattr(sel, "point_indices", None) or (sel.get("point_indices") or [])
                            if idx and 0 <= idx[0] < len(df):
                                row_idx = idx[0]
                    if row_idx is not None:
                        row = df.iloc[row_idx]
                        radar_fig = create_radar_chart(df, radar_indicators, title=f"点位 (经 {row['lon']:.4f}, 纬 {row['lat']:.4f})", row_index=row_idx)
                    else:
                        radar_fig = create_radar_chart(result, radar_indicators, title="区域聚合", aggregation="mean")
                    if radar_fig:
                        st.plotly_chart(radar_fig, use_container_width=True)
                else:
                    st.caption("请选择至少 2 个雷达图指标")

        with st.expander("📋 数据预览"):
            st.dataframe(df.head(100), use_container_width=True)

# ==================== 人口分布主逻辑 ====================
elif module == "👥 人口分布":
    pop_file_idx = st.session_state.get("pop_file", 0)
    pop_file_key = POP_FILE_OPTIONS[pop_file_idx]
    pop_tif_path = _resolve_population_path(f"{pop_file_key}.tif")
    pop_viz_type = st.session_state.get("pop_viz", "栅格热力图")
    pop_subsample = st.session_state.get("pop_subsample", 2)

    if pop_viz_type == "点选雷达图分析区域":
        pop_df = cached_combined_population(pop_subsample)
        pop_indicator = "total_pop" if pop_df is not None and "total_pop" in pop_df.columns else "age65above"
        pop_radar_indicators = [c for c in ["age0_14", "age15_59", "age60_64", "age65above"] if pop_df is not None and c in pop_df.columns]
    else:
        pop_data, pop_bounds, pop_nodata, pop_stats = cached_load_population(pop_tif_path)
        pop_df = cached_population_dataframe(pop_tif_path, pop_subsample) if pop_viz_type in ("KDE 热力图", "等值线图") else None

    if pop_viz_type == "点选雷达图分析区域":
        if pop_df is None or len(pop_df) == 0:
            st.warning("多年龄段人口数据不足，请先运行 `python clip_population.py` 裁剪全部人口文件")
        elif len(pop_radar_indicators) < 2:
            st.warning("至少需要 2 个年龄段数据才能生成雷达图")
        else:
            with st.container():
                st.markdown('<div class="module-card module-card-population">', unsafe_allow_html=True)
                st.subheader(f"👥 徐家汇人口 · {POPULATION_FILES.get(pop_file_key, pop_file_key)}")
                st.caption("点选地图更新右侧年龄段雷达图")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("有效点数", f"{len(pop_df):,}")
                with c2:
                    st.metric("着色指标", pop_indicator)
                with c3:
                    st.metric("雷达图维度", ", ".join(pop_radar_indicators))
                st.markdown("</div>", unsafe_allow_html=True)

            try:
                pop_map_fig = create_clickable_map(
                    pop_df, pop_indicator,
                    map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                    invert_colors=False,
                )
            except Exception as e:
                pop_map_fig = None
                st.error(f"生成地图出错: {e}")

            col_pop_map, col_pop_radar = st.columns([1.5, 1])
            pop_click = None
            with col_pop_map:
                if pop_map_fig:
                    pop_click = st.plotly_chart(
                        pop_map_fig, key="pop_map_click", on_select="rerun", selection_mode="points", use_container_width=True
                    )
                    st.caption("👆 点击地图上的点可更新右侧年龄段雷达图")
                else:
                    st.warning("无法生成地图")

            with col_pop_radar:
                with st.expander("📊 年龄段雷达图", expanded=True):
                    row_idx = None
                    if pop_click is not None:
                        sel = getattr(pop_click, "selection", None) or (pop_click.get("selection") if isinstance(pop_click, dict) else None)
                        if sel:
                            idx = getattr(sel, "point_indices", None) or (sel.get("point_indices") or [])
                            if idx and 0 <= idx[0] < len(pop_df):
                                row_idx = idx[0]
                    if row_idx is not None:
                        row = pop_df.iloc[row_idx]
                        radar_fig = create_radar_chart(
                            pop_df, pop_radar_indicators,
                            title=f"点位 (经 {row['lon']:.4f}, 纬 {row['lat']:.4f})",
                            row_index=row_idx,
                            normalize=False,
                        )
                    else:
                        radar_fig = create_radar_chart(
                            pop_df, pop_radar_indicators,
                            title="区域聚合",
                            aggregation="mean",
                            normalize=False,
                        )
                    if radar_fig:
                        st.plotly_chart(radar_fig, use_container_width=True)

    elif (pop_viz_type == "栅格热力图" and pop_data is None) or (pop_viz_type in ("KDE 热力图", "等值线图") and pop_df is None):
        st.warning(f"人口数据不存在: {pop_tif_path}")
        st.info("请先运行 `python clip_population.py` 生成裁剪后的人口数据。若已生成，请刷新页面或清除缓存（右上角菜单 → Clear cache）后重试。")
    elif pop_viz_type in ("栅格热力图", "KDE 热力图", "等值线图"):
        with st.container():
            st.markdown('<div class="module-card module-card-population">', unsafe_allow_html=True)
            st.subheader(f"👥 徐家汇人口 · {POPULATION_FILES.get(pop_file_key, pop_file_key)}")
            st.caption("100m 栅格 · 高阶可视化")
            if pop_viz_type == "栅格热力图":
                pop_opacity = st.slider("图层透明度", 0.2, 0.9, 0.6, 0.05, key="pop_opacity")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("有效格网数", f"{pop_stats['count']:,.0f}")
                with c2:
                    st.metric("人口合计", f"{pop_stats['sum']:,.0f}")
                with c3:
                    st.metric("格网均值", f"{pop_stats['mean']:.1f}")
                with c4:
                    st.metric("格网最大值", f"{pop_stats['max']:.1f}")
            else:
                st.metric("有效点数", f"{len(pop_df):,}")
            st.markdown("</div>", unsafe_allow_html=True)

        m_pop = None
        try:
            if pop_viz_type == "栅格热力图":
                m_pop = create_population_map(
                    pop_data, pop_bounds, pop_nodata,
                    map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                    cmap_name="YlOrRd", opacity=pop_opacity,
                )
            elif pop_viz_type == "KDE 热力图":
                m_pop = create_kde_heatmap(
                    pop_df, "population",
                    map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                    cmap_name="YlOrRd", invert_colors=False,
                )
            elif pop_viz_type == "等值线图":
                m_pop = create_contour_map(
                    pop_df, "population",
                    map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                    cmap_name="YlOrRd", invert_colors=False,
                )
        except Exception as e:
            st.error(f"生成地图时出错: {e}")

        if m_pop:
            try:
                from streamlit_folium import folium_static
                folium_static(m_pop, width=1100, height=600)
            except ImportError:
                import streamlit.components.v1 as components
                components.html(m_pop._repr_html_(), height=600, scrolling=True)

# ==================== POI 分布主逻辑 ====================
elif module == "📍 POI 分布":
    poi_file_idx = st.session_state.get("poi_file", 0)
    poi_file_options = list(POI_FILES.keys())
    poi_file_key = poi_file_options[poi_file_idx]
    poi_csv_path = POI_DIR / poi_file_key
    poi_viz_type = st.session_state.get("poi_viz", "标记点图")
    poi_cluster = st.session_state.get("poi_cluster", True)
    poi_color_by_group = st.session_state.get("poi_color_group", False)
    poi_clip_bounds = st.session_state.get("poi_clip", True)
    poi_indicator = st.session_state.get("poi_indicator", "rating_numeric")

    poi_df = cached_load_poi(poi_file_key, clip_bounds=poi_clip_bounds)

    if poi_df is None or len(poi_df) == 0:
        st.warning(f"POI 数据不存在或为空: {poi_csv_path}")
        st.info("请确认 poi_data 文件夹下有对应的数据文件（CSV 或 Excel）")
    else:
        poi_df_viz = prepare_poi_for_viz(poi_df)
        poi_stats = get_poi_stats(poi_df)

        with st.container():
            st.markdown('<div class="module-card module-card-poi">', unsafe_allow_html=True)
            st.subheader(f"📍 POI 分布 · {POI_FILES.get(poi_file_key, poi_file_key)}")
            st.caption("高德 POI 数据 · 高阶可视化")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("POI 数量", f"{poi_stats['count']:,}")
            with c2:
                st.metric("含评分", f"{poi_stats['with_rating']:,}")
            with c3:
                st.metric("可视化类型", poi_viz_type)
            st.markdown("</div>", unsafe_allow_html=True)

        m_poi = None
        map_fig_poi = None

        try:
            if poi_viz_type == "标记点图":
                m_poi = create_poi_map(
                    poi_df,
                    map_center=MAP_CENTER,
                    map_zoom=MAP_ZOOM,
                    cluster=poi_cluster,
                    color_by_group=poi_color_by_group,
                )
            elif poi_viz_type == "单指标散点图":
                ind_label = "评分" if poi_indicator == "rating_numeric" else "密度"
                m_poi = create_point_map(
                    poi_df_viz, poi_indicator,
                    title=f"POI {ind_label}",
                    invert=False,
                )
            elif poi_viz_type == "单指标热力图":
                ind_label = "评分" if poi_indicator == "rating_numeric" else "密度"
                m_poi = create_heatmap(poi_df_viz, poi_indicator, title=f"POI {ind_label} 热力图")
            elif poi_viz_type == "KDE 热力图":
                m_poi = create_kde_heatmap(
                    poi_df_viz, poi_indicator,
                    map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                    cmap_name="YlOrRd", invert_colors=False,
                )
            elif poi_viz_type == "等值线图":
                m_poi = create_contour_map(
                    poi_df_viz, poi_indicator,
                    map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                    cmap_name="YlOrRd", invert_colors=False,
                )
            elif poi_viz_type == "点选雷达图分析区域":
                map_fig_poi = create_clickable_map(
                    poi_df_viz, "rating_numeric",
                    map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                    invert_colors=False,
                )
        except Exception as e:
            st.error(f"生成地图时出错: {e}")

        if poi_viz_type == "点选雷达图分析区域":
            col_poi_map, col_poi_radar = st.columns([1.5, 1])
            poi_click = None
            with col_poi_map:
                if map_fig_poi:
                    poi_click = st.plotly_chart(
                        map_fig_poi, key="poi_map_click", on_select="rerun", selection_mode="points", use_container_width=True
                    )
                    st.caption("👆 点击地图上的点可更新右侧类别雷达图")
                else:
                    st.warning("无法生成地图")

            with col_poi_radar:
                with st.expander("📊 周边类别雷达图", expanded=True):
                    row_idx = None
                    radar_fig = None
                    if poi_click is not None:
                        sel = getattr(poi_click, "selection", None) or (poi_click.get("selection") if isinstance(poi_click, dict) else None)
                        if sel:
                            idx = getattr(sel, "point_indices", None) or (sel.get("point_indices") or [])
                            if idx and 0 <= idx[0] < len(poi_df_viz):
                                row_idx = idx[0]
                    if row_idx is not None:
                        row = poi_df_viz.iloc[row_idx]
                        cat_counts = aggregate_poi_by_category_near(
                            poi_df_viz, row["lat"], row["lon"], radius_km=0.5
                        )
                        if len(cat_counts) >= 2:
                            radar_df = pd.DataFrame([cat_counts])
                            radar_indicators = list(cat_counts.keys())
                            radar_fig = create_radar_chart(
                                radar_df, radar_indicators,
                                title=f"周边 500m 内 (经 {row['lon']:.4f}, 纬 {row['lat']:.4f})",
                                row_index=0,
                                normalize=False,
                            )
                        else:
                            radar_fig = create_radar_chart(
                                pd.DataFrame([cat_counts]) if cat_counts else pd.DataFrame(),
                                list(cat_counts.keys()) if cat_counts else [],
                                title="周边类别",
                                row_index=0,
                                normalize=False,
                            )
                    else:
                        all_cats = poi_df_viz["category"].value_counts()
                        if len(all_cats) >= 2:
                            radar_df = pd.DataFrame([all_cats.to_dict()])
                            radar_fig = create_radar_chart(
                                radar_df, list(all_cats.index[:8]),
                                title="区域聚合（各类别数量）",
                                row_index=0,
                                normalize=False,
                            )
                        else:
                            radar_fig = None
                    if radar_fig:
                        st.plotly_chart(radar_fig, use_container_width=True)
                    else:
                        st.caption("请选择至少 2 个类别的 POI 数据，或点击地图上的点")
        else:
            if m_poi:
                try:
                    from streamlit_folium import folium_static
                    folium_static(m_poi, width=1100, height=600)
                except ImportError:
                    import streamlit.components.v1 as components
                    components.html(m_poi._repr_html_(), height=600, scrolling=True)

        with st.expander("📋 数据预览"):
            preview_cols = [c for c in ["name", "type", "address", "lng", "lat", "group", "rating_numeric"] if c in poi_df_viz.columns]
            st.dataframe(poi_df_viz[preview_cols].head(100), use_container_width=True)

# ==================== 房价小区主逻辑 ====================
elif module == "🏠 房价小区":
    house_file_idx = st.session_state.get("house_file", 0)
    house_file_options = list(HOUSE_FILES.keys())
    house_file_key = house_file_options[house_file_idx]
    house_path = HOUSE_DIR / house_file_key
    house_viz_type = st.session_state.get("house_viz", "标记点图")
    house_cluster = st.session_state.get("house_cluster", True)
    house_color_by = st.session_state.get("house_color", "无")
    house_clip_bounds = st.session_state.get("house_clip", True)
    house_convert_gcj = st.session_state.get("house_convert_gcj", False)
    house_indicator = st.session_state.get("house_indicator", "unit_price")

    house_df = cached_load_house(
        house_file_key,
        clip_bounds=house_clip_bounds,
        convert_gcj02_to_wgs84=house_convert_gcj,
    )

    if house_df is None or len(house_df) == 0:
        st.warning(f"房价数据不存在或为空: {house_path}")
        st.info("请确认 house_data 文件夹下有 house_total.xlsx")
    else:
        house_df_viz = prepare_house_for_viz(house_df)
        house_stats = get_house_stats(house_df)

        with st.container():
            st.markdown('<div class="module-card module-card-house">', unsafe_allow_html=True)
            st.subheader(f"🏠 房价小区 · {HOUSE_FILES.get(house_file_key, house_file_key)}")
            st.caption("小区均价 · 容积率 · 绿化率 · 竣工年份 · 高阶可视化")
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("小区数量", f"{house_stats['count']:,}")
            with c2:
                st.metric("含均价", f"{house_stats['with_price']:,}")
            with c3:
                st.metric("均价均值", f"{house_stats['price_mean']:,.0f} 元/㎡" if house_stats['price_mean'] else "—")
            with c4:
                st.metric("均价中位数", f"{house_stats['price_median']:,.0f} 元/㎡" if house_stats['price_median'] else "—")
            with c5:
                st.metric("可视化类型", house_viz_type)
            st.markdown("</div>", unsafe_allow_html=True)

        m_house = None
        map_fig_house = None

        try:
            if house_viz_type == "标记点图":
                color_by = None if house_color_by == "无" else house_color_by
                m_house = create_house_map(
                    house_df,
                    map_center=MAP_CENTER,
                    map_zoom=MAP_ZOOM,
                    cluster=house_cluster,
                    color_by=color_by,
                )
            elif house_viz_type == "单指标散点图":
                _hv = house_df_viz.dropna(subset=[house_indicator])
                if len(_hv) > 0:
                    ind_label = HOUSE_INDICATORS.get(house_indicator, house_indicator)
                    m_house = create_point_map(
                        _hv, house_indicator,
                        title=f"小区 {ind_label}",
                        invert=False,
                    )
            elif house_viz_type == "单指标热力图":
                _hv = house_df_viz.dropna(subset=[house_indicator])
                if len(_hv) > 0:
                    ind_label = HOUSE_INDICATORS.get(house_indicator, house_indicator)
                    m_house = create_heatmap(_hv, house_indicator, title=f"小区 {ind_label} 热力图")
            elif house_viz_type == "KDE 热力图":
                _hv = house_df_viz.dropna(subset=[house_indicator])
                if len(_hv) > 0:
                    m_house = create_kde_heatmap(
                        _hv, house_indicator,
                        map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                        cmap_name="YlOrRd", invert_colors=False,
                    )
            elif house_viz_type == "等值线图":
                _hv = house_df_viz.dropna(subset=[house_indicator])
                if len(_hv) > 0:
                    m_house = create_contour_map(
                        _hv, house_indicator,
                        map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                        cmap_name="YlOrRd", invert_colors=False,
                    )
            elif house_viz_type == "点选雷达图分析区域":
                _click_ind = house_indicator if house_df_viz[house_indicator].notna().sum() > 0 else "unit_price"
                if house_df_viz[_click_ind].notna().sum() == 0:
                    for c in ["plot_ratio", "greening_rate", "completion_year", "density"]:
                        if c in house_df_viz.columns and house_df_viz[c].notna().sum() > 0:
                            _click_ind = c
                            break
                map_fig_house = create_clickable_map(
                    house_df_viz, _click_ind,
                    map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                    invert_colors=False,
                )
        except Exception as e:
            st.error(f"生成地图时出错: {e}")

        if house_viz_type == "点选雷达图分析区域":
            col_house_map, col_house_radar = st.columns([1.5, 1])
            house_click = None
            with col_house_map:
                if map_fig_house:
                    house_click = st.plotly_chart(
                        map_fig_house, key="house_map_click", on_select="rerun", selection_mode="points", use_container_width=True
                    )
                    st.caption("👆 点击地图上的点可更新右侧多指标雷达图")
                else:
                    st.warning("无法生成地图")

            with col_house_radar:
                with st.expander("📊 小区指标雷达图", expanded=True):
                    row_idx = None
                    radar_fig = None
                    if house_click is not None:
                        sel = getattr(house_click, "selection", None) or (house_click.get("selection") if isinstance(house_click, dict) else None)
                        if sel:
                            idx = getattr(sel, "point_indices", None) or (sel.get("point_indices") or [])
                            if idx and 0 <= idx[0] < len(house_df_viz):
                                row_idx = idx[0]
                    radar_inds = [c for c in ["unit_price", "plot_ratio", "greening_rate", "completion_year"] if c in house_df_viz.columns and house_df_viz[c].notna().sum() >= 2]
                    if row_idx is not None and len(radar_inds) >= 2:
                        row = house_df_viz.iloc[row_idx]
                        radar_fig = create_radar_chart(
                            house_df_viz, radar_inds,
                            title=f"点位 (经 {row['lon']:.4f}, 纬 {row['lat']:.4f})",
                            row_index=row_idx,
                            normalize=True,
                        )
                    elif len(radar_inds) >= 2:
                        radar_fig = create_radar_chart(
                            house_df_viz, radar_inds,
                            title="区域聚合",
                            aggregation="mean",
                            normalize=True,
                        )
                    if radar_fig:
                        st.plotly_chart(radar_fig, use_container_width=True)
                    else:
                        st.caption("请选择至少 2 个有效指标，或点击地图上的点")
        else:
            if m_house:
                try:
                    from streamlit_folium import folium_static
                    folium_static(m_house, width=1100, height=600)
                except ImportError:
                    import streamlit.components.v1 as components
                    components.html(m_house._repr_html_(), height=600, scrolling=True)

        with st.expander("📋 数据预览"):
            preview_cols = [c for c in ["name", "address", "lon", "lat", "unit_price", "plot_ratio", "greening_rate", "completion_year"] if c in house_df_viz.columns]
            st.dataframe(house_df_viz[preview_cols].head(100), use_container_width=True)

# ==================== 用地类型主逻辑 ====================
elif module == "🗺️ 用地类型":
    landuse_indicator = st.session_state.get("landuse_indicator", "Shannon 熵")
    landuse_viz_type = st.session_state.get("landuse_viz", "单指标散点图") if landuse_indicator != "多边形地图" else None
    landuse_indicator_map = {
        "Shannon 熵": "shannon",
        "绿地率": "green_rate",
        "混合用途（类型数）": "n_types",
    }
    ind_col = landuse_indicator_map.get(landuse_indicator)

    gdf_landuse, centroid_df = cached_load_landuse()
    landuse_grid_df = cached_landuse_grid_metrics(LANDUSE_DIR) if gdf_landuse is not None else None

    if gdf_landuse is None and centroid_df is None:
        st.warning("用地数据不存在")
        st.info("请先运行 `python fetch_landuse.py` 从 OSM 拉取徐家汇用地数据，将生成 landuse_data/ 目录。")
    else:
        landuse_stats = get_landuse_stats(gdf_landuse, centroid_df)
        adv_metrics = compute_landuse_advanced_metrics(gdf_landuse) if gdf_landuse is not None else {}

        with st.container():
            st.markdown('<div class="module-card module-card-landuse">', unsafe_allow_html=True)
            st.subheader("🗺️ 徐家汇用地类型 · 高级指标")
            st.caption("250m 网格 · Shannon 熵 · 绿地率 · 混合用途 · 与街景模块同构")
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("网格点数", f"{len(landuse_grid_df):,}" if landuse_grid_df is not None and len(landuse_grid_df) > 0 else "0")
            with c2:
                st.metric("多边形数", f"{landuse_stats['polygon_count']:,}")
            with c3:
                st.metric("Shannon 熵（全域）", f"{adv_metrics.get('shannon_entropy', 0):.4f}")
            with c4:
                st.metric("绿地率（全域）", f"{adv_metrics.get('green_space_rate_pct', 0)}%")
            with c5:
                st.metric("混合用途比例（全域）", f"{adv_metrics.get('mixed_use_ratio_pct', 0)}%")
            st.markdown("</div>", unsafe_allow_html=True)

        if landuse_indicator:
            st.markdown(
                f'<p class="indicator-caption"><b>{landuse_indicator}</b></p>',
                unsafe_allow_html=True,
            )

        m_landuse = None
        map_fig_landuse = None
        invert_landuse = ind_col == "green_rate" if ind_col else False

        try:
            if landuse_indicator == "多边形地图" and gdf_landuse is not None and len(gdf_landuse) > 0:
                m_landuse = create_landuse_map(
                    gdf_landuse,
                    map_center=MAP_CENTER,
                    map_zoom=MAP_ZOOM,
                )
            elif landuse_viz_type in ("单指标散点图", "单指标热力图", "KDE 热力图", "等值线图", "双变量对比", "点选雷达图分析区域"):
                if landuse_grid_df is None or len(landuse_grid_df) == 0:
                    st.warning("网格指标数据为空，请确保用地 GeoJSON 存在。")
                elif ind_col not in landuse_grid_df.columns:
                    st.warning(f"指标 {ind_col} 不存在于数据中。")
                else:
                    df_landuse = landuse_grid_df
                    if landuse_viz_type == "单指标散点图":
                        m_landuse = create_point_map(df_landuse, ind_col, invert=invert_landuse)
                    elif landuse_viz_type == "单指标热力图":
                        m_landuse = create_heatmap(df_landuse, ind_col)
                    elif landuse_viz_type == "KDE 热力图":
                        m_landuse = create_kde_heatmap(
                            df_landuse, ind_col,
                            map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                            invert_colors=invert_landuse,
                        )
                    elif landuse_viz_type == "等值线图":
                        m_landuse = create_contour_map(
                            df_landuse, ind_col,
                            map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                            invert_colors=invert_landuse,
                        )
                    elif landuse_viz_type == "双变量对比":
                        ind2 = landuse_indicator_map.get(
                            st.session_state.get("landuse_ind2", "绿地率"),
                            "green_rate",
                        )
                        if ind2 != ind_col and ind2 in df_landuse.columns:
                            m_landuse = create_bivariate_map(df_landuse, ind_col, ind2)
                        else:
                            st.warning("请选择不同的指标进行双变量对比")
                    elif landuse_viz_type == "点选雷达图分析区域":
                        map_fig_landuse = create_clickable_map(
                            df_landuse, ind_col,
                            map_center=MAP_CENTER, map_zoom=MAP_ZOOM,
                            invert_colors=invert_landuse,
                        )
            elif landuse_viz_type == "类别统计" and centroid_df is not None and "landuse_type" in centroid_df.columns:
                type_counts = centroid_df["landuse_type"].value_counts()
                import plotly.express as px
                fig = px.bar(
                    x=type_counts.index,
                    y=type_counts.values,
                    labels={"x": "用地类型", "y": "数量"},
                    title="用地类型分布",
                )
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"生成地图时出错: {e}")

        col_map_landuse, col_radar_landuse = st.columns([1.5, 1])
        map_click_landuse = None

        with col_map_landuse:
            if map_fig_landuse is not None:
                map_click_landuse = st.plotly_chart(
                    map_fig_landuse, key="map_click_landuse", on_select="rerun", selection_mode="points", use_container_width=True
                )
                st.caption("👆 点击地图上的点可更新右侧雷达图")
            elif m_landuse:
                try:
                    from streamlit_folium import folium_static
                    folium_static(m_landuse, width=1100, height=600)
                except ImportError:
                    import streamlit.components.v1 as components
                    components.html(m_landuse._repr_html_(), height=600, scrolling=True)
            elif landuse_viz_type != "类别统计" and landuse_indicator != "多边形地图":
                st.warning("无法生成地图")

        with col_radar_landuse:
            radar_inds = st.session_state.get("landuse_radar", ["shannon", "green_rate", "n_types"])
            if landuse_indicator != "多边形地图" and landuse_grid_df is not None and len(landuse_grid_df) > 0 and radar_inds and len(radar_inds) >= 2:
                with st.expander("📊 雷达图", expanded=True):
                    row_idx = None
                    if map_fig_landuse and map_click_landuse:
                        sel = getattr(map_click_landuse, "selection", None) or (map_click_landuse.get("selection") if isinstance(map_click_landuse, dict) else None)
                        if sel:
                            idx = getattr(sel, "point_indices", None) or (sel.get("point_indices") or [])
                            if idx and 0 <= idx[0] < len(landuse_grid_df):
                                row_idx = idx[0]
                    valid_radar = [c for c in radar_inds if c in landuse_grid_df.columns]
                    if len(valid_radar) >= 2:
                        if row_idx is not None:
                            row = landuse_grid_df.iloc[row_idx]
                            radar_fig = create_radar_chart(
                                landuse_grid_df, valid_radar,
                                title=f"网格 (经 {row['lon']:.4f}, 纬 {row['lat']:.4f})",
                                row_index=row_idx,
                            )
                        else:
                            radar_fig = create_radar_chart(
                                landuse_grid_df, valid_radar,
                                title="区域聚合",
                                aggregation="mean",
                            )
                        if radar_fig:
                            st.plotly_chart(radar_fig, use_container_width=True)
                    else:
                        st.caption("请选择至少 2 个雷达图指标")
            elif landuse_indicator != "多边形地图" and landuse_viz_type in ("单指标散点图", "单指标热力图", "KDE 热力图", "等值线图", "点选雷达图分析区域"):
                st.caption("雷达图需至少 2 个指标")

        with st.expander("📋 数据预览"):
            if landuse_grid_df is not None and len(landuse_grid_df) > 0:
                st.dataframe(landuse_grid_df.head(100), use_container_width=True)
            elif centroid_df is not None and len(centroid_df) > 0:
                st.dataframe(centroid_df.head(100), use_container_width=True)
            elif gdf_landuse is not None and len(gdf_landuse) > 0:
                st.dataframe(gdf_landuse.drop(columns=["geometry"], errors="ignore").head(50), use_container_width=True)

# ==================== 路网主逻辑 ====================
elif module == "🛣️ 路网":
    road_viz_label = st.session_state.get("road_viz", "道路类型 (highway)")
    road_viz_map = {
        "道路类型 (highway)": "highway",
        "车道数 (lanes)": "lanes",
        "限速 (maxspeed)": "maxspeed",
        "路段长度 (length)": "length",
    }
    viz_mode = road_viz_map.get(road_viz_label, "highway")

    G_road, edges_road = cached_load_road_network(with_coords=True)

    if G_road is None:
        st.warning("路网数据不存在")
        st.info("请先运行 `python fetch_road_network.py` 从 OSM 拉取徐家汇步行路网，将生成 road/xujiahui_walk.graphml。")
    else:
        m = compute_n04_connectivity(G_road)
        inter_density = compute_intersection_density(G_road, area_km2=12.0)
        stats = compute_road_summary_stats(G_road)

        st.markdown('<div class="module-card module-card-poi">', unsafe_allow_html=True)
        st.subheader("🛣️ 徐家汇路网")
        st.caption("N04 连通性 · 道路类型分布 · CLD 变量代理")
        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        with c1:
            st.metric("节点数", f"{m.get('n_nodes', 0):,}")
        with c2:
            st.metric("边数", f"{m.get('n_edges', 0):,}")
        with c3:
            st.metric("α 指数", f"{m.get('alpha', 0):.4f}")
        with c4:
            st.metric("β 指数", f"{m.get('beta', 0):.4f}")
        with c5:
            st.metric("交叉口密度", f"{inter_density:.2f}/km²")
        with c6:
            st.metric("步行专用路比例", f"{stats.get('pedestrian_ratio_pct', 0)}%")
        with c7:
            st.metric("机动车干道比例", f"{stats.get('motor_ratio_pct', 0)}%")
        st.markdown("</div>", unsafe_allow_html=True)

        r1, r2 = st.columns(2)
        with r1:
            st.metric("平均路段长度", f"{stats.get('avg_edge_length_m', 0):.1f} m")
        with r2:
            st.metric("lanes 数据覆盖率", f"{stats.get('lanes_coverage_pct', 0)}%")

        road_max_edges_val = st.session_state.get("road_max_edges", 500)
        road_max_edges_param = None if road_max_edges_val == 0 else road_max_edges_val
        m_road = create_road_map(
            G_road,
            map_center=tuple(MAP_CENTER),
            map_zoom=MAP_ZOOM,
            viz_mode=viz_mode,
            max_edges=road_max_edges_param,
        )
        if m_road:
            try:
                from streamlit_folium import folium_static
                folium_static(m_road, width=1100, height=600)
            except ImportError:
                import streamlit.components.v1 as components
                components.html(m_road._repr_html_(), height=600, scrolling=True)
        else:
            st.warning("路网节点缺少坐标，无法绘制地图。")

        if edges_road is not None and "highway_type" in edges_road.columns:
            hw_counts = edges_road["highway_type"].value_counts().head(15)
            import plotly.express as px
            fig_hw = px.bar(
                x=hw_counts.index,
                y=hw_counts.values,
                labels={"x": "道路类型", "y": "边数"},
                title="道路类型分布 (highway)",
            )
            st.plotly_chart(fig_hw, use_container_width=True)

        with st.expander("📊 完整 N04 指标"):
            for k, v in m.items():
                st.write(f"**{k}**: {v}")
        with st.expander("📋 边数据预览"):
            if edges_road is not None and len(edges_road) > 0:
                preview_cols = ["start_node_id", "end_node_id", "length_m", "highway_type"]
                if "name" in edges_road.columns:
                    preview_cols.append("name")
                if "maxspeed" in edges_road.columns:
                    preview_cols.append("maxspeed")
                if "lanes" in edges_road.columns:
                    preview_cols.append("lanes")
                st.dataframe(edges_road[[c for c in preview_cols if c in edges_road.columns]].head(50), use_container_width=True)

# ==================== 适老化改造优先级主逻辑 ====================
elif module == "🔧 适老化改造优先级":
    need_compute = st.session_state.get("cld_run_requested", False)
    has_result = "cld_result" in st.session_state

    if need_compute:
        # 用户点击了「重新计算」：执行流水线并缓存
        progress_bar = st.progress(0, text="准备中...")
        status_placeholder = st.empty()

        def on_progress(step: int, total: int, msg: str):
            progress_bar.progress((step + 1) / total, text=msg)
            status_placeholder.caption(f"步骤 {step + 1}/{total}: {msg}")

        try:
            landuse_df = cached_landuse_grid_metrics(LANDUSE_DIR)
            G_cld, df_prio = run_cld_pipeline(
                road_dir=ROAD_DIR,
                streetview_csv_path=DATA_DIR / "merged.csv",
                poi_csv_path=POI_DIR / "poi_all.csv",
                landuse_grid_df=landuse_df,
                population_dir=POPULATION_DIR,
                progress_callback=on_progress,
            )
            st.session_state["cld_result"] = (G_cld, df_prio)
            st.session_state["cld_run_requested"] = False
            st.session_state["cld_from_cache"] = False
            _save_cld_cache(G_cld, df_prio)
            progress_bar.progress(1.0, text="完成")
            status_placeholder.empty()
        except Exception as e:
            st.error(f"计算失败: {e}")
            st.exception(e)
            progress_bar.empty()
            status_placeholder.empty()
    elif not has_result:
        # 首次进入：尝试从本地缓存加载
        cached = _load_cld_cache()
        if cached is not None:
            G_cld, df_prio = cached
            st.session_state["cld_result"] = (G_cld, df_prio)
            st.session_state["cld_from_cache"] = True

    cld_result = st.session_state.get("cld_result")
    if cld_result is None:
        st.info("👈 点击侧边栏「计算改造优先级」开始分析")
    else:
        G_cld, df_prio = cld_result
        if G_cld is None:
            st.warning("路网数据不存在，请先运行 fetch_road_network.py")
        else:
            st.subheader("🔧 徐汇区适老化改造优先路段")
            cap = "按百分位着色：深红=Top10% 红=75-90% 橙=50-75% 黄=25-50% 绿=10-25% 灰=Bottom10%（优先改造红色路段）"
            if st.session_state.get("cld_from_cache", False):
                cap += " · 已从缓存加载，点击侧边栏「计算改造优先级」可重新计算"
            st.caption(cap)
            cld_map_edges_val = st.session_state.get("cld_map_edges", 500)
            cld_max_edges = None if cld_map_edges_val == 0 else cld_map_edges_val
            m_cld = create_road_map(
                G_cld,
                map_center=(31.19, 121.44),
                map_zoom=14,
                viz_mode="priority",
                weight=3,
                opacity=0.9,
                max_edges=cld_max_edges,
            )
            if m_cld:
                try:
                    from streamlit_folium import folium_static
                    folium_static(m_cld, width=1100, height=600)
                except Exception:
                    import streamlit.components.v1 as components
                    components.html(m_cld._repr_html_(), height=600, scrolling=True)

            if df_prio is not None and len(df_prio) > 0:
                top_n = st.slider("显示 Top 优先边数", 10, 100, 30, key="cld_top_n")
                df_top = df_prio.nlargest(top_n, "priority")
                st.dataframe(
                    df_top[["u", "v", "lon", "lat", "N02", "N15", "N17", "priority"]].round(3),
                    use_container_width=True,
                )

# ==================== CLD 回路主逻辑 ====================
elif module == "📐 CLD 回路":
    from analysis.cld_viz import create_cld_figure

    st.subheader("适老化空间系统 · 因果回路图")
    intro = """
    **系统有 4 条正向强化回路（越做越好）、3 条平衡回路（自动刹车）、1 条恶性强化回路（需人工干预）。**

    | 类型 | 回路 | 含义 |
    |------|------|------|
    | 强化 R | R1 社交活力 | 场所多→老人来→街道热闹→场所更多 |
    | 强化 R | R4 认知恢复 | 空间有挑战→激活认知→愿意探索→空间更丰富 |
    | 强化 R | R5 人机共生 | 部署装置→产生数据→优化装置→更好部署 |
    | 平衡 B | B2 拥挤调节 | 人太多→舒适度下降→不再扎堆 |
    | 平衡 B | B3 认知超载 | 太复杂→压力大→不愿探索 |
    | 平衡 B | B4 干预疲劳 | 装置太多→用腻了→数据变少 |
    | 恶性 R | R_bad 交通诱导 | 车多→噪声大→不愿步行→更多人开车→车更多（需人机干预破解） |
    """
    st.markdown(intro)
    st.divider()

    fig_cld = create_cld_figure()
    if fig_cld:
        st.plotly_chart(fig_cld, use_container_width=True)
    else:
        st.warning("需安装 plotly 以显示 CLD 图")

    with st.expander("📄 完整说明"):
        st.markdown("详见 [CLD回路简介](docs/CLD回路简介.md) 与 [cld_balance_analysis](docs/cld_balance_analysis.md)")
