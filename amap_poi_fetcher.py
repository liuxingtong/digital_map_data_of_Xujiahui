# -*- coding: utf-8 -*-
"""
徐家汇适老化改造 · 高德POI数据采集脚本
=======================================
功能：按CLD节点需求分组拉取高德POI，存储为本地GeoJSON + CSV
防乱码：全程UTF-8编码，JSON解析使用ensure_ascii=False

使用前：
1. 在高德开放平台注册，创建Web服务类型的Key
2. 将Key填入下方 AMAP_KEY 变量
3. pip install requests pandas （如未安装）
4. python amap_poi_fetcher.py

输出文件（保存在 ./poi_data/ 目录下）：
  - poi_all.geojson          全量数据，GeoJSON格式
  - poi_all.csv              全量数据，CSV格式
  - poi_{分组名}.csv         按CLD节点分组的子集
  - fetch_log.txt            采集日志
"""

import os
import json
import time
import csv
import sys
import requests
from datetime import datetime
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
# 配置区 —— 请修改以下参数
# ═══════════════════════════════════════════════════════════════

AMAP_KEY = "d3e53380b5074ad86ff2f2fe67f3e5c1"  # ← 替换为你的高德Web服务Key

# 搜索范围：徐汇区徐家汇街道及周边，覆盖完整研究区 + 约 1.5km 缓冲区
# 用 polygon 定义搜索范围（经度,纬度 格式，多边形顶点，首尾闭合）
# 与 XUJIAHUI_BOUNDS (121.37, 121.48, 31.12, 31.23) 对齐并外扩
SEARCH_POLYGON = (
    "121.3550,31.1050|"  # 西南角
    "121.4950,31.1050|"  # 东南角
    "121.4950,31.2450|"  # 东北角
    "121.3550,31.2450"   # 西北角
)

# 备选方案：用中心点+半径搜索（二选一，取消注释即可切换）
# SEARCH_CENTER = "121.4437,31.1955"  # 徐家汇中心经纬度
# SEARCH_RADIUS = 2000                 # 半径（米），最大50000

# 请求间隔（秒），防限流
REQUEST_DELAY = 0.25

# 每页条数（高德最大25）
PAGE_SIZE = 25

# 输出目录
OUTPUT_DIR = "./poi_data"

# ═══════════════════════════════════════════════════════════════
# POI分类定义 —— 按CLD节点需求分组
# ═══════════════════════════════════════════════════════════════

# 高德POI分类代码参考：https://lbs.amap.com/api/webservice/download
# 格式：{ "分组名": { "codes": [分类代码], "keywords": [关键词补充搜索], "feeds": "喂入的CLD节点" } }

POI_GROUPS = {
    "社交餐饮": {
        "codes": [
            "050100",  # 中餐厅
            "050200",  # 外国餐厅
            "050300",  # 快餐厅
            "050400",  # 休闲餐饮（咖啡厅、茶馆、甜品店）
            "050500",  # 糕饼店
            "050700",  # 小吃店
            "050800",  # 冷饮店
        ],
        "keywords": [],
        "feeds": "N01 社交场所密度",
    },
    "购物菜场": {
        "codes": [
            "060100",  # 综合商场/购物中心
            "060200",  # 便民商店/便利店
            "060300",  # 家电电子卖场
            "060400",  # 超级市场
            "060700",  # 花鸟鱼虫市场
            "060900",  # 综合市场（含菜场/农贸市场）
        ],
        "keywords": ["菜场", "农贸市场", "早市"],
        "feeds": "N01 社交场所密度 + N05 Shannon熵",
    },
    "生活服务": {
        "codes": [
            "070200",  # 邮局
            "070400",  # 物流速递
            "070700",  # 家政服务
            "071000",  # 社区服务中心
            "071200",  # 福利院/养老院
            "073000",  # 老年活动中心（自定义补充）
        ],
        "keywords": ["社区服务", "老年活动", "棋牌室", "居委会", "街道办"],
        "feeds": "N01 社交场所密度",
    },
    "文化地标": {
        "codes": [
            "140100",  # 学校（大学/中学/小学）
            "140200",  # 科研机构
            "140300",  # 图书馆
            "140400",  # 科技馆
            "140500",  # 博物馆
            "140600",  # 美术馆/展览馆
            "140700",  # 会展中心
            "140800",  # 文化宫
            "141000",  # 剧院/音乐厅
        ],
        "keywords": ["纪念馆", "文化中心", "书店", "画廊", "剧场"],
        "feeds": "N14 空间认知复杂度指数",
    },
    "风景名胜": {
        "codes": [
            "110100",  # 公园广场
            "110200",  # 风景名胜
            "110201",  # 国家级景点
            "110202",  # 省级景点
            "110203",  # 其他景点
            "110204",  # 教堂
            "110205",  # 寺庙道观
        ],
        "keywords": ["纪念碑", "历史建筑", "名人故居", "文物保护"],
        "feeds": "N14 空间认知复杂度指数",
    },
    "医疗保健": {
        "codes": [
            "090100",  # 综合医院
            "090200",  # 专科医院
            "090300",  # 社区卫生服务中心/站
            "090400",  # 诊所
            "090500",  # 急救中心
            "090600",  # 疾控中心
            "090700",  # 药店
        ],
        "keywords": [],
        "feeds": "N01 社交场所密度（高频目的地）",
    },
    "体育休闲": {
        "codes": [
            "080100",  # 体育场馆
            "080200",  # 极限运动
            "080300",  # 健身中心
            "080400",  # 高尔夫
            "080500",  # 休闲场所
            "080600",  # 影剧院
        ],
        "keywords": ["健身步道", "运动公园", "广场舞", "太极"],
        "feeds": "N01 + N09 街道舒适度（运动设施）",
    },
    "交通设施": {
        "codes": [
            "150100",  # 飞机场（通常不在范围内，保留完整性）
            "150200",  # 火车站
            "150300",  # 汽车站
            "150400",  # 地铁站
            "150500",  # 轻轨站
            "150600",  # 码头
            "150700",  # 公交车站
            "150900",  # 停车场
        ],
        "keywords": [],
        "feeds": "N04 路网连通性（交通接驳补充）",
    },
    "金融住宿政府": {
        "codes": [
            "100000",  # 金融保险
            "120000",  # 住宿服务
            "130000",  # 政府机构
        ],
        "keywords": [],
        "feeds": "N05 土地混合度（Shannon熵全品类覆盖）",
    },
    "商务产业": {
        "codes": [
            "120000",  # 商务住宅（含写字楼、产业园区）
        ],
        "keywords": [],
        "feeds": "N05 土地混合度",
    },
    "科技体验": {
        "codes": [
            "140400",  # 科技馆
            "140200",  # 科研机构
            "140500",  # 博物馆（科技类）
        ],
        "keywords": [
            "科技馆", "科创中心", "创客空间", "科技体验",
            "人工智能", "AI中心", "科技园", "体验馆",
            "VR体验", "创新中心", "孵化器", "联合办公",
            "钱学森", "科学会堂",
        ],
        "feeds": "N01 银发极客磁力点 → R5",
    },
    "独处品质空间": {
        "codes": [],
        "keywords": [
            "书店", "独立书店", "咖啡馆", "茶室", "画廊",
            "美术馆", "寺庙", "教堂", "街心花园", "口袋公园",
        ],
        "feeds": "N08 街道舒适度（安静节点标注）",
    },
}


# ═══════════════════════════════════════════════════════════════
# 核心采集函数
# ═══════════════════════════════════════════════════════════════

def log(msg, log_file=None):
    """打印并写入日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if log_file:
        log_file.write(line + "\n")
        log_file.flush()


def fetch_by_code(type_code, page=1):
    """按分类代码搜索"""
    params = {
        "key": AMAP_KEY,
        "polygon": SEARCH_POLYGON,
        "types": type_code,
        "offset": PAGE_SIZE,
        "page": page,
        "output": "json",
        "extensions": "all",  # 获取详细信息
    }
    resp = requests.get(
        "https://restapi.amap.com/v3/place/polygon",
        params=params,
        timeout=15,
    )
    resp.encoding = "utf-8"  # 强制UTF-8，防乱码
    return resp.json()


def fetch_by_keyword(keyword, page=1):
    """按关键词搜索"""
    params = {
        "key": AMAP_KEY,
        "polygon": SEARCH_POLYGON,
        "keywords": keyword,
        "offset": PAGE_SIZE,
        "page": page,
        "output": "json",
        "extensions": "all",
    }
    resp = requests.get(
        "https://restapi.amap.com/v3/place/polygon",
        params=params,
        timeout=15,
    )
    resp.encoding = "utf-8"
    return resp.json()


def parse_poi(raw, group_name):
    """解析单条POI，统一字段"""
    location = raw.get("location", "")
    lng, lat = "", ""
    if location and "," in location:
        lng, lat = location.split(",")

    return {
        "id": raw.get("id", ""),
        "name": raw.get("name", ""),
        "type": raw.get("type", ""),
        "typecode": raw.get("typecode", ""),
        "address": raw.get("address", "") if isinstance(raw.get("address"), str) else "",
        "lng": lng,
        "lat": lat,
        "tel": raw.get("tel", "") if isinstance(raw.get("tel"), str) else "",
        "rating": raw.get("biz_ext", {}).get("rating", "") if isinstance(raw.get("biz_ext"), dict) else "",
        "cost": raw.get("biz_ext", {}).get("cost", "") if isinstance(raw.get("biz_ext"), dict) else "",
        "group": group_name,
        "pname": raw.get("pname", ""),
        "cityname": raw.get("cityname", ""),
        "adname": raw.get("adname", ""),
    }


def fetch_all_for_code(type_code, group_name, log_file):
    """拉取某个分类代码的全部分页数据"""
    results = []
    page = 1
    while True:
        try:
            data = fetch_by_code(type_code, page)
        except Exception as e:
            log(f"  ⚠ 请求异常 code={type_code} page={page}: {e}", log_file)
            break

        if data.get("status") != "1":
            info = data.get("info", "unknown")
            log(f"  ⚠ API返回异常 code={type_code}: {info}", log_file)
            break

        pois = data.get("pois", [])
        if not pois:
            break

        for raw in pois:
            results.append(parse_poi(raw, group_name))

        total = int(data.get("count", 0))
        fetched = page * PAGE_SIZE
        if fetched >= total:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return results


def fetch_all_for_keyword(keyword, group_name, log_file):
    """拉取某个关键词的全部分页数据"""
    results = []
    page = 1
    while True:
        try:
            data = fetch_by_keyword(keyword, page)
        except Exception as e:
            log(f"  ⚠ 请求异常 kw={keyword} page={page}: {e}", log_file)
            break

        if data.get("status") != "1":
            info = data.get("info", "unknown")
            log(f"  ⚠ API返回异常 kw={keyword}: {info}", log_file)
            break

        pois = data.get("pois", [])
        if not pois:
            break

        for raw in pois:
            results.append(parse_poi(raw, group_name))

        total = int(data.get("count", 0))
        fetched = page * PAGE_SIZE
        if fetched >= total:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return results


# ═══════════════════════════════════════════════════════════════
# 去重 + 导出
# ═══════════════════════════════════════════════════════════════

def deduplicate(all_pois):
    """按POI ID去重，保留首次出现的分组标签，多次出现的合并分组名"""
    seen = {}
    for poi in all_pois:
        pid = poi["id"]
        if pid in seen:
            existing_groups = seen[pid]["group"].split("|")
            if poi["group"] not in existing_groups:
                seen[pid]["group"] += "|" + poi["group"]
        else:
            seen[pid] = poi.copy()
    return list(seen.values())


def to_geojson(pois):
    """转换为GeoJSON FeatureCollection"""
    features = []
    for poi in pois:
        if not poi["lng"] or not poi["lat"]:
            continue
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(poi["lng"]), float(poi["lat"])],
            },
            "properties": {
                k: v for k, v in poi.items() if k not in ("lng", "lat")
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "高德地图POI",
            "fetch_time": datetime.now().isoformat(),
            "area": "上海市徐汇区徐家汇及周边（含约1.5km缓冲区）",
            "total": len(features),
        },
        "features": features,
    }


def save_csv(pois, filepath):
    """保存为CSV，UTF-8 with BOM（Excel友好）"""
    if not pois:
        return
    fieldnames = [
        "id", "name", "type", "typecode", "address",
        "lng", "lat", "tel", "rating", "cost",
        "group", "pname", "cityname", "adname",
    ]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(pois)


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def main():
    # 检查Key
    if AMAP_KEY == "YOUR_AMAP_KEY_HERE":
        print("=" * 60)
        print("错误：请先在脚本顶部填入你的高德Web服务Key")
        print("注册地址：https://console.amap.com/dev/key/app")
        print("=" * 60)
        sys.exit(1)

    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "fetch_log.txt")
    log_file = open(log_path, "w", encoding="utf-8")

    log("=" * 60, log_file)
    log("徐家汇适老化改造 · 高德POI数据采集", log_file)
    log(f"采集时间：{datetime.now().isoformat()}", log_file)
    log(f"搜索范围：{SEARCH_POLYGON[:60]}...", log_file)
    log("=" * 60, log_file)

    all_pois = []
    group_stats = defaultdict(int)
    total_requests = 0

    for group_name, config in POI_GROUPS.items():
        log(f"\n━━ 分组：{group_name} ━━", log_file)
        log(f"   喂入节点：{config['feeds']}", log_file)
        group_pois = []

        # 按分类代码拉取
        for code in config.get("codes", []):
            log(f"   分类代码 {code} ...", log_file)
            pois = fetch_all_for_code(code, group_name, log_file)
            group_pois.extend(pois)
            total_requests += max(1, len(pois) // PAGE_SIZE + 1)
            log(f"   → {len(pois)} 条", log_file)
            time.sleep(REQUEST_DELAY)

        # 按关键词补充拉取
        for kw in config.get("keywords", []):
            log(f"   关键词 「{kw}」 ...", log_file)
            pois = fetch_all_for_keyword(kw, group_name, log_file)
            group_pois.extend(pois)
            total_requests += max(1, len(pois) // PAGE_SIZE + 1)
            log(f"   → {len(pois)} 条", log_file)
            time.sleep(REQUEST_DELAY)

        group_stats[group_name] = len(group_pois)
        all_pois.extend(group_pois)
        log(f"   小计（去重前）：{len(group_pois)} 条", log_file)

    # 全局去重
    log(f"\n去重前总计：{len(all_pois)} 条", log_file)
    deduped = deduplicate(all_pois)
    log(f"去重后总计：{len(deduped)} 条", log_file)

    # 保存全量 GeoJSON
    geojson_path = os.path.join(OUTPUT_DIR, "poi_all.geojson")
    geojson = to_geojson(deduped)
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    log(f"\n✓ 全量GeoJSON已保存：{geojson_path}", log_file)

    # 保存全量 CSV
    csv_all_path = os.path.join(OUTPUT_DIR, "poi_all.csv")
    save_csv(deduped, csv_all_path)
    log(f"✓ 全量CSV已保存：{csv_all_path}", log_file)

    # 按分组保存子集CSV
    for group_name in POI_GROUPS:
        group_pois = [p for p in deduped if group_name in p["group"]]
        if group_pois:
            safe_name = group_name.replace("/", "_").replace(" ", "_")
            path = os.path.join(OUTPUT_DIR, f"poi_{safe_name}.csv")
            save_csv(group_pois, path)
            log(f"✓ {group_name}: {len(group_pois)} 条 → {path}", log_file)

    # 统计报告
    log("\n" + "=" * 60, log_file)
    log("采集完成 · 统计报告", log_file)
    log("=" * 60, log_file)
    log(f"总API请求数（估）：~{total_requests} 次", log_file)
    log(f"去重后POI总数：{len(deduped)} 条", log_file)
    log("", log_file)

    log("各分组数量（去重前）：", log_file)
    for gn, count in group_stats.items():
        feeds = POI_GROUPS[gn]["feeds"]
        log(f"  {gn:20s}  {count:>5d} 条  →  {feeds}", log_file)

    # 按高德一级分类统计（用于Shannon熵预览）
    log("\n高德一级分类分布（Shannon熵参考）：", log_file)
    type_dist = defaultdict(int)
    for poi in deduped:
        if poi["typecode"]:
            major = poi["typecode"][:2] + "0000"
            type_dist[major] += 1
    for code, count in sorted(type_dist.items(), key=lambda x: -x[1]):
        log(f"  {code}: {count:>5d} 条", log_file)

    log(f"\n全部文件已保存至 {os.path.abspath(OUTPUT_DIR)}/", log_file)
    log_file.close()
    print(f"\n完成！日志已保存至 {log_path}")


if __name__ == "__main__":
    main()
