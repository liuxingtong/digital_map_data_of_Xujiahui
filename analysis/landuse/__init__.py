"""
OSM 用地数据模块
================
数据来源：OpenStreetMap (osmnx features_from_bbox)
坐标：WGS84，无需纠偏。
"""

from .loader import (
    load_landuse,
    load_landuse_geojson,
    load_landuse_centroid,
    prepare_landuse_for_viz,
    get_landuse_stats,
    LANDUSE_LABELS,
    XUJIAHUI_BOUNDS,
)
from .overlay import create_landuse_map
from .fetcher import fetch_landuse, run_fetch, save_landuse

__all__ = [
    "load_landuse",
    "load_landuse_geojson",
    "load_landuse_centroid",
    "prepare_landuse_for_viz",
    "get_landuse_stats",
    "create_landuse_map",
    "fetch_landuse",
    "run_fetch",
    "save_landuse",
    "LANDUSE_LABELS",
    "XUJIAHUI_BOUNDS",
]
