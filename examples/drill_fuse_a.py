"""熔断 A 演练（卡15）：单族精修撞墙 → 分段残差归因，别傻跑

模拟：乙器件 dc_output（含自热+陷阱）只给 voff/u0 两参数族、
family_order 锁死无族可扩——必然撞墙。记录仿真计数与终态 NRMSE，
然后由 residual_triage.py 执行归因处置（证据链闭环）。

用法：python examples/drill_fuse_a.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.agent.qa_loop import S, build  # noqa: E402
from src.tools.sim_tools import run_output_selfheat_params  # noqa: E402

d = np.loadtxt(ROOT / "data" / "devices" / "yi" / "dc_output_yi.csv")
cnt = {"n": 0}


def counting_sim(p, tag):
    cnt["n"] += 1
    return run_output_selfheat_params(p, tag)


init: S = {"target_vg": d[:, 0], "target_id": -d[:, 1], "sim_fn": counting_sim,
           "params_space": ["voff", "u0"], "values": {"voff": -2.0, "u0": 0.17},
           "rmse": None, "qa_pass": False, "violations": [], "n_retry": 0,
           "rmse_target": 0.001, "warm_start": True,
           "family_order": [["voff", "u0"]],   # 锁死：无族可扩=必然撞墙
           "freeze": None, "log": []}

final = build().invoke(init, {"recursion_limit": 60})
print("撞墙现场：实际仿真", cnt["n"], "次；终态 NRMSE =",
      f"{final['rmse']:.2%}", "；终参数",
      {k: round(v, 4) for k, v in final["values"].items()})
for line in final["log"]:
    print(" ", line)
print("\n—— 熔断 A 触发（单族撞墙）→ 处置：residual_triage 分段归因 ——")
