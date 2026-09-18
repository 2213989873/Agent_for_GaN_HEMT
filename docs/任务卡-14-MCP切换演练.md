# 任务卡 14 · MCP 切换演练

> 目的：验证"先当组委会"总策略的最后一环——把闭环的数据来源从本地 ngspice 直连，切换为 MCP 协议调用（模拟组委会 Primarius Modeling MCP Server），确认 Agent 逻辑一行不改、结果逐位一致、调用计数红线可控。

## 一、切换架构：sim_fn 一行换协议

```
run_qa_selfheat.py                    run_qa_mcp.py
  sim_fn = run_output_selfheat_params   sim_fn = mcp_output_sim
        │                                     │
        ▼                                     ▼
  本地直接调 ngspice                  fastmcp Client (stdio)
                                            │
                                            ▼
                                mcp_server_mock.py（mock 组委会）
                                工具 run_iv_simulation(voff, u0, rontr1, rth0)
                                内部：同一个 ngspice、同一个网表、同一个真值
```

- Agent 闭环（coarse → optimize → physics_qa → route → expand）**零改动**；
- 差异全部封装在 `src/tools/mcp_sim.py` 适配层：参数 dict → JSON-RPC → 解析返回 JSON；
- 测试日切换真组委会 = 把 `SERVER_PATH` 换成组委会地址（fastmcp 支持 HTTP/SSE 长连接），适配层函数签名不变。

## 二、新增文件

| 文件 | 作用 |
|---|---|
| `src/tools/mcp_server_mock.py` | FastMCP mock server，暴露 `run_iv_simulation` + `get_call_count` |
| `src/tools/mcp_sim.py` | 客户端适配层 `mcp_output_sim(params, tag)`，asyncio.run 包 Client |
| `src/pipeline/run_qa_mcp.py` | 闭环入口，目标 = dc_output_yi.csv（含自热 847 点） |

**计数持久化**：stdio transport 每次调用重启 server 子进程，内存计数会清零，故调用计数写入 `data/sim/.mcp_call_count` 文件。

## 三、实战记录（2026-09-18，本地 WSL）

目标曲线：乙器件输出特性（含自热，847 点）。两参数起步。

```
coarse: 初值 {'voff': -2.2, 'u0': 0.15}
optimize(8次):  voff=-2.306 u0=0.1223        → NRMSE=1.69%   QA ✅
expand: NRMSE 未达标（RMSE_TARGET=1% 边界外追优）→ rontr1 进场
optimize(15次): voff=-2.238 u0=0.1351 rontr1=-0.8043 → NRMSE=0.60%  QA ✅

最终参数: voff=-2.2377  u0=0.13511  rontr1=-0.80433
最终 NRMSE = 0.6002%
MCP 调用计数: 64 次（红线 ≥10：✅ 满足）
```

**与卡 13 本地直连结果逐位一致**（0.60%、同参数、同轨迹）——协议切换不引入任何数值偏差。

## 四、红线计数机制（测试日保命条款）

- 每器件 MCP 调用 ≥10 次：本演练 64 次，裕量 6.4×；
- 每次工具调用必经计数器落盘，测试日前把计数查询接进 Agent 的 report 节点，跑完自动核对；
- 熔断建议：若某器件闭环收敛过快（<10 次调用），自动补跑一组验证偏置点（外推网格复测），既攒调用数又产外推证据，一举两得。

## 五、已知差异（mock vs 真组委会，测试日核对清单）

| 项 | 本演练 mock | 测试日真 MCP |
|---|---|---|
| transport | stdio（每次调用重启进程，banner 刷屏） | 预计 HTTP/SSE 长连接 |
| 工具名/参数 | run_iv_simulation（我方自定） | 以组委会公布 schema 为准 |
| 数据形态 | 输出特性 847 点 CSV 同源 | 组委会指定偏置网格 |
| 时延 | 每次 ~1-2s（进程重启） | 远程仿真，预计更慢，注意超时设置 |

测试日到场第一件事：拿到组委会 MCP 文档，核对工具名、参数单位、返回字段，只改适配层。

## 六、结论

"先当组委会"全链路打通：**本地虚拟器件练兵（01-13）→ MCP 协议演练（14）→ 测试日一行切换**。Agent 主体逻辑与协议彻底解耦，演练结果与本地直连逐位一致，红线计数机制就位。
