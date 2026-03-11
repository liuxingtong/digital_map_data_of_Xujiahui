# CLD 平台集成优化方案

> 目标：在徐汇区找到人机共生赋能适老化改造的优先区域。  
> 问题：现有 `cld_platform_integration.md` 与平台数据结构不完全匹配。  
> 本文档提出优化方案，使 CLD 与平台数据对齐，并给出可落地的实施路径。

---

## 一、核心不匹配点诊断

### 1.1 空间单元不一致

| 集成文档假设 | 平台实际 | 冲突 |
|--------------|----------|------|
| 250m 格网 + 路网边中点 | 街景=点、人口=100m 栅格、用地=250m 网格、路网=边 | 多套空间单元，难以统一到 SD |
| N09/N11 用「全域 motor_ratio_pct」 | 路网边自带 highway/lanes/maxspeed | 应为**边级**，非全域 |
| N05 等时圈面积 | 平台有 `isochrone_nodes/edges`，按节点/边计算 | 需明确：以节点为源，还是以居住点为源 |

### 1.2 数据挂载现状

| 挂载目标 | 已有 | 缺失 |
|----------|------|------|
| 街景 → 边 | `attach_streetview_scores` | 需挂载 GVI、Shade_Comfort、ART_Score、Shannon_H、Complexity、Motor_Pressure |
| POI → 边 | `attach_poi_density`（poi_count） | 需按类别（社交/医疗/文化）分别挂载 |
| 人口 → 边 | `attach_population` | 已有 |
| 用地 → 边 | 无 | 需新增 `attach_landuse`（边中点最近网格的 shannon、green_rate） |
| 路网自身 | 边有 length、highway、lanes、maxspeed | 节点缺介数中心性（可算） |

### 1.3 决策单元与目标对齐

**改造决策**：在哪些**路段/节点**部署人机共生装置。

因此，**空间单元应统一为「路网边」或「路网节点」**，所有 CLD 变量都应在边/节点上有取值，而不是 250m 格网。

---

## 二、优化方案总览

### 2.1 两阶段策略

| 阶段 | 目标 | 数据需求 | 输出 |
|------|------|----------|------|
| **Phase 1：静态优先级排序** | 用现有数据算每条边的「适老化改造潜力」与「干预紧迫度」 | 边级挂载全部完成 | 边/节点优先级排序、地图热力图 |
| **Phase 2：系统动力学验证**（可选） | 对 Top-K 候选区域做简化 SD，验证干预效果 | 边级初始值 + 传递函数 | 时间演化曲线、敏感性分析 |

**建议**：先完成 Phase 1，用静态得分选出候选区域；Phase 2 作为后续扩展。

### 2.2 统一空间单元：路网边

**原则**：所有 CLD 节点在「边中点」上取值，边为最小决策单元。

```
边 (u,v) → 边中点 (lon_m, lat_m)
    ├── 街景：最近点插值 → GVI, Shade_Comfort, ART_Score, Shannon_H, Complexity, Motor_Pressure
    ├── POI：半径 100m 计数 → poi_social, poi_medical, poi_culture, poi_total
    ├── 人口：栅格采样 → pop_65plus, pop_15_59, pop_0_14
    ├── 用地：最近 250m 网格 → shannon, green_rate, n_types
    └── 路网：边自身 → length, highway, lanes, maxspeed
```

---

## 三、节点计算方式优化（边级）

### 3.1 A 类：直接可算（边级）

| 节点 | 优化后计算方式 | 平台实现 |
|------|----------------|----------|
| **N04** 路网连通性 | 节点介数中心性（边的两端点均值）或 β 指数（全域常数，边共享） | `compute_betweenness_centrality`，按边取 (u+v)/2 |
| **N05** 步行可达性 | 从边中点出发 500m 等时圈内**居住人口**（65+）或**居住边**数量 | 以边中点为源，`isochrone_nodes`，再对节点覆盖的 65+ 人口求和 |
| **N06** 土地混合度 | 边中点最近 250m 网格的 `shannon` | 新增 `attach_landuse`，或边中点与用地网格空间连接 |
| **N07** 绿化遮阴 | 边挂载 `streetview_GVI` + `streetview_Shade_Comfort`，等权或 0.6:0.4 | `attach_streetview_scores` 分别挂 GVI、Shade_Comfort |
| **N09** 车流量代理 | **边级**：`highway` 为 motor 则 1，否则 0；有 lanes 则 ×lanes/4；有 maxspeed 则 ×(maxspeed/60)，归一化 | 边属性已有，写 `compute_edge_traffic_pressure(u,v,d)` |
| **N11** 噪声与污染代理 | 同 N09，可叠加边挂载 `streetview_Motor_Pressure` | 路网 + 街景合成 |
| **N03** 街道界面活跃度 | `streetview_Shannon_H` + `streetview_Complexity` + `poi_total`（或 poi_social），归一化 | 挂载后合成 |

### 3.2 B 类：多源合成（边级，权重建议）

| 节点 | 优化后计算方式 | 权重建议 |
|------|----------------|----------|
| **N01** 社交场所密度 | `poi_social` + `poi_culture` + 0.8×`poi_medical`，归一化 | 1 : 1 : 0.8 |
| **N08** 街道舒适度 | `streetview_GVI` + `streetview_Shade_Comfort` + `streetview_Ped_Friendly` | 0.4 : 0.3 : 0.3 |
| **N14** 空间认知复杂度 | `streetview_Complexity` + `landuse_shannon` + `poi_total` 归一化 | 0.4 : 0.35 : 0.25 |
| **N15** 认知储备激活潜力 | `streetview_ART_Score`（已有公式） | 直接使用 |
| **N17** 环境生理压力 | `streetview_Motor_Pressure` + 边级 N09，min-max 归一化 | 0.5 : 0.5 |
| **N_YP** 年轻人密度 | `pop_15_59` 栅格采样 | 外生，边中点采样 |
| **N_GC** 隔代照料强度 | `pop_65plus` × `pop_0_14`，归一化 | 乘积后 min-max |

### 3.3 C 类：仿真内生（初始值）

| 节点 | 边级初始值 | 说明 |
|------|------------|------|
| **N02** 老年人聚集强度 | `pop_65plus` 归一化 | 用人口栅格作 proxy |
| **N10** 步行意愿 | 0.5 | 无数据，文献默认 |
| **N16** 主动探索意愿 | 0.5 | 无数据 |
| **N18** 人机共生干预 | 0.0 | 设计变量，仿真时拨动 |
| **N19** 行为数据密度 | 0.0 | 装置未部署 |
| **N_IG** 代际互动频率 | 0.4 | 无空间数据 |

---

## 四、平台需新增/扩展的模块

### 4.1 路网挂载扩展

| 模块 | 内容 | 优先级 |
|------|------|--------|
| `attach_streetview_scores` 多指标 | 一次挂载 GVI, Shade_Comfort, ART_Score, Shannon_H, Complexity, Motor_Pressure | ⭐⭐⭐ |
| `attach_poi_by_category` | 按 group 筛选 POI，挂载 poi_social, poi_medical, poi_culture | ⭐⭐⭐ |
| `attach_landuse` | 边中点与 250m 用地网格空间连接，取 shannon, green_rate, n_types | ⭐⭐⭐ |
| `attach_population_multiage` | 挂载 pop_65plus, pop_15_59, pop_0_14 | ⭐⭐ |
| `compute_edge_traffic_pressure` | 边级 N09/N11 计算 | ⭐⭐⭐ |

### 4.2 综合边权重（CLD 合成）

| 函数 | 含义 | 公式 |
|------|------|------|
| `compute_edge_activation_potential` | 认知储备激活潜力（R4 相关） | N14 + N15 - N17 的边级合成 |
| `compute_edge_social_vitality` | 社交活力（R1 相关） | N01 + N02_proxy + N03 |
| `compute_edge_intervention_priority` | 改造优先级 | 高 N15 + 高 N02 + 低 N17 + 高介数，加权 |

### 4.3 等时圈与可达性

| 内容 | 说明 |
|------|------|
| 居住点定义 | 用 65+ 人口栅格格心，或小区点，作为「居住源」 |
| 边可达性 | 从居住源出发 500m 步行，能到达的边；或从边出发 500m 能覆盖的居住人口 |
| N05 边级 | 边中点 500m 等时圈内 65+ 人口总和，归一化 |

---

## 五、实施顺序建议

```
Step 1：扩展 weights.py
  ├── attach_streetview_scores 支持多指标批量挂载
  ├── attach_poi_by_category（社交/医疗/文化）
  ├── attach_landuse（边中点 → 最近用地网格）
  └── compute_edge_traffic_pressure（N09/N11 边级）

Step 2：实现 compute_edge_cld_values
  └── 按上文公式计算 N01–N17、N_YP、N_GC 的边级值

Step 3：实现 compute_edge_intervention_priority
  └── 综合得分 = f(N02, N15, N17, betweenness)，输出边排序

Step 4：仪表盘新增「改造优先级」图层
  └── 路网边按 priority 着色，叠加 65+ 人口热力

Step 5（可选）：简化 SD 模块
  └── 对 Top 50 边所在片区，做聚合后的 SD 仿真
```

---

## 六、与 cld_platform_integration.md 的修订对照

| 原文档 | 优化后 |
|--------|--------|
| 250m 格网 + 边中点双单元 | **统一为边中点**，用地从网格插值到边 |
| N09 用 motor_ratio_pct（全域） | **边级** highway/lanes/maxspeed |
| N05 等时圈面积 | 等时圈内 65+ 人口或居住边数 |
| B 类权重「待确认」 | 采用建议值 1:1:0.8、0.4:0.3:0.3 等 |
| 输出 JSON 初始化文件 | 增加**边级 CSV**：edge_id, N01, N02, ..., priority |
| SD 仿真为必选 | **Phase 1 仅静态排序**，SD 为 Phase 2 可选 |

---

## 七、预期输出

1. **边级 CLD 变量表**：每条边有 N01–N17、N_YP、N_GC 的数值  
2. **改造优先级排序**：按综合得分排序的边列表  
3. **地图可视化**：路网边按优先级着色，叠加人口热力  
4. **候选区域报告**：Top-K 边所在街道/片区，供实地调研与方案设计  

---

*优化方案 · 2026 年 3 月 · 对齐平台数据与 CLD 集成*
