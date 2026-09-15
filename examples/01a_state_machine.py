"""任务 01a：LangGraph 纯状态机 demo（不调用 LLM）

目的：只练 LangGraph 的图结构本身 —— State 定义、节点、边、条件边、
     以及 reducer（Annotated + operator.add）的追加合并语义。

节点图（ASCII）：

  +-----------+    +--------+    条件边: 按 value 奇偶分流
  | set_input | -> | double | --+--(偶数)--> +-------------+
  +-----------+    +--------+   |            | report_even | --+
                                |            +-------------+   |
                                |                              +--> END
                                |            +------------+    |
                                +--(奇数)--> | report_odd | ---+
                                             +------------+

运行：python examples/01a_state_machine.py
（输入 value=7：7 × 2 = 14 为偶数，应走 report_even 分支）
"""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    """图的全局状态。

    value：普通字段，节点返回新值时直接覆盖；
    log：Annotated + operator.add 声明 reducer，
         各节点返回的 list 会被“追加合并”到旧 list 后面，而不是覆盖。
    """

    value: int
    log: Annotated[list[str], operator.add]


def set_input(state: State) -> dict:
    """入口节点：登记初始输入。"""
    return {"log": [f"set_input: 读入初始值 value={state['value']}"]}


def double(state: State) -> dict:
    """把 value 乘以 2，并记一条日志。"""
    new_value = state["value"] * 2
    return {
        "value": new_value,
        "log": [f"double: {state['value']} × 2 = {new_value}"],
    }


def route_by_parity(state: State) -> str:
    """条件边的路由函数：返回下一个节点的名字。"""
    return "report_even" if state["value"] % 2 == 0 else "report_odd"


def report_even(state: State) -> dict:
    """偶数分支的汇报节点。"""
    return {"log": [f"report_even: value={state['value']} 是偶数"]}


def report_odd(state: State) -> dict:
    """奇数分支的汇报节点。"""
    return {"log": [f"report_odd: value={state['value']} 是奇数"]}


# ---------- 组构状态图 ----------
builder = StateGraph(State)

# 注册四个节点
builder.add_node("set_input", set_input)
builder.add_node("double", double)
builder.add_node("report_even", report_even)
builder.add_node("report_odd", report_odd)

# 固定边：START -> set_input -> double
builder.add_edge(START, "set_input")
builder.add_edge("set_input", "double")

# 条件边：double 执行完后，由 route_by_parity 决定去哪个 report 节点
builder.add_conditional_edges("double", route_by_parity)

# 两个 report 节点都通向 END
builder.add_edge("report_even", END)
builder.add_edge("report_odd", END)

graph = builder.compile()


if __name__ == "__main__":
    # stream_mode="values"：产出初始 state 以及每执行完一个节点后的完整 state 快照
    print("输入 value=7，逐节点执行：\n")
    for step, state in enumerate(
        graph.stream({"value": 7, "log": []}, stream_mode="values")
    ):
        title = "初始 state（未执行节点）" if step == 0 else f"第 {step} 个节点执行后的完整 state"
        print(f"--- {title} ---")
        print(f"value = {state['value']}")
        print(f"log   = {state['log']}\n")

    print(f"最终 value = {state['value']}，log 共 {len(state['log'])} 条")
