"""工具接口层（agent架构设计 v1.1 §3）：六类接口，签名不变只换实现

评审修订（2026-09-20，v1.1）：参数一律走 dict 通道（set_params + run_simulation），
参数名永不进工具签名——卡14 的 run_iv_simulation(voff,u0,...) 演示签名已废止。

两种实现（同签名，M4 落地）：
  LocalSession —— 本地 ngspice 直连（M1-M3 默认链路）；
  McpSession   —— 经 mock/真 Primarius MCP Server。长连接：后台线程跑专属
                  asyncio loop，fastmcp Client 一次 __aenter__ 复用到 close——
                  卡14 "每次调用重启 stdio 子进程"模式废止（1500+ 次仿真不可行）。
                  测试日只换 MCP_SERVER_PATH 即切真接口（HTTP/SSE 传输同理）。
会话单例：get_session(via_mcp) —— 状态里不放不可序列化对象（main_graph 约定）。
"""
import asyncio
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.tools import sim_tools as st  # noqa: E402

DEVICE_DIR = ROOT / "data" / "devices"
MCP_SERVER_PATH = ROOT / "src" / "tools" / "mcp_server_mock.py"

# 数据形态注册表：form -> (目标文件模板, 解析方式)
FORM_FILES = {
    "dc_transfer": "{dev}/transfer_{dev}.csv",   # 2 列：Vg, i(vd)（取正）
    "dc_output": "{dev}/dc_output_{dev}.csv",    # 847 点嵌套扫描：Vd, i(vd)（取正拍平）
    "cv_gg": "{dev}/cv_gg_{dev}.csv",            # 4 列：t, v(g), t, i(vg)（C=-i/1e6）
}

# 卡07 铁律：rdsmod=1 是接入电阻/陷阱挂载总开关，所有试算卡必须带
MODEL_SWITCHES = {"rdsmod": 1}


@dataclass
class Handle:
    """模型句柄：选型结果 + 当前参数卡（dict 通道）。"""
    model: str = "asmhemt"
    switches: dict = field(default_factory=lambda: dict(MODEL_SWITCHES))
    params: dict = field(default_factory=dict)


class BaseSession:
    """六类接口中与传输无关的五类：模型选型/参数操作/默认值/数据I/O/QA检查。
    run_simulation（拟合执行）与红线计数（会话管理）由子类按传输方式实现。"""

    is_mcp = False

    def __init__(self):
        self.handle: Handle | None = None

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
        if form == "cv_gg":
            # 准静态 C-V：4 列 t, v(g), t, i(vg)；C=-i/slope；丢首尾各5点（卡08）
            d = d[5:-5]
            return {"path": str(p), "n_points": int(len(d)),
                    "x": d[:, 1], "y": -d[:, 3] / 1e6}
        return {"path": str(p), "n_points": int(len(d)),
                "x": d[:, 0], "y": -d[:, 1]}   # SPICE 电流符号约定取正

    # ---- 5 QA检查 ----
    def qa_check(self, values: dict, curves: dict | None = None,
                 level: str = "param") -> dict:
        from src.agent import qa_validator
        v = qa_validator.param_violations(values)
        if curves and level in ("curve", "both"):
            v += qa_validator.curve_violations(curves)
        return {"pass": not v, "violations": v}

    # 子类必须实现：run_simulation / get_call_count / reset_count / close


class LocalSession(BaseSession):
    """mock 实现：本地 ngspice 直连。"""

    is_mcp = False

    def __init__(self):
        super().__init__()
        self.n_calls = 0

    # ---- 6 会话管理 ----
    def get_call_count(self) -> int:
        return self.n_calls

    def reset_count(self) -> None:
        self.n_calls = 0

    def close(self) -> None:
        pass

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
        if form == "cv_gg":
            # 自适应步长 → interp 到目标网格（sim_spec["grid"] 由调用方给）
            vg, c = st.run_cv_params(p, tag)
            return np.interp(sim_spec["grid"], vg, c)
        raise ValueError(f"未支持的形态 {form}（pulse 为后续里程碑）")


class _McpLink:
    """后台线程 + 专属 asyncio loop 上的长连接 fastmcp Client。

    一次 __aenter__ 后所有 call_tool 复用同一 stdio 子进程；
    所有协程经 run_coroutine_threadsafe 调度到该 loop，避免跨 loop 绑定冲突。"""

    def __init__(self, server_path: Path):
        from fastmcp import Client
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever,
                                        daemon=True, name="mcp-link")
        self._thread.start()
        self._client = Client(Path(server_path))
        self._call(self._client.__aenter__(), timeout=60)

    def _call(self, coro, timeout: float = 300.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def call_tool(self, name: str, args: dict):
        return self._call(self._client.call_tool(name, args))

    def close(self) -> None:
        try:
            self._call(self._client.__aexit__(None, None, None), timeout=30)
        except Exception:                            # noqa: BLE001（收尾容错）
            pass
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=10)


class McpSession(BaseSession):
    """经 MCP Server 的会话：仿真与红线计数走 server 工具（计数 server 端落盘）。"""

    is_mcp = True

    def __init__(self, server_path: Path | None = None):
        super().__init__()
        self._link = _McpLink(server_path or MCP_SERVER_PATH)

    # ---- 6 会话管理 ----
    def get_call_count(self) -> int:
        r = self._link.call_tool("get_call_count", {})
        return int(json.loads(r.content[0].text)["count"])

    def reset_count(self) -> None:
        self._link.call_tool("reset_count", {})

    def close(self) -> None:
        self._link.close()

    # ---- 4 拟合执行 ----
    def run_simulation(self, handle: Handle, sim_spec: dict) -> np.ndarray:
        """spec 只传 form/grid（JSON 可序列化）；tag 由 server 端按调用序号自造。"""
        spec = {"form": sim_spec["form"]}
        if "grid" in sim_spec:                       # cv_gg 目标网格 → list
            spec["grid"] = np.asarray(sim_spec["grid"], float).tolist()
        r = self._link.call_tool("run_simulation",
                                 {"params": dict(handle.params), "sim_spec": spec})
        return np.array(json.loads(r.content[0].text)["id"])


_SESSION: BaseSession | None = None


def get_session(via_mcp: bool = False) -> BaseSession:
    """会话单例：main_graph 各节点共享；resume 时惰性重建；模式切换关旧建新。"""
    global _SESSION
    if _SESSION is not None and _SESSION.is_mcp != via_mcp:
        _SESSION.close()
        _SESSION = None
    if _SESSION is None:
        _SESSION = McpSession() if via_mcp else LocalSession()
    return _SESSION
