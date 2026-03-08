# 坐标系与坐标纠偏规范

## 存储坐标系

- **WGS84 (EPSG:4326)**：所有存储数据统一使用 WGS84 经纬度。
- 街景、人口、路网、POI、房价等模块的输入/输出均以 WGS84 为准。

## 分析坐标系

- **UTM Zone 51N (EPSG:32651)**：用于面积、距离（米）等需要物理单位的分析。
- 通过 `utils.coord` 中的 `transform_to_utm` / `transform_to_wgs84` 进行转换。

## 数据源与纠偏

| 数据源 | 原始坐标系 | 处理 |
|--------|------------|------|
| 街景 (OSM/merged.csv) | WGS84 | 无需转换 |
| 人口 (rasterio) | WGS84 | 无需转换 |
| 路网 (OSMnx) | WGS84 | 无需转换 |
| POI (高德 CSV) | GCJ-02 | 加载时 `gcj02_to_wgs84` 转为 WGS84 |
| POI (coffee.xlsx 等含 wgs84Lng/wgs84Lat) | WGS84 | 直接使用 |
| 房价 (house_total.xlsx) | POINT_X/POINT_Y 通常为 WGS84 | 若来源为高德/GCJ，设置 `convert_gcj02_to_wgs84=True` |
| 用地 (OSM landuse) | WGS84 | 无需转换 |

## 距离计算

- 使用 `haversine_meters(lon1, lat1, lon2, lat2)` 计算 WGS84 两点球面距离（米）。
- 粗筛可用经纬度 bounding box 减少计算量，再对候选点用 haversine 精确过滤。
