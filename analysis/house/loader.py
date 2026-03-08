"""
房价/小区数据加载器
==================
从 house_data 文件夹加载小区 Excel 数据。
坐标：POINT_X/POINT_Y 为 WGS84，直接使用。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    pass

# 徐家汇边界 (lon_min, lon_max, lat_min, lat_max)
XUJIAHUI_BOUNDS = (121.37, 121.48, 31.12, 31.23)

HOUSE_FILES = {
    "house_total.xlsx": "小区房价",
}

# 列位置映射（兼容中文列名编码差异）
# 0:FID, 1:?, 2:name, 3:address, 4:物业类型, 5:总建面, 6:?, 7:容积率, 8:绿化率, 9:竣工时, 10:lon_bd, 11:lat_bd, 12:POINT_X, 13:POINT_Y, 14:小区均价
COL_NAME = 2
COL_ADDRESS = 3
COL_PLOT_RATIO = 7
COL_GREENING_RATE = 8
COL_COMPLETION = 9
COL_LON = 12
COL_LAT = 13
COL_UNIT_PRICE = 14


def load_house_data(
    path: str | Path,
    bounds: tuple[float, float, float, float] | None = None,
    convert_gcj02_to_wgs84: bool = False,
) -> pd.DataFrame | None:
    """
    加载小区房价数据。

    Args:
        path: Excel 文件路径
        bounds: 可选 (lon_min, lon_max, lat_min, lat_max)，裁剪到徐家汇范围
        convert_gcj02_to_wgs84: 若数据来源为高德/GCJ-02，设为 True 转为 WGS84

    Returns:
        DataFrame 含 name, address, lon, lat, plot_ratio, greening_rate,
        completion_year, unit_price 等，坐标统一为 WGS84
    """
    p = Path(path)
    if not p.exists():
        return None

    try:
        df = pd.read_excel(p)
    except Exception:
        return None

    if df.empty or len(df.columns) <= max(COL_LON, COL_LAT, COL_UNIT_PRICE):
        return None

    out = pd.DataFrame()
    out["name"] = df.iloc[:, COL_NAME].astype(str)
    out["address"] = df.iloc[:, COL_ADDRESS].astype(str) if COL_ADDRESS < len(df.columns) else ""
    lon_raw = pd.to_numeric(df.iloc[:, COL_LON], errors="coerce")
    lat_raw = pd.to_numeric(df.iloc[:, COL_LAT], errors="coerce")
    if convert_gcj02_to_wgs84:
        from utils.coord import gcj02_to_wgs84
        wgs = df.apply(
            lambda r: gcj02_to_wgs84(lon_raw[r.name], lat_raw[r.name])
            if pd.notna(lon_raw[r.name]) and pd.notna(lat_raw[r.name]) else (float("nan"), float("nan")),
            axis=1,
        )
        out["lon"] = [p[0] for p in wgs]
        out["lat"] = [p[1] for p in wgs]
    else:
        out["lon"] = lon_raw.values
        out["lat"] = lat_raw.values
    out["plot_ratio"] = pd.to_numeric(df.iloc[:, COL_PLOT_RATIO], errors="coerce")
    out["greening_rate"] = pd.to_numeric(df.iloc[:, COL_GREENING_RATE], errors="coerce")
    out["completion_year"] = _extract_year(df.iloc[:, COL_COMPLETION])
    out["unit_price"] = pd.to_numeric(df.iloc[:, COL_UNIT_PRICE], errors="coerce")

    out = out.dropna(subset=["lon", "lat"])

    if bounds is not None:
        lon_min, lon_max, lat_min, lat_max = bounds
        out = out[
            (out["lon"] >= lon_min)
            & (out["lon"] <= lon_max)
            & (out["lat"] >= lat_min)
            & (out["lat"] <= lat_max)
        ]

    return out.reset_index(drop=True)


def _extract_year(series: pd.Series) -> pd.Series:
    """从「2010年」「1994」等字符串提取年份。"""
    def _one(x):
        if pd.isna(x):
            return pd.NA
        s = str(x).strip()
        m = re.search(r"(\d{4})", s)
        return int(m.group(1)) if m else pd.NA
    return series.apply(_one)


def get_house_stats(df: pd.DataFrame) -> dict:
    """计算小区数据基本统计量"""
    if df is None or len(df) == 0:
        return {"count": 0, "with_price": 0, "price_mean": 0, "price_median": 0}

    with_price = int(df["unit_price"].notna().sum()) if "unit_price" in df.columns else 0
    price_mean = float(df["unit_price"].mean()) if with_price else 0
    price_median = float(df["unit_price"].median()) if with_price else 0

    return {
        "count": len(df),
        "with_price": with_price,
        "price_mean": price_mean,
        "price_median": price_median,
    }


def prepare_house_for_viz(df: pd.DataFrame) -> pd.DataFrame:
    """
    为高阶可视化准备小区数据：确保数值列存在，density 恒为 1。
    """
    if df is None or len(df) == 0:
        return df
    out = df.copy()
    for col in ["plot_ratio", "greening_rate", "completion_year", "unit_price"]:
        if col not in out.columns:
            out[col] = pd.NA
        else:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["density"] = 1.0
    return out
