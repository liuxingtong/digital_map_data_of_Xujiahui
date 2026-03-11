"""
CLD 系统动力学（SD）仿真模块
============================
按 CLD_SD_可行性说明.md 实现。
"""

from .simulator import (
    SDInitialValues,
    DEFAULT_PARAMS,
    aggregate_from_priority_df,
    run_sd_simulation,
    run_sd_scenarios,
)

__all__ = [
    "SDInitialValues",
    "DEFAULT_PARAMS",
    "aggregate_from_priority_df",
    "run_sd_simulation",
    "run_sd_scenarios",
]
