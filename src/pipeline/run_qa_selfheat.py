"""任务卡 13 入口：热参数族进场 + expand 双触发器实战

目标：dc_output_yi.csv（乙全处方**含自热**版，847 点——饱和区下垂就是 rth0=20 的签名）。
提取空间从 (voff, u0) 起步，预期剧情：
  两参数 → NRMSE 未达标（缺陷阱+缺自热）→ 触发器2 扩 rontr1
        → 仍缺自热 → 触发器2 扩 rth0 → 四参数命中真值。
真值：voff=-2.2, u0=150e-3, rontr1=-1, rth0=20（cth0 在 DC 下不起作用）。

运行：python src/pipeline/run_qa_selfheat.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.qa_loop import S, build  # noqa: E402
from src.tools.sim_tools import run_output_selfheat_params  # noqa: E402

d = np.loadtxt(ROOT / "data" / "sim" / "dc_output_yi.csv")

init: S = {
    "target_vg": d[:, 0],
    "target_id": -d[:, 1],
    "sim_fn": run_output_selfheat_params,   # 含自热的输出特性（847 点）
    "params_space": ["voff", "u0"],
    "values": {"voff": -2.0, "u0": 170e-3},
    "rmse": None,
    "qa_pass": False,
    "violations": [],
    "n_retry": 0,
    "log": [],
}

final = build().invoke(init, {"recursion_limit": 60})

print("===== physics_qa 闭环（乙·输出特性·含自热 847 点）=====")
for line in final["log"]:
    print(line)
print(f"\n最终参数空间: {final['params_space']}")
print("最终参数: " + " ".join(f"{p}={v:.5g}" for p, v in final["values"].items()))
print(f"最终 NRMSE = {final['rmse']:.4%}")
print("（真值 voff=-2.2, u0=150e-3, rontr1=-1.0, rth0=20）")
