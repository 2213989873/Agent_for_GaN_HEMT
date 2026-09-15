"""任务 02 配套：FastMCP stdio client demo

用 Client("02_mcp_server.py") 以 stdio 方式拉起同目录的 MCP server 子进程，
先 list_tools() 打印工具清单，再依次调用 greet 和 calc。

注意：FastMCP Client 是异步的，必须用 async with + asyncio.run 包一层。

运行：python examples/02_mcp_client.py
"""
import asyncio
from pathlib import Path

from fastmcp import Client

SERVER_PATH = Path(__file__).resolve().parent / "02_mcp_server.py"

# JSON Schema 类型名 -> Python 类型名，让打印的参数签名更像 Python 函数
_TYPE_MAP = {"string": "str", "number": "float", "integer": "int", "boolean": "bool"}


def format_signature(input_schema: dict) -> str:
    """把工具的 JSON Schema 参数定义格式化成 Python 风格签名，如 (name: str)。"""
    props = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    parts = []
    for name, info in props.items():
        py_type = _TYPE_MAP.get(info.get("type", ""), "any")
        default = "" if name in required else " = ..."
        parts.append(f"{name}: {py_type}{default}")
    return "(" + ", ".join(parts) + ")"


async def main() -> None:
    # Client 收到 .py 路径会自动用 stdio 传输拉起 server 子进程（用当前 python 解释器），
    # 进入 async with 时完成 initialize 握手，退出时关闭子进程
    async with Client(SERVER_PATH) as client:
        # ---------- 工具清单 ----------
        print("===== 工具清单 =====")
        for t in await client.list_tools():
            desc = t.description.splitlines()[0] if t.description else "(无描述)"
            print(f"- {t.name}{format_signature(t.input_schema)}")
            print(f"    {desc}")

        # ---------- 调用1：greet ----------
        print("\n===== 调用1: greet =====")
        r1 = await client.call_tool("greet", {"name": "小明"})
        print(r1.content[0].text)

        # ---------- 调用2：calc ----------
        print("\n===== 调用2: calc =====")
        r2 = await client.call_tool("calc", {"expression": "120 * 2"})
        print(r2.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
