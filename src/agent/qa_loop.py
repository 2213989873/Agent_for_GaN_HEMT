"""任务卡 11 核心：physics_qa 节点 —— 评分公式另一半的落地

闭环战术链（任务卡 10-bis 规范优先级的代码化）：

    START → coarse(LLM粗调) → optimize(精修) → physics_qa
      ├─ 通过 ────────────────────────────────→ END
      ├─ 驳回（重调次数 <2）── 带驳回原因 ──→ coarse（换初值）
      └─ 驳回（≥2，撞天花板）→ expand（扩提取空间，新参数族进场）→ optimize

QA 阈值来自任务卡 10-bis 任务 4c 定稿（知识表 3）；
"反复驳回=新参数族进场时机"来自任务卡 10-bis 任务 2 派生判据。
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import TypedDict

import numpy as np
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from openai import OpenAI
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.eval.metrics import nrmse  # noqa: E402
from src.tools.sim_tools import run_transfer_params  # noqa: E402

load_dotenv(ROOT / ".env")
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
           "all_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)
client = OpenAI(base_url="https://api.deepseek.com",
                api_key=os.getenv("DEEPSEEK_API_KEY"), timeout=60)

# ---------- QA 规则（任务卡 10-bis 任务 4c 定稿） ----------
QA_RULES = {                      # 物理合理区间（含触发值，超出=驳回）
    "voff": (-4.0, -0.5),         # D-mode 阈值电压 (V)
    "u0": (100e-3, 250e-3),       # GaN 低场迁移率 (m²/V·s)
    "rontr1": (-3.0, 1.0),        # 陷阱耦合强度
}
OPT_BOUNDS = {                    # 优化器边界（比 QA 宽，给探索留余地）
    "voff": (-3.0, -1.0),
    "u0": (0.05, 0.30),
    "rontr1": (-3.0, 1.0),
}
DEFAULTS = {"voff": -2.0, "u0": 170e-3, "rontr1": 0.0}
PARAM_ENTRY_ORDER = [["voff", "u0"], ["rontr1"]]  # 参数族进场顺序（知识表1）
BOUND_TOL = 1e-3                  # 触优化边界判定容差（相对）


class S(TypedDict):
    target_vg: np.ndarray
    target_id: np.ndarray
    params_space: list      # 当前提取参数名
    values: dict            # 当前参数值（初值/精修结果）
    rmse: float             # 当前 NRMSE
    qa_pass: bool
    violations: list        # QA 驳回原因
    n_retry: int            # 本参数空间内的重调次数
    log: list


def coarse(state: S) -> dict:
    """LLM 粗调给初值；带 QA 驳回历史时会针对性换方向。"""
    space = state["params_space"]
    fail_info = "；".join(state["violations"]) if state["violations"] else "无"
    prompt = f"""你是 GaN HEMT 建模工程师。为转移特性（Vd=1V）提取给优化器初值。
当前提取参数集：{space}。
上次 QA 驳回原因：{fail_info}（若"无"则是首轮，给常规初值）。
参考：甲器件 voff=-2.0, u0=0.17；新器件阈值一般略负、迁移率略低。
只输出 JSON：{{{", ".join(f'"{p}": 数值' for p in space)}}}"""
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150, temperature=0)
    m = re.search(r"\{[^{}]*\}", resp.choices[0].message.content, re.S)
    values = {p: DEFAULTS[p] for p in space}
    if m:
        try:
            obj = json.loads(m.group(0))
            for p in space:
                if p in obj:
                    values[p] = float(obj[p])
        except (json.JSONDecodeError, ValueError):
            pass
    return {"values": values,
            "log": state["log"] + [f"coarse: 初值 { {p: round(v, 4) for p, v in values.items()} }（驳回史: {fail_info}）"]}


def optimize(state: S) -> dict:
    """least_squares 精修当前参数空间。"""
    space = state["params_space"]
    tgt = state["target_id"]
    scale = np.abs(tgt).max()

    def resid(x):
        _, idv = run_transfer_params(dict(zip(space, x)), tag=f"qa{state['n_retry']}")
        return (idv - tgt) / scale

    x0 = np.array([state["values"][p] for p in space])
    lb = np.array([OPT_BOUNDS[p][0] for p in space])
    ub = np.array([OPT_BOUNDS[p][1] for p in space])
    x0 = np.clip(x0, lb + 1e-6, ub - 1e-6)
    r = least_squares(resid, x0, bounds=(lb, ub), xtol=1e-5)
    values = dict(zip(space, r.x))
    rmse_now = float(np.sqrt(np.mean(r.fun ** 2)))
    return {"values": values, "rmse": rmse_now,
            "log": state["log"] + [f"optimize({r.nfev}次仿真): "
                                   + " ".join(f"{p}={v:.4g}" for p, v in values.items())
                                   + f" → NRMSE={rmse_now:.2%}"]}


def physics_qa(state: S) -> dict:
    """QA 检查：物理范围 + 触优化边界告警（任务卡10-bis 定稿规则）。"""
    violations = []
    for p, v in state["values"].items():
        lo, hi = QA_RULES.get(p, (-np.inf, np.inf))
        if not (lo <= v <= hi):
            violations.append(f"{p}={v:.4g} 超出物理范围 [{lo:.4g}, {hi:.4g}]")
        blo, bhi = OPT_BOUNDS[p]
        if abs(v - blo) < BOUND_TOL * abs(blo) or abs(v - bhi) < BOUND_TOL * abs(bhi):
            violations.append(f"{p}={v:.4g} 触及优化边界（补偿解嫌疑）")
    qa_pass = not violations
    return {"qa_pass": qa_pass, "violations": violations,
            "n_retry": state["n_retry"] + (0 if qa_pass else 1),
            "log": state["log"] + [f"physics_qa: {'✅ 通过' if qa_pass else '❌ 驳回——' + '；'.join(violations)}"]}


def route_after_qa(state: S) -> str:
    if state["qa_pass"]:
        return END
    if state["n_retry"] < 2:
        return "coarse"          # 先换初值重调（兜底）
    return "expand"              # 反复驳回=撞天花板，新参数族进场（治本）


def expand(state: S) -> dict:
    """扩提取空间：按知识表1的进场顺序补下一族参数。"""
    space = list(state["params_space"])
    for fam in PARAM_ENTRY_ORDER:
        new = [p for p in fam if p not in space]
        if new:
            space += new
            values = dict(state["values"])
            for p in new:
                values[p] = DEFAULTS[p]
            return {"params_space": space, "values": values, "n_retry": 0,
                    "log": state["log"] + [f"expand: QA 反复驳回 → 新参数族进场 {new}（撞天花板判据）"]}
    return {"log": state["log"] + ["expand: 无更多参数族可扩，停"]}


def build():
    g = StateGraph(S)
    g.add_node("coarse", coarse)
    g.add_node("optimize", optimize)
    g.add_node("physics_qa", physics_qa)
    g.add_node("expand", expand)
    g.add_edge(START, "coarse")
    g.add_edge("coarse", "optimize")
    g.add_edge("optimize", "physics_qa")
    g.add_conditional_edges("physics_qa", route_after_qa,
                            {"coarse": "coarse", "expand": "expand", END: END})
    g.add_edge("expand", "optimize")
    return g.compile()
