"""QA validator（agent架构设计 v1.1 §4）

参数级：阈值单一来源 = qa_loop.QA_RULES / OPT_BOUNDS（知识表3 的代码化），不复制。
曲线级：
- 单调性按形态分区——转移特性要求单调不降；输出特性饱和区豁免
  （自热下垂是合法负微分，卡07③ -2.8% 签名），只查线性段。
- 对称性（v1.1 修订）：物理镜像定义已废弃（GaN HEMT 源漏/场板本就不对称，
  asmhemt.va 495/499/505/592 行），新定义=模型与实测不对称度相对一致；
  默认不启用，待赛题 Q&A 明确含义后标定。
- kink：未标定，默认不启用。
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.qa_loop import BOUND_TOL, OPT_BOUNDS, QA_RULES  # noqa: E402

MONO_TOL = 1e-3          # 单调性容差（相对峰值），⚠️ 初定未标定
LINEAR_VD_MAX = 1.0      # 输出特性只查 Vd≤1V 线性段的单调性


def param_violations(values: dict) -> list[str]:
    """参数物理范围 + 触优化边界告警（与 qa_loop.physics_qa 同规则）。"""
    v = []
    for p, val in values.items():
        lo, hi = QA_RULES.get(p, (-np.inf, np.inf))
        if not (lo <= val <= hi):
            v.append(f"{p}={val:.4g} 超出物理范围 [{lo:.4g}, {hi:.4g}]")
        blo, bhi = OPT_BOUNDS[p]
        if abs(val - blo) < BOUND_TOL * abs(blo) or abs(val - bhi) < BOUND_TOL * abs(bhi):
            v.append(f"{p}={val:.4g} 触及优化边界（补偿解嫌疑）")
    return v


def monotonic_violations(x: np.ndarray, y: np.ndarray, form: str) -> list[str]:
    """单调性按形态分区。x/y 为单条曲线（输出特性需调用方先按 Vg 阶梯切条）。"""
    peak = float(np.abs(y).max())
    if peak == 0:
        return []
    if form == "dc_output":
        mask = x <= LINEAR_VD_MAX      # 饱和区豁免（自热下垂合法）
        x, y = x[mask], y[mask]
    d = np.diff(y)
    bad = int((d < -MONO_TOL * peak).sum())
    if bad:
        return [f"{form} 非单调：{bad} 处下降超容差 {MONO_TOL:.0%}·峰值"]
    return []


def curve_violations(curves: dict, enabled=("monotonic",)) -> list[str]:
    """curves: {form: (x, y)}。对称性/kink 未标定（v1.1 §4），不在 enabled 里就不查。"""
    out = []
    if "monotonic" in enabled:
        for form, (x, y) in curves.items():
            out += monotonic_violations(np.asarray(x), np.asarray(y), form)
    return out
