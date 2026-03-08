"""
POI 数据加载器
==============
从 poi_data 文件夹加载高德 POI CSV 数据。
高德 POI 坐标为 GCJ-02，加载时自动纠偏为 WGS84（存储坐标系）。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    pass


# POI 文件配置：文件名（不含路径）-> 显示名
# 支持 CSV（高德格式）和 Excel（如 coffee.xlsx）
POI_FILES = {
    "coffee.xlsx": "咖啡店",
    "poi_all.csv": "全部 POI",
    "poi_交通设施.csv": "交通设施",
    "poi_文化地标.csv": "文化地标",
    "poi_医疗保健.csv": "医疗保健",
    "poi_体育休闲.csv": "体育休闲",
    "poi_风景名胜.csv": "风景名胜",
    "poi_购物菜场.csv": "购物菜场",
    "poi_生活服务.csv": "生活服务",
    "poi_社交餐饮.csv": "社交餐饮",
    "poi_金融住宿政府.csv": "金融住宿政府",
    "poi_商务产业.csv": "商务产业",
    "poi_银发极客_科技体验.csv": "银发极客/科技体验",
    "poi_独处品质空间.csv": "独处品质空间",
}


def _read_poi_file(path: Path) -> pd.DataFrame | None:
    """读取 POI 文件（CSV 或 Excel），返回原始 DataFrame。"""
    suffix = path.suffix.lower()
    if suffix == ".xlsx" or suffix == ".xls":
        try:
            return pd.read_excel(path)
        except Exception:
            return None
    # CSV
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="gbk")


def _normalize_poi_coords(
    df: pd.DataFrame,
    convert_gcj02_to_wgs84: bool = True,
) -> pd.DataFrame | None:
    """
    统一坐标列为 lng/lat/lon，并做 GCJ→WGS84 纠偏（如需要）。
    支持列名：lng/lat、gcj_lng/gcj_lat、wgs84Lng/wgs84Lat。
    """
    lon_col = lat_col = None
    already_wgs84 = False

    if "wgs84Lng" in df.columns and "wgs84Lat" in df.columns:
        lon_col, lat_col = "wgs84Lng", "wgs84Lat"
        already_wgs84 = True
    elif "gcj_lng" in df.columns and "gcj_lat" in df.columns:
        lon_col, lat_col = "gcj_lng", "gcj_lat"
    elif "lng" in df.columns and "lat" in df.columns:
        lon_col, lat_col = "lng", "lat"

    if lon_col is None or lat_col is None:
        return None

    df = df.copy()
    df["lng"] = pd.to_numeric(df[lon_col], errors="coerce")
    df["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    df = df.dropna(subset=["lng", "lat"])

    if already_wgs84:
        df["lon"] = df["lng"]
    elif convert_gcj02_to_wgs84:
        from utils.coord import gcj02_to_wgs84
        wgs = df.apply(lambda r: gcj02_to_wgs84(r["lng"], r["lat"]), axis=1)
        df["lon"] = [p[0] for p in wgs]
        df["lat"] = [p[1] for p in wgs]
        df["lng"] = df["lon"]
    else:
        df["lon"] = df["lng"]

    return df


def load_poi_data(
    csv_path: str | Path,
    bounds: tuple[float, float, float, float] | None = None,
    convert_gcj02_to_wgs84: bool = True,
) -> pd.DataFrame | None:
    """
    加载 POI 数据（支持 CSV 和 Excel）。

    Args:
        csv_path: 文件路径（.csv 或 .xlsx）
        bounds: 可选 (lon_min, lon_max, lat_min, lat_max)，裁剪到徐家汇范围
        convert_gcj02_to_wgs84: 高德 POI 为 GCJ-02 时转为 WGS84；Excel 若含 wgs84Lng/wgs84Lat 则跳过

    Returns:
        DataFrame 含 id, name, type, lng, lat, lon, address, group, rating 等
        坐标统一为 WGS84（与街景/人口/路网一致）
    """
    path = Path(csv_path)
    if not path.exists():
        return None

    df = _read_poi_file(path)
    if df is None or df.empty:
        return None

    df = _normalize_poi_coords(df, convert_gcj02_to_wgs84=convert_gcj02_to_wgs84)
    if df is None or df.empty:
        return None

    if bounds is not None:
        lon_min, lon_max, lat_min, lat_max = bounds
        df = df[
            (df["lon"] >= lon_min)
            & (df["lon"] <= lon_max)
            & (df["lat"] >= lat_min)
            & (df["lat"] <= lat_max)
        ]

    return df.reset_index(drop=True)


def get_poi_stats(df: pd.DataFrame) -> dict:
    """计算 POI 基本统计量"""
    if df is None or len(df) == 0:
        return {"count": 0, "groups": [], "with_rating": 0}
    groups = []
    if "group" in df.columns:
        groups = df["group"].dropna().unique().tolist()
    with_rating = 0
    if "rating" in df.columns:
        with_rating = int(df["rating"].notna().sum())
    return {
        "count": len(df),
        "groups": groups[:10],
        "with_rating": with_rating,
    }


def prepare_poi_for_viz(df: pd.DataFrame) -> pd.DataFrame:
    """
    为高阶可视化准备 POI 数据：添加 rating_numeric、density、category 列。

    - rating_numeric: 数值型评分，缺失填 0
    - density: 恒为 1，用于 KDE 密度估计
    - category: 从 type 提取（取最后一段，如 博物馆、地铁站）
    """
    if df is None or len(df) == 0:
        return df
    out = df.copy()
    if "rating" in out.columns:
        out["rating_numeric"] = pd.to_numeric(out["rating"], errors="coerce").fillna(0)
    else:
        out["rating_numeric"] = 0.0
    out["density"] = 1.0
    if "type" in out.columns:
        out["category"] = out["type"].apply(
            lambda x: str(x).split(";")[-1].strip() if pd.notna(x) and ";" in str(x) else str(x) if pd.notna(x) else ""
        )
    return out


def aggregate_poi_by_category_near(
    df: pd.DataFrame,
    lat: float,
    lon: float,
    radius_km: float = 0.5,
) -> dict[str, float]:
    """
    统计指定点附近各 category 的 POI 数量，供雷达图使用。
    使用 haversine 距离（米），坐标需为 WGS84。

    Args:
        df: 含 lat, lon, category 的 POI DataFrame（需先 prepare_poi_for_viz）
        lat, lon: 中心点坐标 (WGS84)
        radius_km: 半径（公里）

    Returns:
        {category: count, ...}
    """
    if df is None or len(df) == 0 or "category" not in df.columns:
        return {}

    from utils.coord import haversine_meters

    lon_col = "lon" if "lon" in df.columns else "lng"
    radius_m = radius_km * 1000
    # 粗筛减少 haversine 计算量
    lat_deg = radius_km / 111.0
    lon_deg = radius_km / (111.0 * max(0.1, abs(math.cos(math.radians(lat)))))
    rough = df[
        (df["lat"] >= lat - lat_deg) & (df["lat"] <= lat + lat_deg)
        & (df[lon_col] >= lon - lon_deg) & (df[lon_col] <= lon + lon_deg)
    ]
    if len(rough) == 0:
        return {}
    dists = rough.apply(
        lambda r: haversine_meters(lon, lat, r[lon_col], r["lat"]),
        axis=1,
    )
    nearby = rough.loc[dists <= radius_m]
    if len(nearby) == 0:
        return {}
    return nearby["category"].value_counts().to_dict()
