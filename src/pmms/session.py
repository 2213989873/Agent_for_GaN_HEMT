# -*- coding: utf-8 -*-
"""PmmsSession：PMMS MCP stdio 客户端包装层（M7 子任务1）。

设计依据（全部来自 docs/pmms/MCP_API.md / MCP_INTEGRATION.md 原文）：
- 返回值全是人可读文本（content[0].text）；失败也是 isError:false。
  业务错误前缀：``错误：Tool 执行失败，错误码：<n>，错误信息：<msg>``
  调用异常前缀：``错误：<描述>``
- BUSY=9：server 单 session 锁，PMMS 不做自动重试，客户端须指数退避
  （0.5s 起、~10s 封顶、连续 30 次后报错）。
- 异步 Job：start_optimize/start_qa 立即返回 job_id；get_job_status 轮询，
  job_status 0=RUNNING 1=DONE 2=FAILED 3=CANCELLED；轮询超时建议 5–30min。
- 红线计数：PMMS 无内置计数器，本层对每次真实 wire 调用（含 BUSY 重试）
  落一行 JSONL 审计日志（时间戳/工具名/参数/返回哈希/解析结果）。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("pmms.session")

# ---------------------------------------------------------------- 文本解析

_BIZ_RE = re.compile(r"错误：Tool 执行失败，错误码：(\d+)，错误信息：(.*)", re.S)
_EXC_RE = re.compile(r"错误：(?!Tool 执行失败)(.*)", re.S)
_JOB_ID_RE = re.compile(r"Job ID:\s*([0-9A-Za-z\-]+)")
_JOB_STATUS_RE = re.compile(r"Job 状态:\s*(\w+)")
_JOB_PROGRESS_RE = re.compile(r"进度:\s*(\d+)%")

BUSY_CODE = 9
JOB_STATUS_MAP = {"RUNNING": 0, "DONE": 1, "FAILED": 2, "CANCELLED": 3}


@dataclass
class ToolResult:
    """一次逻辑调用的最终结果（BUSY 重试已内含）。"""

    ok: bool
    text: str
    error_code: int | None = None     # 业务错误码；无错误/异常型为 None
    error_kind: str | None = None     # 'business' | 'exception' | None
    wire_calls: int = 1               # 本次逻辑调用实际消耗的 wire 次数（含 BUSY 重试）
    attempts: int = 1                 # 同上（别名语义，便于审计可读性）


@dataclass
class JobResult:
    ok: bool
    job_id: str | None
    status: str | None                # DONE / FAILED / CANCELLED / TIMEOUT
    progress: int | None
    text: str                         # 最后一次 get_job_status 的原文


def parse_result_text(text: str) -> tuple[bool, int | None, str | None]:
    """解析 PMMS 返回文本 → (ok, error_code, error_kind)。

    成功文本不以"错误："开头；业务错误带错误码；调用异常无错误码。
    """
    m = _BIZ_RE.search(text)
    if m:
        return False, int(m.group(1)), "business"
    m = _EXC_RE.search(text)
    if m:
        return False, None, "exception"
    return True, None, None


# ---------------------------------------------------------------- 计数+审计

class McpCallLedger:
    """红线计数与审计日志：每次真实 wire 调用落一行 JSONL。

    判据（评审预登记）：计数器读数 == 实际 MCP 调用次数（含每次 BUSY 重试）。
    """

    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    def record(self, tool: str, args: dict[str, Any] | None, text: str,
               ok: bool, error_code: int | None) -> int:
        self._count += 1
        row = {
            "seq": self._count,
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "args": args or {},
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "ok": ok,
            "error_code": error_code,
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return self._count


# ---------------------------------------------------------------- 会话本体

class PmmsSession:
    """PMMS MCP stdio 会话：dict 通道 + BUSY 退避 + Job 轮询。

    用法：
        params = StdioServerParameters(command=..., args=[...])
        async with PmmsSession(params, ledger) as s:
            res = await s.call("set_param", {...})
    """

    def __init__(
        self,
        server_params: StdioServerParameters,
        ledger: McpCallLedger,
        *,
        init_timeout_s: float = 120.0,
        busy_max_retries: int = 30,
        busy_initial_delay: float = 0.5,
        busy_max_delay: float = 10.0,
        job_poll_interval: float = 2.0,
        job_timeout_s: float = 1800.0,
    ):
        self._params = server_params
        self.ledger = ledger
        self.init_timeout_s = init_timeout_s
        self.busy_max_retries = busy_max_retries
        self.busy_initial_delay = busy_initial_delay
        self.busy_max_delay = busy_max_delay
        self.job_poll_interval = job_poll_interval
        self.job_timeout_s = job_timeout_s
        self._stdio_cm = None
        self._session_cm = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "PmmsSession":
        self._stdio_cm = stdio_client(self._params)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write,
                                         read_timeout_seconds=self.init_timeout_s)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        logger.info("PmmsSession initialize OK")
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(*exc)
        if self._stdio_cm is not None:
            await self._stdio_cm.__aexit__(*exc)
        self._session = None

    # ---------------- 基础调用（含 BUSY 退避） ----------------

    async def call(self, tool: str, args: dict[str, Any] | None = None) -> ToolResult:
        """一次逻辑调用；BUSY 时指数退避重试，每次 wire 调用都计数。"""
        assert self._session is not None, "session not started"
        delay = self.busy_initial_delay
        attempts = 0
        while True:
            attempts += 1
            raw = await self._session.call_tool(tool, args or {})
            text = "".join(
                getattr(c, "text", "") for c in raw.content
            )
            ok, code, kind = parse_result_text(text)
            self.ledger.record(tool, args, text, ok, code)
            if ok or code != BUSY_CODE:
                return ToolResult(ok=ok, text=text, error_code=code,
                                  error_kind=kind, wire_calls=attempts,
                                  attempts=attempts)
            if attempts > self.busy_max_retries:
                return ToolResult(ok=False, text=text, error_code=code,
                                  error_kind="business(busy_exhausted)",
                                  wire_calls=attempts, attempts=attempts)
            logger.warning("BUSY on %s (attempt %d), retry in %.1fs",
                           tool, attempts, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, self.busy_max_delay)

    # ---------------- 异步 Job ----------------

    async def run_job(
        self,
        start_tool: str,
        start_args: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> JobResult:
        """start_* → 轮询 get_job_status 直到非 RUNNING。

        timeout_s 默认取 job_timeout_s（1800s，依据 API §12 "建议 5-30 分钟"）。
        """
        timeout_s = timeout_s if timeout_s is not None else self.job_timeout_s
        start = await self.call(start_tool, start_args)
        if not start.ok:
            return JobResult(False, None, None, None,
                             f"start failed: {start.text}")
        m = _JOB_ID_RE.search(start.text)
        if not m:
            return JobResult(False, None, None, None,
                             f"job_id not found in: {start.text}")
        job_id = m.group(1)

        t0 = time.monotonic()
        last_text = ""
        while True:
            await asyncio.sleep(self.job_poll_interval)
            st = await self.call("get_job_status", {"job_id": job_id})
            last_text = st.text
            if not st.ok:
                return JobResult(False, job_id, None, None, last_text)
            sm = _JOB_STATUS_RE.search(last_text)
            pm = _JOB_PROGRESS_RE.search(last_text)
            status = sm.group(1) if sm else None
            progress = int(pm.group(1)) if pm else None
            code = JOB_STATUS_MAP.get(status or "", 0)
            if code != 0:  # 非 RUNNING → 终态
                return JobResult(code == 1, job_id, status, progress, last_text)
            if time.monotonic() - t0 > timeout_s:
                return JobResult(False, job_id, "TIMEOUT", progress, last_text)
