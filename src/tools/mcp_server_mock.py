"""M4：mock 组委会 MCP Server v2 —— v1.1 接口的 dict 通道版

评审修订落地（agent架构设计 v1.1 §3）：参数一律走 dict 通道，
工具签名永不随参数空间膨胀——v1 的 run_iv_simulation(voff,u0,...) 已废止。

工具清单（六类接口的 server 侧）：
  run_simulation(params: dict, sim_spec: dict)  —— 拟合执行（唯一仿真入口）
  get_call_count() / reset_count()              —— 会话管理（红线计数，文件持久化）

计数口径：仅 run_simulation 计数（赛题红线=仿真调用）；
stdio 模式 server 可能重启，计数落盘 data/sim/.mcp_call_count。

运行（stdio 驻留）：python src/tools/mcp_server_mock.py
"""
import json
import sys
from pathlib import Path

from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
from src.tools import sim_tools as st  # noqa: E402
from src.tools.sim_tools import SIM_DIR  # noqa: E402

COUNT_FILE = SIM_DIR / ".mcp_call_count"

mcp = FastMCP("mock-primarius-modeling")


def _peek() -> int:
    return int(COUNT_FILE.read_text().strip() or 0) if COUNT_FILE.exists() else 0


def _bump() -> int:
    n = _peek() + 1
    COUNT_FILE.write_text(str(n))
    return n


@mcp.tool
def run_simulation(params: dict, sim_spec: dict) -> str:
    """对 ASM-HEMT 模型卡执行仿真并返回漏极电流/电容数组。

    Args:
        params: 模型参数 dict（如 {"voff": -2.0, "u0": 0.17, "tbar": 2.5e-8}）；
                参数名/数量任意，走 dict 通道不进签名。
        sim_spec: 仿真规格 {"form": "dc_transfer"|"dc_output"|"cv_gg",
                            "grid": [可选，cv_gg 形态的目标 Vg 网格]}。

    Returns:
        JSON：{"id": [数组]，"form": ..., "mcp_call": 调用序号}。
    """
    n = _bump()
    form = sim_spec["form"]
    if form == "dc_transfer":
        idv = st.run_transfer_params(params, f"mcp{n}")[1]
    elif form == "dc_output":
        fn = st.run_output_selfheat_params if "rth0" in params else st.run_output_params
        idv = fn(params, f"mcp{n}")
    elif form == "cv_gg":
        vg, c = st.run_cv_params(params, f"mcp{n}")
        idv = np.interp(np.asarray(sim_spec["grid"], float), vg, c)
    else:
        raise ValueError(f"未支持的形态 {form}")
    return json.dumps({"id": np.asarray(idv).tolist(), "form": form, "mcp_call": n})


@mcp.tool
def get_call_count() -> str:
    """查询本会话仿真调用计数（赛题红线核对用）。"""
    return json.dumps({"count": _peek()})


@mcp.tool
def reset_count() -> str:
    """器件提取开始时清零红线计数。"""
    COUNT_FILE.unlink(missing_ok=True)
    return json.dumps({"count": 0})


if __name__ == "__main__":
    mcp.run()
