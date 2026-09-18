"""任务卡 10 入口：乙器件 voff+u0 双参数耦合提取

扮演场景：transfer_yi.csv 是"晶圆实测"（真值 voff=-2.2, u0=150e-3，Agent 不知道），
Agent 从甲的参数（voff=-2.0, u0=170e-3）出发——模拟"以旧器件为起点提新器件"。

运行：python src/pipeline/run_dual.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.dual_loop import S, build  # noqa: E402

d = np.loadtxt(ROOT / "data" / "sim" / "transfer_yi.csv")

init: S = {
    "target_vg": d[:, 0],
    "target_id": -d[:, 1],
    "trial_vg": None,
    "trial_id": None,
    "params": {"voff": -2.0, "u0": 170e-3},   # 甲的参数作起点
    "rmse_hist": [],
    "params_hist": [],
    "best_params": None,
    "best_rmse": None,
    "iter": 0,
    "max_iter": 10,
    "log": [],
}

final = build().invoke(init)

print("===== 提取过程 =====")
for line in final["log"]:
    print(line)
bp = final["best_params"]
print(f"\n最优参数: voff={bp['voff']:.4f} V（真值 -2.2）, u0={bp['u0']*1e3:.1f}e-3（真值 150e-3）")
print(f"最优 NRMSE = {final['best_rmse']:.2%}")
print(f"误差: voff {abs(bp['voff'] + 2.2):.4f} V, u0 {abs(bp['u0'] - 150e-3)*1e3:.2f}e-3")
