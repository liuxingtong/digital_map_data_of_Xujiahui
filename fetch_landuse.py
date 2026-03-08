"""
拉取徐家汇 OSM 用地数据
======================
用法: python fetch_landuse.py

从 OpenStreetMap 拉取 landuse/leisure/natural 多边形，
保存至 landuse_data/landuse_xujiahui.geojson 和 landuse_data/landuse_centroid.csv。
"""

from analysis.landuse.fetcher import run_fetch

if __name__ == "__main__":
    geojson_p, csv_p = run_fetch()
    print(f"GeoJSON: {geojson_p}")
    print(f"Centroid CSV: {csv_p}")
