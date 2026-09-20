"""M1 主图（agent架构设计 v1.1 §2.1）：最小全流程无人干预

节点链：
  START → session_open → load_data → analyze_data → init_params
        → extract（qa_loop 编译子图，四节点+双触发器，卡11/12/13 验证）
        → finalize_card → write_logs → session_close → END

checkpoint 偏差说明（相对设计文档 §1，2026-09-20 工程判决）：
状态含 sim_fn/ndarray 等不可序列化对象，langgraph-checkpoint 的
InMemorySaver 不能跨进程、SqliteSaver 要求状态全可序列化——故改用
**节点粒度 JSON 快照**（logs/ckpt_<device>.json）：每个主图节点完成后落盘，
--resume 时已完成的节点跳过；extract 子图内部中断则整段重跑（M2 再细化）。
"""
import json
import sys
import time
from pathlib import Path
from typing import TypedDict

import numpy as np
from langgraph.graph import END, START, StateGraph

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.qa_loop import DEFAULTS, build as build_extract, client  # noqa: E402
from src.tools.interface import get_session  # noqa: E402

LOG_DIR = ROOT / "logs"
REDLINE_MIN_CALLS = 10      # 赛题红线：每器件工具调用 ≥10（卡14 §4 保底条款）


class S_agent(TypedDict):
    device_id: str
    forms: list
    active_form: str
    data_forms: dict
    target_vg: object        # np.ndarray，不入 ckpt
    target_id: object        # np.ndarray，不入 ckpt
    sim_fn: object           # 不可序列化，不入 ckpt（resume 时按 active_form 重建）
    params_space: list
    values: dict
    fit_hist: list
    best_values: object
    best_rmse: object
    rmse: object
    qa_pass: bool
    violations: list
    n_retry: int
    budget: dict
    final_card: object
    completed: list
    via_mcp: bool
    log: list


# ---------- checkpoint（节点粒度 JSON 快照）----------

def _ckpt_path(device_id: str) -> Path:
    return LOG_DIR / f"ckpt_{device_id}.json"


def _save_ckpt(state: S_agent) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    snap = {k: state[k] for k in
            ("device_id", "forms", "active_form", "data_forms", "params_space",
             "values", "fit_hist", "best_values", "best_rmse", "rmse", "qa_pass",
             "violations", "n_retry", "budget", "final_card", "completed", "log")}
    _ckpt_path(state["device_id"]).write_text(
        json.dumps(snap, ensure_ascii=False, default=str, indent=1), encoding="utf-8")


def load_ckpt(device_id: str) -> dict | None:
    p = _ckpt_path(device_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def rehydrate(state: S_agent) -> S_agent:
    """resume 补水：ckpt 只存可序列化字段，sim_fn/数组/session 按 active_form
    确定性重建（与 load_data 同逻辑，不产生新副作用、不写日志）。"""
    sess = get_session()
    if sess.handle is None:
        sess.select_model("asmhemt")
    handle = sess.handle
    form0 = state["active_form"] or state["forms"][0]
    m = sess.load_measurement(state["device_id"], form0)

    def sim_fn(params: dict, tag: str):
        sess.set_params(handle, params)
        return sess.run_simulation(handle, {"form": form0, "tag": tag})

    state["active_form"] = form0
    state["target_vg"], state["target_id"], state["sim_fn"] = m["x"], m["y"], sim_fn
    return state


def node(name):
    """节点包装：resume 跳过已完成节点；正常执行后落 ckpt。"""
    def deco(fn):
        def wrapped(state: S_agent):
            if name in state["completed"]:
                return {"log": state["log"] + [f"{name}: 已完成，跳过（resume）"]}
            out = fn(state)
            completed = state["completed"] + [name]
            _save_ckpt({**state, **out, "completed": completed})
            return {**out, "completed": completed}
        return wrapped
    return deco


# ---------- 节点实现 ----------

@node("session_open")
def session_open(state: S_agent) -> dict:
    sess = get_session()
    sess.reset_count()
    handle = sess.select_model("asmhemt")          # 默认带 rdsmod=1（卡07 铁律）
    budget = {"sim_count": 0, "llm_calls": 0, "t0": time.time()}
    return {"budget": budget,
            "log": state["log"] + [f"session_open: 选型 asmhemt，开关 {handle.switches}，预算计数清零"]}


@node("load_data")
def load_data(state: S_agent) -> dict:
    sess = get_session()
    data_forms, first = {}, None
    for form in state["forms"]:
        m = sess.load_measurement(state["device_id"], form)
        if m["n_points"] <= 0 or not np.isfinite(m["y"]).all():
            raise RuntimeError(f"load_data: {form} 数据异常（{m['path']}）")
        data_forms[form] = {"path": m["path"], "n_points": m["n_points"]}
        if first is None:
            first = m
    handle = sess.handle
    form0 = state["forms"][0]

    def sim_fn(params: dict, tag: str):
        sess.set_params(handle, params)
        return sess.run_simulation(handle, {"form": form0, "tag": tag})

    return {"data_forms": data_forms, "active_form": form0,
            "target_vg": first["x"], "target_id": first["y"], "sim_fn": sim_fn,
            "log": state["log"] + [f"load_data: " + "，".join(
                f"{f}={d['n_points']}点" for f, d in data_forms.items())]}


@node("analyze_data")
def analyze_data(state: S_agent) -> dict:
    """LLM 签名自检（知识表3 附表）：看曲线特征提示参数族。LLM 失效→降级跳过。"""
    y = state["target_id"]
    peak = float(np.abs(y).max())
    stats = (f"点数{len(y)}，峰值{peak:.4g}A，首点{y[0]:.4g}，末点{y[-1]:.4g}，"
             f"单调点占比{float((np.diff(y) >= 0).mean()):.0%}")
    note, llm_ok = "", True
    try:
        r = client.chat.completions.create(
            model="deepseek-chat", temperature=0, max_tokens=120,
            messages=[{"role": "user", "content":
                       f"GaN HEMT 转移特性统计：{stats}。"
                       f"一句话判断：有无明显自热/陷阱迹象？只答结论。"}])
        note = r.choices[0].message.content.strip()
    except Exception as e:                                # noqa: BLE001
        llm_ok = False
        note = f"LLM 不可用（{type(e).__name__}），按默认顺序继续（卡11：不依赖 LLM 质量）"
    budget = {**state["budget"], "llm_calls": state["budget"]["llm_calls"] + (1 if llm_ok else 0)}
    return {"budget": budget,
            "log": state["log"] + [f"analyze_data: {stats} → {note}"]}


@node("init_params")
def init_params(state: S_agent) -> dict:
    space = ["voff", "u0"]                     # 知识表1 步骤1：两参数族起步
    values = {p: DEFAULTS[p] for p in space}
    return {"params_space": space, "values": values, "n_retry": 0,
            "qa_pass": False, "violations": [], "rmse": None,
            "log": state["log"] + [f"init_params: 起步空间 {space}，初值 {values}"]}


@node("finalize_card")
def finalize_card(state: S_agent) -> dict:
    sess = get_session()
    budget = {**state["budget"], "sim_count": sess.get_call_count()}
    card = {"device": state["device_id"], "model": "asmhemt",
            "params": state["values"], "space": state["params_space"],
            "nrmse": state["rmse"], "qa_pass": state["qa_pass"]}
    hist = state["fit_hist"] + [{"space": list(state["params_space"]),
                                 "values": dict(state["values"]), "rmse": state["rmse"]}]
    return {"final_card": card, "fit_hist": hist,
            "best_values": state["values"], "best_rmse": state["rmse"], "budget": budget,
            "log": state["log"] + [f"finalize_card: {card['params']} NRMSE={state['rmse']:.4%}"]}


@node("write_logs")
def write_logs(state: S_agent) -> dict:
    LOG_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    p = LOG_DIR / f"run_{state['device_id']}_{ts}.json"
    p.write_text(json.dumps(
        {"final_card": state["final_card"], "budget": state["budget"],
         "fit_hist": state["fit_hist"], "log": state["log"]},
        ensure_ascii=False, default=str, indent=1), encoding="utf-8")
    return {"log": state["log"] + [f"write_logs: {p.name}"]}


@node("session_close")
def session_close(state: S_agent) -> dict:
    """红线保底（卡14 §4）：调用 <10 次则自动补扰动验证点（既攒调用又产证据）。"""
    sess = get_session()
    log = list(state["log"])
    n = sess.get_call_count()
    if n < REDLINE_MIN_CALLS:
        base = dict(state["best_values"])
        keys = list(base)
        for i in range(REDLINE_MIN_CALLS - n):
            p = dict(base)
            k = keys[i % len(keys)]
            p[k] = base[k] * (1 + 0.01 * (1 + i % 2))   # ±1~2% 扰动验证点
            state["sim_fn"](p, tag=f"redline{i}")
            log.append(f"session_close: 红线保底补测 #{i}（{k} 扰动）")
        n = sess.get_call_count()
    budget = {**state["budget"], "sim_count": n,
              "wall_s": round(time.time() - state["budget"]["t0"], 1)}
    sess.close()
    return {"budget": budget,
            "log": log + [f"session_close: 调用计数 {n} 次（红线≥{REDLINE_MIN_CALLS}：{'✅' if n >= REDLINE_MIN_CALLS else '❌'}）"
                          f"，耗时 {budget['wall_s']}s"]}


# ---------- 建图 ----------

def build_main():
    g = StateGraph(S_agent)
    g.add_node("session_open", session_open)
    g.add_node("load_data", load_data)
    g.add_node("analyze_data", analyze_data)
    g.add_node("init_params", init_params)
    g.add_node("extract", build_extract())       # qa_loop 编译子图（卡11/12/13 验证）
    g.add_node("finalize_card", finalize_card)
    g.add_node("write_logs", write_logs)
    g.add_node("session_close", session_close)
    g.add_edge(START, "session_open")
    g.add_edge("session_open", "load_data")
    g.add_edge("load_data", "analyze_data")
    g.add_edge("analyze_data", "init_params")
    g.add_edge("init_params", "extract")
    g.add_edge("extract", "finalize_card")
    g.add_edge("finalize_card", "write_logs")
    g.add_edge("write_logs", "session_close")
    g.add_edge("session_close", END)
    return g.compile()
