"""
POI 分布模块
============
徐家汇 POI 数据的加载与地图叠加。
数据来源：poi_data 文件夹下的高德 POI CSV。
低耦合设计，可独立使用。
"""

from .loader import (
    load_poi_data,
    get_poi_stats,
    prepare_poi_for_viz,
    aggregate_poi_by_category_near,
    POI_FILES,
)
from .overlay import create_poi_map, add_poi_overlay, XUJIAHUI_BOUNDS

__all__ = [
    "load_poi_data",
    "get_poi_stats",
    "prepare_poi_for_viz",
    "aggregate_poi_by_category_near",
    "POI_FILES",
    "create_poi_map",
    "add_poi_overlay",
    "XUJIAHUI_BOUNDS",
]
