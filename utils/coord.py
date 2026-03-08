"""
坐标系转换
==========
- 存储坐标系: WGS84 (EPSG:4326)
- 分析坐标系: UTM Zone 51N (EPSG:32651)，用于面积、距离（米）
- 高德 POI: GCJ-02 → 需转 WGS84
"""

from __future__ import annotations

import math
from typing import Tuple

# CRS 常量
STORAGE_CRS = "EPSG:4326"   # WGS84，存储与展示
ANALYSIS_CRS = "EPSG:32651"  # UTM Zone 51N，上海所在带，分析用（米）


# --- GCJ-02 ↔ WGS84（无外部依赖）---
_x_pi = 3.14159265358979324 * 3000.0 / 180.0
_pi = 3.1415926535897932384626
_a = 6378245.0
_ee = 0.00669342162296594323


def _transformlat(lng: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat
    ret += 0.1 * lng * lat + 0.2 * math.sqrt(max(0, lng))
    ret += (20.0 * math.sin(6.0 * lng * _pi) + 20.0 * math.sin(2.0 * lng * _pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * _pi) + 40.0 * math.sin(lat / 3.0 * _pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * _pi) + 320 * math.sin(lat * _pi / 30.0)) * 2.0 / 3.0
    return ret


def _transformlng(lng: float, lat: float) -> float:
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng
    ret += 0.1 * lng * lat + 0.1 * math.sqrt(max(0, lng))
    ret += (20.0 * math.sin(6.0 * lng * _pi) + 20.0 * math.sin(2.0 * lng * _pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * _pi) + 40.0 * math.sin(lng / 3.0 * _pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * _pi) + 300.0 * math.sin(lng / 30.0 * _pi)) * 2.0 / 3.0
    return ret


def _out_of_china(lng: float, lat: float) -> bool:
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)


def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    高德/腾讯 GCJ-02 → WGS84。
    高德 POI 的 lng/lat 为 GCJ-02，加载后应调用此函数转 WGS84。
    """
    if _out_of_china(lng, lat):
        return (lng, lat)
    dlat = _transformlat(lng - 105.0, lat - 35.0)
    dlng = _transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * _pi
    magic = math.sin(radlat)
    magic = 1 - _ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_a * (1 - _ee)) / (magic * sqrtmagic) * _pi)
    dlng = (dlng * 180.0) / (_a / sqrtmagic * math.cos(radlat) * _pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return (lng * 2 - mglng, lat * 2 - mglat)


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """WGS84 → GCJ-02（如需回传高德 API 时用）"""
    if _out_of_china(lng, lat):
        return (lng, lat)
    dlat = _transformlat(lng - 105.0, lat - 35.0)
    dlng = _transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * _pi
    magic = math.sin(radlat)
    magic = 1 - _ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_a * (1 - _ee)) / (magic * sqrtmagic) * _pi)
    dlng = (dlng * 180.0) / (_a / sqrtmagic * math.cos(radlat) * _pi)
    return (lng + dlng, lat + dlat)


# --- UTM Zone 51N（需 pyproj）---
def transform_to_utm(lon: float, lat: float) -> Tuple[float, float]:
    """
    WGS84 (lon, lat) → UTM Zone 51N (x, y) 米。
    用于距离、面积等分析。
    """
    try:
        from pyproj import Transformer
        t = Transformer.from_crs(STORAGE_CRS, ANALYSIS_CRS, always_xy=True)
        x, y = t.transform(lon, lat)
        return (float(x), float(y))
    except ImportError:
        return (lon, lat)  # 无 pyproj 时原样返回


def transform_to_wgs84(x: float, y: float) -> Tuple[float, float]:
    """UTM Zone 51N (x, y) 米 → WGS84 (lon, lat)。"""
    try:
        from pyproj import Transformer
        t = Transformer.from_crs(ANALYSIS_CRS, STORAGE_CRS, always_xy=True)
        lon, lat = t.transform(x, y)
        return (float(lon), float(lat))
    except ImportError:
        return (x, y)


def haversine_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    两 WGS84 点间距离（米），近似公式。
    精确分析请用 transform_to_utm 后算欧氏距离。
    """
    R = 6371000  # 地球半径 m
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
