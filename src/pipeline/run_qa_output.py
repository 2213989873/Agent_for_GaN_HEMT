"""任务卡 12 Part B 入口：DC 输出特性纳入拟合

目标：dc_output_yi_iso.csv（乙全处方等温版，847 点 = 7 条 Vg 阶梯 × 121 点 Vd 扫描）
——赛题真实数据形态（多偏置网格）。两参数起步，预期 QA 自动扩 rontr1 后命中。
自热（rth0/cth0）刻意排除在本卡之外，热参数族进场留任务卡 13。

运行：python src/pipeline/run_qa_output.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.qa_loop import S, build  # noqa: E402
from src.tools.sim_tools import run_output_params  # noqa: E402

d = np.loadtxt(ROOT / "data" / "sim" / "dc_output_yi_iso.csv")

init: S = {
    "target_vg": d[:, 0],
    "target_id": -d[:, 1],
    "sim_fn": run_output_params,        # 输出特性形态（847 点嵌套扫描）
    "params_space": ["voff", "u0"],
    "values": {"voff": -2.0, "u0": 170e-3},
    "rmse": None,
    "qa_pass": False,
    "violations": [],
    "n_retry": 0,
    "log": [],
}

final = build().invoke(init)

print("===== physics_qa 闭环过程（乙·DC 输出特性 847 点）=====")
for line in final["log"]:
    print(line)
print(f"\n最终参数空间: {final['params_space']}")
print("最终参数: " + " ".join(f"{p}={v:.5g}" for p, v in final["values"].items()))
print(f"最终 NRMSE = {final['rmse']:.4%}")
print("（真值 voff=-2.2, u0=150e-3, rontr1=-1.0）")
