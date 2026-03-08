"""
构建徐家汇路网图
================
加载 Excel 边列表 + OSMnx 补全节点坐标 + 计算图论指标。
用法: python build_road_network.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent
ROAD_EXCEL = ROOT / "road" / "Xuhui_Road_Network_Data_Fixed.xlsx"
OUT_GRAPH = ROOT / "road" / "xujiahui_road_graph.gpickle"
OUT_METRICS = ROOT / "road" / "n04_metrics.txt"

# 徐家汇面积约 12 km² (粗略)
XUJIAHUI_AREA_KM2 = 12.0


def main() -> None:
    from analysis.road import (
        load_road_network,
        compute_n04_connectivity,
        compute_intersection_density,
        XUJIAHUI_BOUNDS,
    )

    print("Step 1: Loading road edges from Excel...")
    G, edges = load_road_network(ROAD_EXCEL, with_coordinates=True, bbox=XUJIAHUI_BOUNDS)
    print(f"  Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

    nodes_with_coords = sum(1 for n, d in G.nodes(data=True) if d.get("lon") is not None)
    print(f"  Nodes with coordinates: {nodes_with_coords}")

    print("\nStep 2: Computing N04 connectivity metrics...")
    m = compute_n04_connectivity(G)
    for k, v in m.items():
        print(f"  {k}: {v}")

    inter_density = compute_intersection_density(G, XUJIAHUI_AREA_KM2)
    print(f"  Intersection density (per km2): {inter_density:.2f}")

    print("\nStep 3: Saving graph...")
    import networkx as nx
    nx.write_gpickle(G, OUT_GRAPH)
    print(f"  Saved to {OUT_GRAPH}")

    with open(OUT_METRICS, "w", encoding="utf-8") as f:
        f.write("N04 Road Network Connectivity\n")
        f.write("=" * 40 + "\n")
        for k, v in m.items():
            f.write(f"{k}: {v}\n")
        f.write(f"\nIntersection density (per km2): {inter_density:.2f}\n")
    print(f"  Metrics saved to {OUT_METRICS}")

    print("\nDone.")


if __name__ == "__main__":
    main()
