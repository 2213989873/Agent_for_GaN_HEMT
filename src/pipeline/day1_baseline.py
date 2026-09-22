"""T1 冒烟 + 计数验证（作战手册 T1 代码化，测试日直接跑）

动作（手册 T1 三条）：
  1. 默认卡全网格仿真存基准 csv——全天所有 NRMSE 的对拍基准
     （data/sim/day1_default_transfer.csv / day1_default_output.csv）；
  2. 记录单次仿真耗时 t_sim（决定全天仿真预算，手册 §3）；
  3. 确认红线计数器工作（本地/MCP 两种链路均支持）。

用法：
  python src/pipeline/day1_baseline.py              # 本地链路
  python src/pipeline/day1_baseline.py --via-mcp    # MCP 链路（测试日形态）
"""
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.qa_loop import DEFAULTS  # noqa: E402
from src.tools.interface import close_session, get_session  # noqa: E402


def main() -> None:
    via_mcp = "--via-mcp" in sys.argv
    sess = get_session(via_mcp)
    h = sess.select_model("asmhemt")
    sess.reset_count()
    sess.set_params(h, dict(DEFAULTS))
    print(f"T1 冒烟（链路 {'MCP' if via_mcp else '本地直连'}，默认卡 {DEFAULTS}）")
    for form in ("dc_transfer", "dc_output"):
        t0 = time.time()
        y = sess.run_simulation(h, {"form": form, "tag": "day1"})
        dt = time.time() - t0
        p = ROOT / "data" / "sim" / f"day1_default_{form.replace('dc_', '')}.csv"
        np.savetxt(p, np.asarray(y))
        print(f"  {form}: {len(y)} 点 → {p.name}，t_sim={dt:.2f}s，峰值 {np.abs(y).max():.4g}")
    n = sess.get_call_count()
    print(f"红线计数器读数: {n}（应为 2：{'✅' if n == 2 else '❌'}）")
    close_session()


if __name__ == "__main__":
    main()
