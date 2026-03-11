"""
CLD 系统动力学（SD）仿真模块
============================
按 CLD_SD_可行性说明.md 实现：N18 为 N_YP→代际接触的转换器。
模拟不同 N18 干预强度下，N15、N16、N_IG 的时间演化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd


# 默认参数（可标定）
DEFAULT_PARAMS = {
    "alpha": 2.0,       # N18 对 N_YP→N_IG 的放大系数
    "beta": 0.15,       # N_IG→N15 注入强度
    "gamma": 0.6,       # N18 对 N10 的削弱系数
    "delta": 0.5,       # N18 对 N17 的削弱系数
    "tau_IG": 0.3,      # N_IG 调整时间常数（月^-1）
    "k14": 0.2,         # N14→N15
    "k17": 0.25,        # N17→N15(-)
    "k15_decay": 0.05,  # N15 自然衰减
    "k16_from_N15": 0.2,   # N15→N16
    "k16_from_GC": 0.15,   # N_GC→N16(-)
    "k16_decay": 0.05,     # N16 衰减
    "k19_from_N02": 0.1,   # N02*N18→N19
    "k_b4": 0.3,           # B4 干预疲劳
    "k19_decay": 0.02,     # N19 衰减
    "k20_from_N19": 0.15,  # N19→N20
    "k20_decay": 0.02,    # N20 衰减
}


@dataclass
class SDInitialValues:
    """SD 仿真初始值（片区聚合或手动设定）"""
    N01: float = 0.5
    N02: float = 0.5
    N03: float = 0.5
    N04: float = 0.5
    N05: float = 0.5
    N06: float = 0.5
    N07: float = 0.5
    N09: float = 0.5
    N10_base: float = 0.5   # 车流量代理（无 N17 时用）
    N14: float = 0.5
    N15: float = 0.5
    N16: float = 0.5
    N17: float = 0.5
    N_YP: float = 0.5
    N_GC: float = 0.5
    N_IG: float = 0.4
    N19: float = 0.0
    N20: float = 0.0

    def to_dict(self) -> dict:
        return {
            "N01": self.N01, "N02": self.N02, "N03": self.N03,
            "N04": self.N04, "N05": self.N05, "N06": self.N06,
            "N07": self.N07, "N09": self.N09, "N10_base": self.N10_base,
            "N14": self.N14, "N15": self.N15, "N16": self.N16,
            "N17": self.N17, "N_YP": self.N_YP, "N_GC": self.N_GC,
            "N_IG": self.N_IG, "N19": self.N19, "N20": self.N20,
        }


def aggregate_from_priority_df(
    df_prio: "pd.DataFrame",
    top_k: int = 50,
) -> SDInitialValues:
    """
    从边级 CLD 优先级 DataFrame 聚合 Top-K 边的均值，生成 SD 初始值。
    """
    if df_prio is None or len(df_prio) == 0:
        return SDInitialValues()

    top = df_prio.nlargest(min(top_k, len(df_prio)), "priority")
    cols = ["N01", "N02", "N03", "N06", "N07", "N08", "N14", "N15", "N17", "N_YP", "N_GC"]
    means = {}
    for c in cols:
        if c in top.columns:
            means[c] = float(top[c].mean())
        else:
            means[c] = 0.5

    # N08 映射到 N09（街道舒适度）
    n09 = means.get("N08", 0.5)
    n10_base = 0.5  # 车流量代理，边级无直接值，用默认

    return SDInitialValues(
        N01=means.get("N01", 0.5),
        N02=means.get("N02", 0.5),
        N03=means.get("N03", 0.5),
        N04=0.5, N05=0.5, N06=means.get("N06", 0.5),
        N07=means.get("N07", 0.5),
        N09=n09,
        N10_base=n10_base,
        N14=means.get("N14", 0.5),
        N15=means.get("N15", 0.5),
        N16=0.5,
        N17=means.get("N17", 0.5),
        N_YP=means.get("N_YP", 0.5),
        N_GC=means.get("N_GC", 0.5),
        N_IG=0.4,
        N19=0.0,
        N20=0.0,
    )


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def run_sd_simulation(
    t0: SDInitialValues,
    N18: float,
    months: int = 24,
    dt_month: float = 1.0,
    params: dict | None = None,
) -> "pd.DataFrame":
    """
    运行 SD 仿真。

    Args:
        t0: 初始值
        N18: 人机干预强度（0 / 0.3 / 0.6 / 1.0）
        months: 仿真月数
        dt_month: 步长（月）
        params: 覆盖默认参数

    Returns:
        DataFrame 含列: month, N02, N15, N16, N_IG, N19, N20
    """
    import numpy as np
    import pandas as pd

    p = {**DEFAULT_PARAMS, **(params or {})}
    alpha = p["alpha"]
    beta = p["beta"]
    gamma = p["gamma"]
    delta = p["delta"]
    tau_IG = p["tau_IG"]
    k14 = p["k14"]
    k17 = p["k17"]
    k15_decay = p["k15_decay"]
    k16_from_N15 = p["k16_from_N15"]
    k16_from_GC = p["k16_from_GC"]
    k16_decay = p["k16_decay"]
    k19_from_N02 = p["k19_from_N02"]
    k_b4 = p["k_b4"]
    k19_decay = p["k19_decay"]
    k20_from_N19 = p["k20_from_N19"]
    k20_decay = p["k20_decay"]

    # 外生（固定）
    N01, N03, N05, N07, N09 = t0.N01, t0.N03, t0.N05, t0.N07, t0.N09
    N14, N17_base, N_YP, N_GC = t0.N14, t0.N17, t0.N_YP, t0.N_GC
    N10_base = t0.N10_base

    # N18 削弱
    N17_eff = _clip(N17_base * (1 - delta * N18))
    N10_eff = _clip(N10_base * (1 - gamma * N18))

    # 状态
    y = np.array([
        t0.N02, t0.N15, t0.N16, t0.N_IG, t0.N19, t0.N20,
    ])

    n_steps = int(months / dt_month) + 1
    rows = []

    for i in range(n_steps):
        t = i * dt_month
        N02, N15, N16, N_IG, N19, N20 = y

        # N_IG: 目标 = N_YP * (1 + α*N18)，一阶延迟
        N_IG_target = _clip(N_YP * (1 + alpha * N18))
        dN_IG = tau_IG * (N_IG_target - N_IG) * dt_month

        # N15: R4 + N_IG 注入
        dN15 = (k14 * N14 - k17 * N17_eff * N15 + beta * N_IG - k15_decay * N15) * dt_month

        # N16: N15→N16, N_GC→N16(-), 衰减
        dN16 = (k16_from_N15 * N15 - k16_from_GC * N_GC - k16_decay * N16) * dt_month

        # N19: R5 N02*N18, B4 N18*N19(-)
        dN19 = (k19_from_N02 * N02 * N18 - k_b4 * N18 * N19 - k19_decay * N19) * dt_month

        # N20: N19→N20
        dN20 = (k20_from_N19 * N19 - k20_decay * N20) * dt_month

        # N02: 简化，R1/R2/R3 注入 - 轻度衰减
        dN02 = (0.1 * (N01 + N03 + N05 + N07 + N09) / 5 - 0.02 * N02 + 0.05 * N18) * dt_month

        y = y + np.array([dN02, dN15, dN16, dN_IG, dN19, dN20])
        y = np.array([_clip(v) for v in y])

        rows.append({
            "month": t,
            "N02": y[0], "N15": y[1], "N16": y[2],
            "N_IG": y[3], "N19": y[4], "N20": y[5],
        })

    return pd.DataFrame(rows)


def run_sd_scenarios(
    t0: SDInitialValues,
    N18_levels: list[float] | None = None,
    months: int = 24,
    params: dict | None = None,
) -> "pd.DataFrame":
    """
    多情景仿真：不同 N18 档位下的时间演化。

    Returns:
        DataFrame 含列: scenario, month, N02, N15, N16, N_IG, N19, N20
    """
    import pandas as pd

    N18_levels = N18_levels or [0.0, 0.3, 0.6, 1.0]
    dfs = []
    for n18 in N18_levels:
        df = run_sd_simulation(t0, N18=n18, months=months, params=params)
        df["scenario"] = f"N18={n18:.1f}"
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)
