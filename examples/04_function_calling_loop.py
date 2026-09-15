"""任务 04：手写 function calling 循环 —— 不依赖 LangGraph，看清 Agent 底层原理

所谓"工具调用 Agent"，拆开看只有一个 while 循环：
  1. 把 messages + 工具的 JSON schema 一起 POST 给模型
  2. 模型要么直接回复文本（结束），要么在 message.tool_calls 里
     "请求"调用函数 —— 注意模型并不真的执行函数，只是返回结构化参数
  3. 我们的代码负责真正执行函数，把结果以 role="tool" 消息
     （带对应的 tool_call_id）追加进 messages，再回到第 1 步
LangGraph 的 llm_call + tool_node 循环，本质就是把这三步包了一层。

运行：python examples/04_function_calling_loop.py
"""
import ast
import json
import operator
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]  # 仓库根目录（examples/ 的上一级）
GLOSSARY_PATH = ROOT / "docs" / "名词手册.md"

load_dotenv(ROOT / ".env")
api_key = os.getenv("DEEPSEEK_API_KEY", "")
if not api_key or api_key.startswith("sk-在这里"):
    sys.exit("❌ 请先把 .env.example 复制为 .env，并填入真实 DEEPSEEK_API_KEY")

client = OpenAI(base_url="https://api.deepseek.com", api_key=api_key)


# ---------- 工具的真实实现（本地 Python 函数） ----------
def lookup_glossary(term: str) -> str:
    """在 docs/名词手册.md 中查找名词，返回所有包含该词的行；找不到返回"未收录"。"""
    hits = [
        line.strip()
        for line in GLOSSARY_PATH.read_text(encoding="utf-8").splitlines()
        if term.lower() in line.lower()
    ]
    return "\n".join(hits) if hits else "未收录"


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


def calc(expression: str) -> float:
    """安全计算四则运算表达式（只允许数字、括号和 + - * /），禁止 eval。"""
    return float(_eval_node(ast.parse(expression, mode="eval")))


# 工具名 -> 本地函数，循环里按模型返回的名字查表分发
FUNCTIONS = {"lookup_glossary": lookup_glossary, "calc": calc}

# ---------- 给模型看的工具 JSON schema（tools 参数，随请求 POST 给 API） ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_glossary",
            "description": "在名词手册中查找 GaN HEMT / 紧凑模型 / AI 工程相关名词的解释。"
            "返回手册中包含该词的行；找不到返回『未收录』。查名词必须先调本工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "要查找的名词，例如『ASM-HEMT』『HEMT』",
                    },
                },
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "安全计算四则运算表达式（只允许数字、括号和 + - * /）。"
            "任何算术都必须调用本工具，不要口算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "要计算的表达式字符串，例如『120 * 2』",
                    },
                },
                "required": ["expression"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "你是 GaN HEMT 紧凑模型参数提取助手。"
    "遇到专业名词先调用 lookup_glossary 查名词手册；"
    "需要算术时调用 calc，不要口算。"
    "拿到工具结果后再组织最终回答，用中文简洁作答。"
)


def run_agent(question: str, max_rounds: int = 10) -> str:
    """手写 Agent 循环：问模型 -> 执行它请求的工具 -> 把结果喂回去 -> 再问。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for round_no in range(1, max_rounds + 1):
        print(f"\n===== 第 {round_no} 轮 =====")
        resp = client.chat.completions.create(
            model="deepseek-chat", messages=messages, tools=TOOLS
        )
        msg = resp.choices[0].message

        # 模型回复（含 tool_calls）必须原样进 messages，否则下轮上下文不完整
        messages.append(msg)

        # 没有 tool_calls = 模型给出最终回答，循环结束
        if not msg.tool_calls:
            print(f"【最终回答】{msg.content}")
            return msg.content

        # 模型只是"请求"调用；真正执行函数的是我们
        print("【模型决策】发起工具调用：")
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)  # 参数是 JSON 字符串，先解析
            print(f"  - {name}({args})")
            try:
                result = FUNCTIONS[name](**args)
            except Exception as e:  # 执行失败也把错误喂回去，让模型自己纠正
                result = f"工具执行出错: {e}"
            print(f"【工具返回】{name} -> {result}")

            # role="tool" + tool_call_id：告诉模型"这是你刚才那个调用的结果"
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": str(result)}
            )

    raise RuntimeError(f"超过 {max_rounds} 轮仍未得到最终回答，强制退出")


if __name__ == "__main__":
    run_agent("ASM-HEMT 是什么？它的参数数量乘以 2 等于多少？")
