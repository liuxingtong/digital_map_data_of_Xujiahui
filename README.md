# 徐家汇空间规划一张图

徐家汇地区多源空间数据融合平台，支持街景指标、人口分布、POI、房价小区、用地类型、路网等数据的可视化与分析，面向老年人友好型街道与认知储备激活的 CLD 建模研究。

---

## 功能模块

| 模块 | 数据来源 | 可视化形式 |
|------|----------|------------|
| **街景指标** | 街景图像分割 CSV | 散点图、热力图、KDE、等值线、雷达图 |
| **人口分布** | 栅格 TIF | 栅格热力图、KDE、等值线 |
| **POI 分布** | 高德 POI CSV | 标记点、热力图、KDE、等值线 |
| **房价小区** | 小区数据 CSV | 标记点、热力图、KDE、等值线 |
| **用地类型** | OSM landuse/leisure/natural | 多边形地图、热力图、等值线 |
| **路网** | OSM 步行路网 | 按 highway/lanes/maxspeed/length 着色 |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_visualization.txt
```

### 2. 数据准备（可选）

部分模块需预先拉取数据：

```bash
# 路网（仪表盘路网模块必需）
python fetch_road_network.py

# 用地类型
python fetch_landuse.py
```

### 3. 启动仪表盘

```bash
streamlit run streetview_dashboard.py
```

或双击 `run_dashboard.bat`（Windows）。

启动后在浏览器打开 **http://localhost:8501**。

---

## 数据目录结构

```
SVI/
├── streetview_images/     # 街景 CSV（merged.csv 等）
├── population/            # 人口栅格 TIF
├── poi_data/              # POI CSV
├── house_data/            # 房价小区 CSV
├── road/                  # 路网 GraphML（fetch_road_network.py 生成）
├── landuse_data/          # 用地 GeoJSON/CSV（fetch_landuse.py 生成）
└── docs/                  # 建模思路与待办文档
```

---

## 主要脚本

| 脚本 | 用途 |
|------|------|
| `streetview_dashboard.py` | 主仪表盘入口 |
| `fetch_road_network.py` | 从 OSM 拉取徐家汇步行路网 |
| `fetch_landuse.py` | 从 OSM 拉取用地多边形 |
| `clip_population.py` | 裁剪人口栅格到徐家汇范围 |

---

## 技术栈

- **可视化**：Streamlit、Folium、Plotly
- **空间分析**：GeoPandas、OSMnx、NetworkX、Rasterio
- **高阶分析**：SciPy（KDE）、Matplotlib（等值线）

---

## 建模背景

平台为「老年人认知储备激活」CLD 建模提供数据基础，支持将街景、POI、人口、用地等挂载到路网边/节点，用于后续系统动力学与多目标优化分析。详见 `docs/空间规划建模思路与待办.md`。

---

## License

MIT
