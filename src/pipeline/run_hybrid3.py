"""任务卡10-bis 任务2：提取空间补 rontr1，重跑混合架构（规范3实证）

任务1已确证 harness/目标两侧 rdsmod=1 一致（接入电阻基线差=0），
缺口全在 trapmod=2 的 ron_trap。本脚本把 rontr1 补进提取空间：
  LLM 粗调 2 轮（voff/u0）→ least_squares 三参数精修 (voff, u0, rontr1)

预登记判读标准：NRMSE <1% 且参数落在真值附近（voff=-2.2, u0=150e-3, rontr1=-1）
→ 规范3（提取空间须覆盖主要差异源）实证通过；降不动 → 原样贴数据停手。

运行：python src/pipeline/run_hybrid3.py
"""
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.eval.metrics import nrmse  # noqa: E402
from src.tools.sim_tools import run_transfer3  # noqa: E402

d = np.loadtxt(ROOT / "data" / "sim" / "transfer_yi.csv")
tgt_vg, tgt_id = d[:, 0], -d[:, 1]
scale = np.abs(tgt_id).max()


def resid(x):
    _, idv = run_transfer3(x[0], x[1], x[2], tag="bis2")
    return (idv - tgt_id) / scale


# LLM 粗调结论（卡10第一幕）：起流点≈-2.2 方向、u0 略低于甲 → 初值 (-2.1, 0.155)
# rontr1 从 0（无陷阱）起步，让优化器自己发现陷阱强度
x0 = np.array([-2.1, 0.155, 0.0])
print(f"初值: voff={x0[0]}, u0={x0[1]}, rontr1={x0[2]}")
t0 = time.time()
r = least_squares(resid, x0,
                  bounds=([-3.0, 0.05, -3.0], [-1.0, 0.30, 1.0]), xtol=1e-5)
final_nrmse = float(np.sqrt(np.mean(r.fun ** 2)))
print(f"\n精修: {r.nfev} 次仿真, {time.time()-t0:.0f}s")
print(f"结果: voff={r.x[0]:.4f} (真值-2.2), u0={r.x[1]*1e3:.2f}e-3 (真值150), "
      f"rontr1={r.x[2]:.4f} (真值-1.0)")
print(f"NRMSE = {final_nrmse:.4%}   预登记判读: <1% 且近真值 → 规范3实证通过")
