"""
拉取 OSM 徐家汇路网并保存到本地
================================
用法: python fetch_road_network.py

从 OpenStreetMap 下载徐家汇步行路网，保存到 road/xujiahui_walk.graphml。
之后仪表盘加载路网时直接读本地文件，无需联网。
"""

from pathlib import Path

from analysis.road import (
    load_road_network_from_osmnx,
    save_road_network_to_graphml,
    compute_n04_connectivity,
    compute_intersection_density,
    XUJIAHUI_BOUNDS,
)

ROOT = Path(__file__).parent
GRAPHML_PATH = ROOT / "road" / "xujiahui_walk.graphml"

if __name__ == "__main__":
    print("正在从 OpenStreetMap 拉取徐家汇步行路网...")
    G, edges = load_road_network_from_osmnx(bbox=XUJIAHUI_BOUNDS)
    print(f"节点: {G.number_of_nodes()}, 边: {G.number_of_edges()}")

    save_road_network_to_graphml(G, GRAPHML_PATH)
    print(f"[OK] 已保存到 {GRAPHML_PATH}")

    m = compute_n04_connectivity(G)
    print("N04 指标:", m)
    print("交叉口密度:", compute_intersection_density(G, 12.0), "/km2")
    print("仪表盘将自动加载本地路网，无需再联网。")
