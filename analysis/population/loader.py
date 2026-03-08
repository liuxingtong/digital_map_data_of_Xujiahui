"""
人口栅格加载器
==============
使用 rasterio 加载裁剪后的徐家汇人口 TIF。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    pass

try:
    import rasterio
    from rasterio.transform import xy
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False


# 人口文件配置：输出文件名 -> 显示名
POPULATION_FILES = {
    "population_age65above": "65岁以上",
    "population_age0_14": "0-14岁",
    "population_age15_59": "15-59岁",
    "population_age60_64": "60-64岁",
    "population_total_pop": "总人口",
}


def load_population_raster(
    tif_path: str | Path,
) -> tuple[np.ndarray, tuple[float, float, float, float], float | None] | tuple[None, None, None]:
    """
    加载人口栅格数据。

    Args:
        tif_path: 裁剪后的 TIF 路径（如 population_xujiahui.tif）

    Returns:
        (data, bounds, nodata) 或 (None, None, None)
        - data: 2D numpy 数组，单位 100m 格网的 65+ 人口数
        - bounds: (lon_min, lon_max, lat_min, lat_max)
        - nodata: 无数据值
    """
    if not HAS_RASTERIO:
        return None, None, None

    path = Path(tif_path)
    if not path.exists():
        return None, None, None

    with rasterio.open(path) as src:
        data = src.read(1)
        nodata = src.nodata
        bounds = src.bounds
        # rasterio bounds: (left, bottom, right, top)
        lon_min, lat_min, lon_max, lat_max = bounds.left, bounds.bottom, bounds.right, bounds.top

    return data, (lon_min, lon_max, lat_min, lat_max), nodata


def get_population_stats(
    data: np.ndarray,
    nodata: float | None,
) -> dict[str, float]:
    """计算人口栅格基本统计量"""
    arr = data.astype(float)
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return {"count": 0, "sum": 0, "mean": 0, "max": 0}
    return {
        "count": int((valid > 0).sum()),
        "sum": float(valid.sum()),
        "mean": float(valid.mean()),
        "max": float(valid.max()),
    }


def raster_to_dataframe(
    tif_path: str | Path,
    value_col: str = "population",
    subsample: int | None = None,
) -> pd.DataFrame | None:
    """
    将人口栅格转为 DataFrame（lon, lat, value_col），供 KDE/等值线等分析使用。

    Args:
        tif_path: TIF 路径
        value_col: 数值列名
        subsample: 若指定，每隔 N 个格网采样以加速（如 2 表示 1/4 点）

    Returns:
        DataFrame 含 lon, lat, value_col
    """
    if not HAS_RASTERIO:
        return None

    path = Path(tif_path)
    if not path.exists():
        return None

    with rasterio.open(path) as src:
        data = src.read(1)
        transform = src.transform
        nodata = src.nodata

    rows, cols = data.shape
    lons, lats, vals = [], [], []

    step = subsample if subsample and subsample > 1 else 1
    for r in range(0, rows, step):
        for c in range(0, cols, step):
            v = float(data[r, c])
            if nodata is not None and v == nodata:
                continue
            if v <= 0:
                continue
            lon, lat = xy(transform, r, c)
            lons.append(lon)
            lats.append(lat)
            vals.append(v)

    if not lons:
        return None
    return pd.DataFrame({"lon": lons, "lat": lats, value_col: vals})


def load_combined_population(
    population_dir: str | Path,
    subsample: int | None = 2,
) -> pd.DataFrame | None:
    """
    加载并合并多个人口栅格为 DataFrame，含各年龄段列。
    用于人口雷达图（点选时展示各年龄段分布）。

    Returns:
        DataFrame 含 lon, lat, age0_14, age15_59, age60_64, age65above, total_pop
        若某文件不存在则对应列为 NaN
    """
    if not HAS_RASTERIO:
        return None

    base = Path(population_dir)
    col_map = {
        "population_age0_14": "age0_14",
        "population_age15_59": "age15_59",
        "population_age60_64": "age60_64",
        "population_age65above": "age65above",
        "population_total_pop": "total_pop",
    }

    merged: pd.DataFrame | None = None
    for fname, col in col_map.items():
        path = base / f"{fname}.tif"
        if not path.exists():
            continue
        df = raster_to_dataframe(path, value_col=col, subsample=subsample)
        if df is None or len(df) == 0:
            continue
        if merged is None:
            merged = df
        else:
            merged = merged.merge(
                df[["lon", "lat", col]],
                on=["lon", "lat"],
                how="outer",
            )

    return merged
