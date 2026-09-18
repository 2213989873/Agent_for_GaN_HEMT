"""任务卡 10 核心：双参数耦合提取 —— voff + u0 同时提（LLM 在环）

与任务卡 09 的差异：参数从一个变两个。难点在于两参数效果纠缠——
voff 偏了看起来像 u0 偏小（曲线整体偏低），单靠 NRMSE 分不清谁错了。
破解钥匙是知识表 2 的"参数-曲线段映射"：voff 管左右平移、u0 管高度斜率，
写进 prompt 让 LLM 分段归因。这是"专家知识进 prompt"的第一次实战。

图结构与 09 相同：simulate → evaluate → decide → propose(LLM) → simulate
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
from src.tools.sim_tools import run_transfer2  # noqa: E402

load_dotenv(ROOT / ".env")
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
           "all_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)  # WSL 代理陷阱（任务卡09踩坑记录）
client = OpenAI(base_url="https://api.deepseek.com",
                api_key=os.getenv("DEEPSEEK_API_KEY"), timeout=60)

SAMPLE_VG = [-4, -3, -2.6, -2.4, -2.3, -2.2, -2.1, -2, -1.9, -1.8,
             -1.5, -1, 0, 1, 2]  # 过渡区加密：观测分辨率决定提取精度
CONVERGE_TOL = 0.02

# 知识表 2 的映射，原文进 prompt（专家知识的第一次实战投喂）
PARAM_KNOWLEDGE = """参数-曲线映射（专家经验，分段归因的钥匙）：
- voff 控制曲线左右平移：Id 起流点的栅压位置。voff 越负，起流越晚（曲线右移）。只看"在哪起流"，不看高度。
- u0 控制曲线高度/斜率：线性区 Id 近似正比于 u0。只影响"多高"，不影响"在哪起流"。"""


class S(TypedDict):
    target_vg: np.ndarray
    target_id: np.ndarray
    trial_vg: np.ndarray
    trial_id: np.ndarray
    params: dict            # {"voff": float, "u0": float}
    rmse_hist: list
    params_hist: list
    best_params: dict       # 历史最优（交卷交这张）
    best_rmse: float
    iter: int
    max_iter: int
    log: list


def _sample(vg: np.ndarray, y: np.ndarray) -> dict:
    return {f"Vg={v}": round(float(y[np.argmin(np.abs(vg - v))]), 5) for v in SAMPLE_VG}


def simulate(state: S) -> dict:
    p = state["params"]
    vg, idv = run_transfer2(p["voff"], p["u0"], tag=f"iter{state['iter']}")
    return {"trial_vg": vg, "trial_id": idv}


def evaluate(state: S) -> dict:
    r = nrmse(state["trial_id"], state["target_id"])
    best_p, best_r = state.get("best_params"), state.get("best_rmse")
    if best_r is None or r < best_r:
        best_p, best_r = dict(state["params"]), r
    p = state["params"]
    return {
        "rmse_hist": state["rmse_hist"] + [r],
        "params_hist": state["params_hist"] + [dict(p)],
        "best_params": best_p,
        "best_rmse": best_r,
        "log": state["log"] + [f"iter{state['iter']}: voff={p['voff']:.4f} u0={p['u0']:.4f}, NRMSE={r:.2%}"
                               + ("  ← 新最优" if best_p == p else "")],
    }


def route(state: S) -> str:
    if state["rmse_hist"][-1] < CONVERGE_TOL:
        return END
    if state["iter"] >= state["max_iter"]:
        return END
    return "propose"


def propose(state: S) -> dict:
    hist = "\n".join(
        f"  voff={p['voff']:.4f} u0={p['u0']:.4f} → NRMSE={r:.2%}"
        for p, r in zip(state["params_hist"], state["rmse_hist"])
    )
    cur = state["params"]
    prompt = f"""你是 GaN HEMT 建模工程师，正在同时提取两个参数：voff（阈值电压）与 u0（低场迁移率）。
器件线性区转移特性（Vd=1V）实测（Vg: Id/A）：
{json.dumps(_sample(state["target_vg"], state["target_id"]))}
当前参数 voff={cur["voff"]:.4f}, u0={cur["u0"]:.4f} 的仿真：
{json.dumps(_sample(state["trial_vg"], state["trial_id"]))}
历史（参数 → NRMSE，越小越好）：
{hist}
{PARAM_KNOWLEDGE}
策略要求（铁律）：**每轮只改一个参数**（坐标下降法）——先用起流点位置定 voff（u0 冻结），
voff 到位后再调 u0（voff 冻结），如此交替。同时改两个参数会让误差无法归因，严禁。
voff 判读：起流点（Id 明显脱离 0 处）≈ voff + 0.1~0.2V 的亚阈值摆幅，别把起流点本身当 voff。
步进减半逼近，不重复历史值。
只输出 JSON：{{"voff": 数值, "u0": 数值, "reason": "一句话"}}"""
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0,
    )
    text = resp.choices[0].message.content
    m = re.search(r"\{[^{}]*\}", text, re.S)
    new = dict(cur)
    reason = "解析失败，保持"
    if m:
        try:
            obj = json.loads(m.group(0))
            new["voff"] = float(obj.get("voff", cur["voff"]))
            new["u0"] = float(obj.get("u0", cur["u0"]))
            reason = obj.get("reason", "?")
        except (json.JSONDecodeError, KeyError, ValueError):
            reason = "JSON 解析失败，保持当前值"
    return {
        "params": new,
        "iter": state["iter"] + 1,
        "log": state["log"] + [f"  LLM 提议 voff={new['voff']}, u0={new['u0']} —— {reason}"],
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
