"""任务卡 09 核心：最小提取闭环 —— LLM 在环提取 voff

图结构（任务卡 01 的状态机概念实战）：

    START → simulate → evaluate → decide ──收敛/超限──→ END
                                    │
                                    └─继续──→ propose(LLM) → simulate

State 沿图流动；每个节点读 state、返回要更新的字段。
propose 是唯一"动脑"的节点：把目标曲线和当前试算曲线摆给 LLM，
让它像工程师一样决定下一个 voff 猜多少。
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.eval.metrics import nrmse  # noqa: E402
from src.tools.sim_tools import run_transfer  # noqa: E402

load_dotenv(ROOT / ".env")

# WSL 网络坑（2026-09-18 实测）：shell 里的 127.0.0.1:7897 代理是 Windows 主机的，
# WSL 的 127.0.0.1 是自己——代理变量在 WSL 里指向虚空，SSL 握手必超时。
# DeepSeek 直连可通（curl 实测 0.16s 返回 401），摘掉代理变量走直连。
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
           "all_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)

client = OpenAI(base_url="https://api.deepseek.com",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                timeout=60)

SAMPLE_VG = [-4, -3, -2.5, -2, -1.5, -1, -0.5, 0, 1, 2]  # 给 LLM 看的采样点
CONVERGE_TOL = 0.02  # NRMSE < 2% 判收敛


class S(TypedDict):
    target_vg: np.ndarray   # 目标（"晶圆实测"）曲线
    target_id: np.ndarray
    trial_vg: np.ndarray    # 当前试算曲线
    trial_id: np.ndarray
    voff: float             # 当前 voff 猜测
    rmse_hist: list         # 每轮 NRMSE
    voff_hist: list         # 每轮尝试的 voff
    best_voff: float        # 历史最优（交卷交这张，不是最后一次）
    best_rmse: float
    iter: int
    max_iter: int
    log: list


def _sample(vg: np.ndarray, y: np.ndarray) -> dict:
    """在固定采样点上取电流值，给 LLM 看的"曲线摘要"。"""
    return {f"Vg={v}": round(float(y[np.argmin(np.abs(vg - v))]), 5) for v in SAMPLE_VG}


def simulate(state: S) -> dict:
    vg, idv = run_transfer(state["voff"], tag=f"iter{state['iter']}")
    return {"trial_vg": vg, "trial_id": idv}


def evaluate(state: S) -> dict:
    r = nrmse(state["trial_id"], state["target_id"])  # 同协议同网格，直接对位
    # 交卷交历史最优，不是最后一次（2026-09-18 震荡教训）
    best_v, best_r = state.get("best_voff"), state.get("best_rmse")
    if best_r is None or r < best_r:
        best_v, best_r = state["voff"], r
    return {
        "rmse_hist": state["rmse_hist"] + [r],
        "voff_hist": state["voff_hist"] + [state["voff"]],
        "best_voff": best_v,
        "best_rmse": best_r,
        "log": state["log"] + [f"iter{state['iter']}: voff={state['voff']:.4f} V, NRMSE={r:.2%}"
                               + ("  ← 新最优" if best_v == state["voff"] else "")],
    }


def route(state: S) -> str:
    """条件边：收敛或超限 → 收工；否则 → 让 LLM 提下一个猜测。"""
    if state["rmse_hist"][-1] < CONVERGE_TOL:
        return END
    if state["iter"] >= state["max_iter"]:
        return END
    return "propose"


def propose(state: S) -> dict:
    # voff ↔ NRMSE 配对历史——LLM 必须看到"哪个值误差多小"才会逼近，
    # 只给 voff 列表它会震荡（2026-09-18 实测教训）
    hist = "\n".join(
        f"  voff={v:.4f} → NRMSE={r:.2%}"
        for v, r in zip(state["voff_hist"], state["rmse_hist"])
    )
    prompt = f"""你是 GaN HEMT 建模工程师，正在提取阈值电压 voff。
器件线性区转移特性（Vd=1V）的实测数据（Vg: Id/A）：
{json.dumps(_sample(state["target_vg"], state["target_id"]))}
你当前用 voff={state["voff"]:.4f} 仿真的结果：
{json.dumps(_sample(state["trial_vg"], state["trial_id"]))}
历史（voff → 拟合误差 NRMSE，越小越好）：
{hist}
物理知识：voff 是阈值电压，即 Id 开始明显起流的栅压；voff 越负，曲线整体右移（需要更高的 Vg 才导通）。
策略要求：历史里 NRMSE 最小的方向就是对的方向；朝它继续、并步进减半逼近（二分法），
不要重复试过的值。请给出下一个 voff 尝试值。只输出 JSON：{{"voff": 数值, "reason": "一句话"}}"""
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0,  # 工程 pipeline 锁可复现性
    )
    text = resp.choices[0].message.content
    m = re.search(r"\{[^{}]*\}", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            new_voff, reason = float(obj["voff"]), obj.get("reason", "?")
        except (json.JSONDecodeError, KeyError, ValueError):
            new_voff, reason = state["voff"] - 0.2, "JSON 解析失败，默认步进 -0.2"
    else:
        new_voff, reason = state["voff"] - 0.2, "未返回 JSON，默认步进 -0.2"
    return {
        "voff": new_voff,
        "iter": state["iter"] + 1,
        "log": state["log"] + [f"  LLM 提议 voff={new_voff} —— {reason}"],
    }


def build():
    g = StateGraph(S)
    g.add_node("simulate", simulate)
    g.add_node("evaluate", evaluate)
    g.add_node("propose", propose)
    g.add_edge(START, "simulate")
    g.add_edge("simulate", "evaluate")
    g.add_conditional_edges("evaluate", route, {"propose": "propose", END: END})
    g.add_edge("propose", "simulate")
    return g.compile()
