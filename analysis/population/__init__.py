"""
人口分布模块
============
徐家汇人口栅格数据的加载、地图叠加与高阶可视化。
支持多年龄段：0-14、15-59、60-64、65+、总人口。
低耦合设计，可独立使用。
"""

from .loader import (
    load_population_raster,
    get_population_stats,
    raster_to_dataframe,
    load_combined_population,
    POPULATION_FILES,
)
from .overlay import create_population_map, add_population_overlay

__all__ = [
    "load_population_raster",
    "get_population_stats",
    "raster_to_dataframe",
    "load_combined_population",
    "POPULATION_FILES",
    "create_population_map",
    "add_population_overlay",
]
