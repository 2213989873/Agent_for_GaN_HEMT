"""任务卡 10 下半场：混合架构 —— LLM 粗定位 + 数值优化器精修

上半场教训（实测）：两参数子集拟合存在"未建模差异天花板"——乙的 ron_trap 随 Vg
变化（trapmod=2 效应），不在 (voff,u0) 提取空间内，真值组合 NRMSE=11.08%，
LLM 逐点猜参在鞍点打转。工业做法：LLM 给初值+归因，优化器精修。

本脚本两段实验：
  A. 乙器件实战：LLM 粗调 3 轮 → least_squares 精修，看能压到多少（预期≈天花板 9.9%）
  B. 干净目标对照：目标本身就是"只差 voff/u0 的合成器件"，验证架构能收敛到真值≈0
     —— 证明天花板来自未建模差异，不是架构缺陷

运行：python src/pipeline/run_hybrid.py
"""
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.dual_loop import S as DS  # noqa: E402
from src.agent.dual_loop import build  # noqa: E402
from src.eval.metrics import nrmse  # noqa: E402
from src.tools.sim_tools import run_transfer2  # noqa: E402


def llm_coarse(target_vg: np.ndarray, target_id: np.ndarray, rounds: int = 3) -> dict:
    """LLM 粗调：从甲的参数出发跑 N 轮，返回历史最优作优化器初值。"""
    init: DS = {
        "target_vg": target_vg, "target_id": target_id,
        "trial_vg": None, "trial_id": None,
        "params": {"voff": -2.0, "u0": 170e-3},
        "rmse_hist": [], "params_hist": [],
        "best_params": None, "best_rmse": None,
        "iter": 0, "max_iter": rounds, "log": [],
    }
    final = build().invoke(init)
    for line in final["log"]:
        print("  " + line)
    return final["best_params"]


def refine(target_id: np.ndarray, x0: np.ndarray, label: str) -> np.ndarray:
    """least_squares 精修：残差按目标峰值归一（即直接最小化 NRMSE）。"""
    scale = np.abs(target_id).max()

    def resid(x):
        _, idv = run_transfer2(x[0], x[1], tag=f"hyb_{label}")
        return (idv - target_id) / scale

    t0 = time.time()
    r = least_squares(resid, x0, bounds=([-3.0, 0.05], [-1.0, 0.30]), xtol=1e-5)
    print(f"  精修: {r.nfev} 次仿真, {time.time()-t0:.0f}s, "
          f"voff={r.x[0]:.4f}, u0={r.x[1]*1e3:.2f}e-3, NRMSE={np.sqrt(np.mean(r.fun**2)):.4%}")
    return r.x


# ---------- A. 乙器件实战 ----------
print("===== A. 乙器件（含 trapmod=2 未建模差异）=====")
d = np.loadtxt(ROOT / "data" / "sim" / "transfer_yi.csv")
tgt_vg, tgt_id = d[:, 0], -d[:, 1]
print("[1] LLM 粗调 3 轮：")
bp = llm_coarse(tgt_vg, tgt_id)
print(f"  LLM 初值: voff={bp['voff']:.4f}, u0={bp['u0']*1e3:.1f}e-3")
print("[2] 优化器精修：")
x = refine(tgt_id, np.array([bp["voff"], bp["u0"]]), "yi")
print(f"  （真值 voff=-2.2, u0=150e-3；两参数子集的天花板≈9.9%）")

# ---------- B. 干净目标对照 ----------
print("\n===== B. 干净目标（只含 voff/u0 差异的合成器件）=====")
TRUE_VOFF, TRUE_U0 = -2.3, 0.160
vg_c, id_c = run_transfer2(TRUE_VOFF, TRUE_U0, tag="clean_target")
print(f"合成目标真值: voff={TRUE_VOFF}, u0={TRUE_U0}")
x = refine(id_c, np.array([-2.0, 0.170]), "clean")
print(f"  命中误差: voff {abs(x[0]-TRUE_VOFF):.5f} V, u0 {abs(x[1]-TRUE_U0)*1e3:.3f}e-3")
