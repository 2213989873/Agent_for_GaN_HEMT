"""任务卡 09 入口：甲器件 voff 最小提取闭环

扮演场景：transfer_jia.csv 是"晶圆实测"（真值 voff=-2.0，但 Agent 不知道），
Agent 从初始猜测 voff=-1.0 出发，通过 仿真→对拍→LLM 修正 的循环逼近真值。

运行：python src/pipeline/run_mini.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.mini_loop import S, build  # noqa: E402

d = np.loadtxt(ROOT / "data" / "sim" / "transfer_jia.csv")

init: S = {
    "target_vg": d[:, 0],
    "target_id": -d[:, 1],
    "trial_vg": None,
    "trial_id": None,
    "voff": -1.0,       # 初始猜测（故意偏 1V）
    "rmse_hist": [],
    "voff_hist": [],
    "iter": 0,
    "max_iter": 6,
    "log": [],
}

final = build().invoke(init)

print("===== 提取过程 =====")
for line in final["log"]:
    print(line)
print(f"\n收敛 voff = {final['voff']:.4f} V（真值 -2.0）")
print(f"最终 NRMSE = {final['rmse_hist'][-1]:.2%}")
print(f"收敛误差 = {abs(final['voff'] + 2.0):.4f} V")
