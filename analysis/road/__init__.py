"""
路网图论分析模块
================
徐家汇路网加载、坐标补全、图论指标、权重挂载、最短路径/等时圈。
"""

from .loader import (
    load_road_edges,
    fetch_node_coordinates_osmnx,
    build_networkx_graph,
    load_road_network,
    load_road_network_from_osmnx,
    load_road_network_from_graphml,
    save_road_network_to_graphml,
    XUJIAHUI_BOUNDS,
    EDGE_COLUMNS,
)
from .metrics import (
    compute_n04_connectivity,
    compute_intersection_density,
    compute_road_summary_stats,
    compute_betweenness_centrality,
)
from .weights import (
    get_edge_midpoint,
    attach_streetview_scores,
    attach_streetview_scores_multi,
    attach_poi_density,
    attach_poi_by_category,
    attach_population,
    attach_landuse,
    attach_population_multiage,
    compute_edge_traffic_pressure,
)
from .paths import shortest_path, isochrone_nodes, isochrone_edges
from .pipeline import run_cld_pipeline
from .cld import (
    compute_edge_cld_values,
    compute_edge_intervention_priority,
    edges_to_priority_dataframe,
)
from .overlay import create_road_map

__all__ = [
    "load_road_edges",
    "fetch_node_coordinates_osmnx",
    "build_networkx_graph",
    "load_road_network",
    "load_road_network_from_osmnx",
    "load_road_network_from_graphml",
    "save_road_network_to_graphml",
    "XUJIAHUI_BOUNDS",
    "EDGE_COLUMNS",
    "compute_n04_connectivity",
    "compute_intersection_density",
    "compute_road_summary_stats",
    "compute_betweenness_centrality",
    "get_edge_midpoint",
    "attach_streetview_scores",
    "attach_streetview_scores_multi",
    "attach_poi_density",
    "attach_poi_by_category",
    "attach_population",
    "attach_landuse",
    "attach_population_multiage",
    "compute_edge_traffic_pressure",
    "compute_edge_cld_values",
    "compute_edge_intervention_priority",
    "edges_to_priority_dataframe",
    "run_cld_pipeline",
    "shortest_path",
    "isochrone_nodes",
    "isochrone_edges",
    "create_road_map",
]
