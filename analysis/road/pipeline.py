"""
CLD 改造优先级计算流水线
========================
一站式加载路网、街景、POI、用地、人口，挂载并计算改造优先级。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx
    import pandas as pd


def run_cld_pipeline(
    road_dir: Path,
    streetview_csv_path: Path,
    poi_csv_path: Path,
    landuse_grid_df: "pd.DataFrame | None",
    population_dir: Path,
    streetview_indicators: list[str] | None = None,
    progress_callback: "callable[[int, int, str], None] | None" = None,
) -> "tuple[nx.DiGraph | None, pd.DataFrame | None]":
    """
    运行 CLD 流水线：加载路网 → 挂载街景/POI/用地/人口 → 计算 CLD 变量 → 计算 priority。

    Args:
        progress_callback: 可选，回调 (step, total_steps, message) 用于进度提示。

    Returns:
        (G, priority_df) - 图与边级优先级 DataFrame。
    """
    try:
        import pandas as pd
    except ImportError:
        return None, None

    def _progress(step: int, total: int, msg: str) -> None:
        if progress_callback:
            progress_callback(step, total, msg)

    from .loader import load_road_network, XUJIAHUI_BOUNDS
    from .weights import (
        attach_streetview_scores_multi,
        attach_poi_by_category,
        attach_landuse,
        attach_population_multiage,
        compute_edge_traffic_pressure,
    )
    from .cld import (
        compute_edge_cld_values,
        compute_edge_intervention_priority,
        edges_to_priority_dataframe,
    )

    TOTAL_STEPS = 9
    _progress(0, TOTAL_STEPS, "加载路网...")
    excel_path = road_dir / "Xuhui_Road_Network_Data_Fixed.xlsx"
    G, _ = load_road_network(excel_path, with_coordinates=True, bbox=XUJIAHUI_BOUNDS)
    if G is None or G.number_of_edges() == 0:
        return None, None

    _progress(1, TOTAL_STEPS, "挂载街景指标...")
    if streetview_csv_path.exists():
        df_sv = pd.read_csv(streetview_csv_path)
        if "lng" in df_sv.columns and "lon" not in df_sv.columns:
            df_sv = df_sv.rename(columns={"lng": "lon"})
        attach_streetview_scores_multi(G, df_sv, indicators=streetview_indicators)

    _progress(2, TOTAL_STEPS, "挂载 POI 分类...")
    poi_path = Path(poi_csv_path)
    if poi_path.exists():
        import sys
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from analysis.poi.loader import load_poi_data
        df_poi = load_poi_data(poi_path, bounds=XUJIAHUI_BOUNDS)
        if df_poi is not None and len(df_poi) > 0:
            attach_poi_by_category(G, df_poi, radius_m=100, category_col="group")

    _progress(3, TOTAL_STEPS, "挂载用地网格...")
    if landuse_grid_df is not None and len(landuse_grid_df) > 0:
        attach_landuse(G, landuse_grid_df)

    _progress(4, TOTAL_STEPS, "挂载人口栅格...")
    pop_dir = Path(population_dir)
    pop_paths = {}
    for key, fname in [
        ("pop_65plus", "population_age65above.tif"),
        ("pop_15_59", "population_age15_59.tif"),
        ("pop_0_14", "population_age0_14.tif"),
    ]:
        p = pop_dir / fname
        if p.exists():
            pop_paths[key] = p
    if pop_paths:
        attach_population_multiage(G, pop_paths)

    _progress(5, TOTAL_STEPS, "计算车流量代理...")
    compute_edge_traffic_pressure(G)

    _progress(6, TOTAL_STEPS, "计算 CLD 变量...")
    compute_edge_cld_values(G)

    _progress(7, TOTAL_STEPS, "计算改造优先级...")
    compute_edge_intervention_priority(G)

    _progress(8, TOTAL_STEPS, "导出结果...")
    return G, edges_to_priority_dataframe(G)
