"""任务 02：FastMCP 最小 MCP server demo

两个工具：greet（中文问候）、calc（ast 白名单安全计算，禁止 eval）。
用 stdio 方式运行（FastMCP 默认），供 MCP client / LLM 宿主程序通过标准输入输出接入。

注意：每个工具的 docstring 会被 MCP 当作工具描述暴露给 client 和 LLM，
描述质量直接决定 LLM 会不会正确选用工具，务必写清楚适用场景、参数和返回值。

运行：python examples/02_mcp_server.py（进程驻留，等待 stdio 上的 JSON-RPC 请求）
"""
import ast
import operator

from fastmcp import FastMCP

# 创建 MCP server 实例，名字会随 initialize 握手暴露给 client
mcp = FastMCP("demo-modeling-server")


# ---------- 工具一：中文问候 ----------
@mcp.tool
def greet(name: str) -> str:
    """向指定的人发送一句中文问候。

    适用场景：需要跟用户打招呼、确认本服务在线、或做 MCP 联调测试时调用。

    Args:
        name: 对方的名字或称呼，例如 "小明"、"郑工程师"。

    Returns:
        一句包含对方名字的中文问候语。

    示例:
        greet("小明") -> "你好，小明！我是 demo-modeling-server，很高兴见到你。"
    """
    return f"你好，{name}！我是 demo-modeling-server，很高兴见到你。"


# ---------- 工具二：安全计算器（ast 白名单，禁止 eval） ----------
_BIN_OPS = {  # 二元运算白名单：只允许 + - * /
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}  # 一元 +x / -x


def _eval_node(node: ast.AST) -> float:
    """递归求值 AST 节点；遇到白名单外的语法直接抛 ValueError。"""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):  # 数字字面量（布尔值按非法处理）
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"只允许数字，收到: {node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    # 括号由语法树结构天然体现，无需单独处理
    raise ValueError(f"表达式含不允许的语法: {ast.dump(node)}")


@mcp.tool
def calc(expression: str) -> float:
    """安全地计算一个四则运算表达式，返回数值结果。

    适用场景：任何算术计算都必须调用本工具，不要口算。
    支持的语法：数字（整数或小数）、括号、加减乘除（+ - * /）。
    不支持：变量、函数调用、乘方、取余等其它语法，传入会被拒绝并报错。

    Args:
        expression: 要计算的表达式字符串，例如 "120 * 2"、"(3.5 + 1) / 2"。

    Returns:
        计算结果（float）。

    示例:
        calc("120 * 2") -> 240.0
    """
    return float(_eval_node(ast.parse(expression, mode="eval")))


if __name__ == "__main__":
    mcp.run()  # 默认 stdio 传输：从标准输入读 JSON-RPC 请求，往标准输出写响应
