"""任务 01b：工具调用 Agent demo（LangGraph 官方 quickstart 的 Graph API 结构）

结构：llm_call 节点（模型决策）+ tool_node 节点（执行工具）+ 条件边循环。
模型用 DeepSeek（OpenAI 兼容接口），工具一查名词手册，工具二做安全计算。

节点图（ASCII）：

  START
    |
    v
  +----------+   条件边 should_continue   +-----------+
  | llm_call | ---- 有 tool_calls -----> | tool_node |
  +----------+                           +-----------+
       ^                                      |
       |----------- 工具返回结果 --------------|
       |
       |---- 无 tool_calls
       v
      END

运行：python examples/01b_tool_agent.py
"""
import ast
import operator
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

ROOT = Path(__file__).resolve().parents[1]  # 仓库根目录（examples/ 的上一级）
GLOSSARY_PATH = ROOT / "docs" / "名词手册.md"

load_dotenv(ROOT / ".env")
api_key = os.getenv("DEEPSEEK_API_KEY", "")
if not api_key or api_key.startswith("sk-在这里"):
    sys.exit("❌ 请先把 .env.example 复制为 .env，并填入真实 DEEPSEEK_API_KEY")


# ---------- 工具一：查名词手册 ----------
@tool
def lookup_glossary(term: str) -> str:
    """在 docs/名词手册.md 中查找名词解释。返回所有包含该词的行；找不到返回"未收录"。"""
    hits = [
        line.strip()
        for line in GLOSSARY_PATH.read_text(encoding="utf-8").splitlines()
        if term.lower() in line.lower()
    ]
    return "\n".join(hits) if hits else "未收录"


# ---------- 工具二：安全计算器（ast 白名单，禁止 eval） ----------
_BIN_OPS = {  # 只允许 + - * /
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}  # 允许 +x / -x


def _eval_node(node: ast.AST) -> float:
    """递归求值 AST 节点；遇到白名单外的语法直接抛错。"""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):  # 数字字面量
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"只允许数字，收到: {node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    # ast.BinOp 的括号由语法树结构天然体现，无需单独处理
    raise ValueError(f"表达式含不允许的语法: {ast.dump(node)}")


@tool
def calc(expression: str) -> str:
    """计算四则运算表达式（只允许数字、括号和 + - * /），例如 "120 * 2"。"""
    try:
        result = _eval_node(ast.parse(expression, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        return f"计算失败: {e}"
    return str(result)


TOOLS = [lookup_glossary, calc]

# ---------- 模型：DeepSeek（OpenAI 兼容接口），绑定工具 ----------
model = init_chat_model(
    "deepseek-chat",
    model_provider="openai",
    base_url="https://api.deepseek.com",
    api_key=api_key,
).bind_tools(TOOLS)

SYSTEM_PROMPT = (
    "你是 GaN HEMT 紧凑模型参数提取助手。"
    "遇到专业名词先调用 lookup_glossary 查名词手册；"
    "需要算术时调用 calc，不要口算。"
    "拿到工具结果后再组织最终回答，用中文简洁作答。"
)


# ---------- 节点与条件边（官方 quickstart 结构） ----------
def llm_call(state: MessagesState) -> dict:
    """模型决策节点：直接回答，或发起工具调用。"""
    response = model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
    return {"messages": [response]}


tool_node = ToolNode(TOOLS)  # 工具执行节点：按 tool_calls 逐个调用并回写 ToolMessage


def should_continue(state: MessagesState) -> str:
    """条件边：最后一条消息带 tool_calls 就去执行工具，否则结束。"""
    last = state["messages"][-1]
    return "tool_node" if last.tool_calls else "end"


builder = StateGraph(MessagesState)
builder.add_node("llm_call", llm_call)
builder.add_node("tool_node", tool_node)

builder.add_edge(START, "llm_call")
builder.add_conditional_edges("llm_call", should_continue, {"tool_node": "tool_node", "end": END})
builder.add_edge("tool_node", "llm_call")  # 工具结果回到模型，形成循环

agent = builder.compile()


# ---------- 消息流打印 ----------
def print_message(msg) -> None:
    """按角色打印一条消息：模型决策 / 工具调用参数 / 工具返回 / 最终回答。"""
    if isinstance(msg, HumanMessage):
        print(f"【用户提问】{msg.content}")
    elif isinstance(msg, ToolMessage):
        print(f"【工具返回】{msg.name} -> {msg.content}")
    elif isinstance(msg, AIMessage) and msg.tool_calls:
        if msg.content:
            print(f"【模型决策】{msg.content}")
        print("【模型决策】发起工具调用：")
        for tc in msg.tool_calls:
            args = ", ".join(f"{k}={v!r}" for k, v in tc["args"].items())
            print(f"  - {tc['name']}({args})")
    elif isinstance(msg, AIMessage):
        print(f"【最终回答】{msg.content}")


if __name__ == "__main__":
    question = "ASM-HEMT 是什么？它的参数数量乘以 2 等于多少？"

    printed = 0  # 已打印的消息数，用于只增量打印新消息
    n_round = 0
    for state in agent.stream(
        {"messages": [HumanMessage(content=question)]},
        stream_mode="values",
        config={"recursion_limit": 15},  # 兜底：最多循环 15 步，防死循环
    ):
        for msg in state["messages"][printed:]:
            if isinstance(msg, AIMessage):  # 每条 AI 消息 = 一轮模型决策
                n_round += 1
                print(f"\n===== 第 {n_round} 轮 =====")
            print_message(msg)
        printed = len(state["messages"])
