"""工具接口层（agent架构设计 v1.1 §3）：六类接口，签名不变只换实现

评审修订（2026-09-20，v1.1）：参数一律走 dict 通道（set_params + run_simulation），
参数名永不进工具签名——卡14 的 run_iv_simulation(voff,u0,...) 演示签名已废止。

LocalSession = mock 实现（本地 ngspice 包 sim_tools）；
真 Primarius MCP 到位后写 McpSession，同签名（M4）。
会话单例：get_session() —— 状态里不放不可序列化对象（main_graph 约定）。
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.tools import sim_tools as st  # noqa: E402

DEVICE_DIR = ROOT / "data" / "devices"

# 数据形态注册表：form -> (目标文件模板, 解析方式)
# cv/pulse 为 M3 内容，到时在此加行即可（卡12 sim_fn 解耦模式）
FORM_FILES = {
    "dc_transfer": "{dev}/transfer_{dev}.csv",   # 2 列：Vg, i(vd)（取正）
    "dc_output": "{dev}/dc_output_{dev}.csv",    # 847 点嵌套扫描：Vd, i(vd)（取正拍平）
}

# 卡07 铁律：rdsmod=1 是接入电阻/陷阱挂载总开关，所有试算卡必须带
MODEL_SWITCHES = {"rdsmod": 1}


@dataclass
class Handle:
    """模型句柄：选型结果 + 当前参数卡（dict 通道）。"""
    model: str = "asmhemt"
    switches: dict = field(default_factory=lambda: dict(MODEL_SWITCHES))
    params: dict = field(default_factory=dict)


class LocalSession:
    """mock 实现：本地 ngspice。接口六类与真 MCP 一一对应。"""

    def __init__(self):
        self.n_calls = 0
        self.handle: Handle | None = None

    # ---- 6 会话管理 ----
    def get_call_count(self) -> int:
        return self.n_calls

    def reset_count(self) -> None:
        self.n_calls = 0

    def close(self) -> None:
        pass

    # ---- 2 模型选型 ----
    def select_model(self, name: str = "asmhemt", switches: dict | None = None) -> Handle:
        self.handle = Handle(model=name,
                             switches={**MODEL_SWITCHES, **(switches or {})})
        return self.handle

    # ---- 3 参数操作（dict 通道，参数名不进签名）----
    def set_params(self, handle: Handle, params: dict) -> Handle:
        handle.params.update(params)
        return handle

    def get_defaults(self, name: str = "asmhemt") -> dict:
        from src.agent.qa_loop import DEFAULTS
        return dict(DEFAULTS)

    # ---- 1 数据I/O ----
    def load_measurement(self, device_id: str, form: str) -> dict:
        rel = FORM_FILES[form]
        p = DEVICE_DIR / rel.format(dev=device_id)
        d = np.atleast_2d(np.loadtxt(p))
        return {"path": str(p), "n_points": int(len(d)),
                "x": d[:, 0], "y": -d[:, 1]}   # SPICE 电流符号约定取正

    # ---- 4 拟合执行 ----
    def run_simulation(self, handle: Handle, sim_spec: dict) -> np.ndarray:
        """sim_spec: {"form": ..., "tag": ...}；参数经 handle.params（dict 通道）。"""
        self.n_calls += 1
        form, tag = sim_spec["form"], sim_spec.get("tag", "sess")
        p = dict(handle.params)
        if form == "dc_transfer":
            return st.run_transfer_params(p, tag)[1]
        if form == "dc_output":
            fn = st.run_output_selfheat_params if "rth0" in p else st.run_output_params
            return fn(p, tag)
        raise ValueError(f"未支持的形态 {form}（cv/pulse 为 M3 内容）")

    # ---- 5 QA检查 ----
    def qa_check(self, values: dict, curves: dict | None = None,
                 level: str = "param") -> dict:
        from src.agent import qa_validator
        v = qa_validator.param_violations(values)
        if curves and level in ("curve", "both"):
            v += qa_validator.curve_violations(curves)
        return {"pass": not v, "violations": v}


_SESSION: LocalSession | None = None


def get_session() -> LocalSession:
    """会话单例：main_graph 各节点共享；resume 时惰性重建。"""
    global _SESSION
    if _SESSION is None:
        _SESSION = LocalSession()
    return _SESSION
