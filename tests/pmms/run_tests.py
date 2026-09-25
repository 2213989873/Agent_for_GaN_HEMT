# -*- coding: utf-8 -*-
"""PmmsSession 单元测试（mock server 对拍）。

判据（评审预登记）：
1. mock server 单元测试通过；
2. 计数器读数与实际调用次数一致（含 BUSY 重试：mock 侧 JSONL 行数对拍）。

运行：python tests/pmms/run_tests.py
"""
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mcp import StdioServerParameters  # noqa: E402
from src.pmms import McpCallLedger, PmmsSession, parse_result_text  # noqa: E402

MOCK = Path(__file__).parent / "mock_pmms_server.py"


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return cond


async def main() -> int:
    passed = True
    tmp = Path(tempfile.mkdtemp(prefix="pmms_mock_"))

    # ---- 纯函数：文本解析器 ----
    ok, code, kind = parse_result_text("参数设置成功")
    passed &= check("parse: 成功文本", (ok, code, kind) == (True, None, None))
    ok, code, kind = parse_result_text("错误：Tool 执行失败，错误码：4，错误信息：模型未加载")
    passed &= check("parse: 业务错误码4", (ok, code, kind) == (False, 4, "business"))
    ok, code, kind = parse_result_text("错误：参数无效")
    passed &= check("parse: 异常型文本", (ok, code, kind) == (False, None, "exception"))
    ok, code, kind = parse_result_text("错误：Tool 执行失败，错误码：9，错误信息：另一个操作进行中，请稍后重试")
    passed &= check("parse: BUSY=9", (ok, code, kind) == (False, 9, "business"))

    # ---- 会话层：mock server ----
    server_log = tmp / "server_calls.jsonl"
    ledger = McpCallLedger(tmp / "client_ledger.jsonl")
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(MOCK), str(server_log)])
    async with PmmsSession(params, ledger, job_poll_interval=0.1) as s:
        # echo
        r = await s.call("echo", {"param_name": "voff", "param_value": "-2.0"})
        passed &= check("echo 成功+dict通道", r.ok and "voff" in r.text, r.text[:60])

        # BUSY 退避：前 2 次 BUSY，第 3 次成功
        t0 = time.monotonic()
        r = await s.call("busy_flaky", {"x": 1})
        dt = time.monotonic() - t0
        passed &= check("BUSY 退避后成功", r.ok and r.attempts == 3,
                        f"attempts={r.attempts} elapsed={dt:.2f}s")
        passed &= check("BUSY 退避间隔(0.5+1.0)", dt >= 1.4, f"elapsed={dt:.2f}s")

        # BUSY 耗尽
        s2 = s  # 缩短重试上限做快速耗尽
        old = s2.busy_max_retries
        s2.busy_max_retries = 3
        r = await s.call("busy_forever", {})
        s2.busy_max_retries = old
        passed &= check("BUSY 重试耗尽报错", (not r.ok) and r.error_code == 9
                        and r.error_kind == "business(busy_exhausted)"
                        and r.attempts == 4, f"attempts={r.attempts}")

        # 业务错误 / 异常型
        r = await s.call("biz_fail", {})
        passed &= check("业务错误码4透传", (not r.ok) and r.error_code == 4
                        and r.error_kind == "business")
        r = await s.call("exc_fail", {})
        passed &= check("异常型透传", (not r.ok) and r.error_code is None
                        and r.error_kind == "exception")

        # 异步 Job 轮询
        jr = await s.run_job("start_job", {}, timeout_s=30)
        passed &= check("Job 轮询至 DONE", jr.ok and jr.status == "DONE"
                        and jr.job_id == "11111111-2222-3333-4444-555555555555"
                        and jr.progress == 100,
                        f"status={jr.status} progress={jr.progress}")

    # ---- 计数对拍：client ledger 行数 == mock server 侧行数 ----
    client_lines = (tmp / "client_ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    server_lines = server_log.read_text(encoding="utf-8").strip().splitlines()
    passed &= check("计数器==实际调用次数",
                    len(client_lines) == len(server_lines),
                    f"client={len(client_lines)} server={len(server_lines)}")
    row = json.loads(client_lines[0])
    passed &= check("审计日志字段齐全",
                    all(k in row for k in ("seq", "ts", "tool", "args", "sha256", "ok")),
                    json.dumps(row, ensure_ascii=False)[:120])

    print("\n===== " + ("ALL PASS" if passed else "SOME FAILED") + " =====")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
