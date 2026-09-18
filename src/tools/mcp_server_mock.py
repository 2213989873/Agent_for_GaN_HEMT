"""任务卡 14：mock 组委会 MCP Server —— Primarius Modeling 的本地替身

模拟赛题真实接口形态：Agent 不直接碰仿真器，一切经 MCP 工具远程调用。
本 server 包装本地 ngspice（run_output_selfheat_params），并做**调用计数持久化**
（写文件，因为 stdio 模式下 server 子进程每次调用可能重启）——
赛题红线"每器件 MCP 调用 ≥10 次"的计数机制预演。

运行（stdio 驻留）：python src/tools/mcp_server_mock.py
"""
import json
import sys
from pathlib import Path

from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.tools.sim_tools import SIM_DIR, run_output_selfheat_params  # noqa: E402

COUNT_FILE = SIM_DIR / ".mcp_call_count"

mcp = FastMCP("mock-primarius-modeling")


def _bump() -> int:
    """调用计数 +1 并持久化（赛题红线统计口径）。"""
    n = int(COUNT_FILE.read_text().strip() or 0) if COUNT_FILE.exists() else 0
    n += 1
    COUNT_FILE.write_text(str(n))
    return n


@mcp.tool
def run_iv_simulation(voff: float, u0: float,
                      rontr1: float | None = None,
                      rth0: float | None = None) -> str:
    """对 ASM-HEMT 模型卡执行 DC 输出特性仿真（847 点嵌套扫描：
    Vd 0→12V 步 0.1 × Vg -1.5→1.5V 步 0.5），返回漏极电流数组。

    适用场景：GaN HEMT 紧凑模型参数提取——给定一组候选参数，
    获取对应的 I-V 曲线数据用于与实测对拍。

    Args:
        voff: 阈值电压 (V)，D-mode 典型 -4 ~ -0.5。
        u0: 低场迁移率 (m²/V·s)，典型 0.1 ~ 0.25。
        rontr1: 陷阱耦合强度（可选，给定时自动启用 trapmod=2）。
        rth0: 热阻 K/W（可选，给定时启用自热模型）。

    Returns:
        JSON 字符串：{"id": [847 个电流值(A)]，"mcp_call": 本次调用序号}。
    """
    n = _bump()
    params = {"voff": voff, "u0": u0}
    if rontr1 is not None:
        params["rontr1"] = rontr1
    if rth0 is not None:
        params["rth0"] = rth0
    idv = run_output_selfheat_params(params, tag=f"mcp{n}")
    return json.dumps({"id": idv.tolist(), "mcp_call": n})


@mcp.tool
def get_call_count() -> str:
    """查询本会话对 run_iv_simulation 的累计调用次数（赛题红线 ≥10 次/器件）。"""
    n = int(COUNT_FILE.read_text().strip() or 0) if COUNT_FILE.exists() else 0
    return json.dumps({"mcp_call_count": n})


if __name__ == "__main__":
    mcp.run()  # stdio 传输
