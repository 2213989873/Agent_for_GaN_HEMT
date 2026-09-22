# M6：24h 作战 dry run 演练记录（2026-09-22）

- **判据**（总进度/架构设计 §5）：作战手册 T0–T5 全块演练入档；熔断 A–D 各模拟触发一次有处置证据
- **依据文档**：任务卡15（作战手册）；压缩方式=动作真实执行、等待时间压缩（熔断 D 退避窗 31s 代替"连续 10 分钟"）
- **最大收获**：四条熔断里有三条在演练前**名存实亡**（手册写了、代码没兜底），dry run 全部抓出并修复——这正是演练的意义

## T0 · 环境核对 + MCP 适配（手册 0–1h，实测 15s）

适配核对四项（卡14 §5 清单）：transport=stdio 长连接 / 工具名 run_simulation·get_call_count·reset_count / 参数 dict 通道 / 返回 JSON。
工具：`src/tools/smoke_mcp_session.py`——三形态各跑一次 + 计数断言（=3 ✅），15 秒出结果。
T0 改动面再压缩：server 路径可用环境变量 `MCP_SERVER_PATH` 覆盖，连代码都不用动（手册原方案是改 mcp_sim.py）。

## T1 · 冒烟 + 计数验证（手册 1–2h，实测 30s）

`src/pipeline/day1_baseline.py --via-mcp`：
- 默认卡基准落盘：`data/sim/day1_default_transfer.csv`（121 点，峰值 0.3664A）、`day1_default_output.csv`（847 点，峰值 0.4919A）——全天 NRMSE 对拍基准；
- t_sim≈0.02–0.03s（mock 本地；真 MCP 按手册 §3 估 10s/次，单族精修预算上限 1h 不变）；
- 红线计数器读数=2，与仿真次数一致 ✅。

## T2/T3 · 器件提取（测试日真实形态：--via-mcp）

`python src/pipeline/run_agent.py --devices jia,yi --via-mcp` 一条命令：

| 器件 | 最差形态 NRMSE | 最终参数 | 仿真计数 | 耗时 |
|---|---|---|---|---|
| jia | 0.3857%（≤1% 达标） | voff=-2.0, u0=0.16662 | 81 | 4.5s |
| yi | **0.0001%** | voff=-2.2, u0=0.15, rontr1=-0.99999, rth0=19.997（真值 20） | 2581 | 60.9s |

- 与 M5 本地直连结果**逐位一致**（MCP 链路零偏差第三次复证）；
- joint_refine 两条路径再现：yi 接受（三形态 0.006%→0.000%）、jia 回退（dc_output 回潮超 5% 容差，保分形态解）；
- Schema 校验 ✅；提交物随跑自动产出。

## 熔断 A · 单族撞墙 → 分段归因

- **模拟触发**：`examples/drill_fuse_a.py`——乙 dc_output 锁死 voff/u0 两族（无族可扩），27 次仿真撞墙停在 NRMSE=1.69%（QA 过线但远低于目标，extract 被强制 END）；
- **处置**：`src/pipeline/residual_triage.py`（卡10-bis 任务1 方法代码化，847 点排布=Vg 外层 7 档×Vd 内层 121 点，本次实测判定）：
  - 残差 91% 集中在线性区且随 Vg 单调递增（|corr|=0.90>0.8）→ 判决**陷阱耦合 rontr1 族**；
  - 正确性佐证：卡10-bis 归因结论=缺口含 ron_trap 随 Vg 变化；M2 史实=rontr1 进场 1.69%→0.60%。
- 诚实标注：压缩演练 27 次仿真/1.69% 未达手册">100 次仍>5%"字面阈值——撞墙机理（无族可扩强制 END）已实锤，测试日按字面阈值执行。

## 熔断 B · 保底交卷通道

- **模拟触发**：构造 QA 过线但 dc_output NRMSE=0.60%（超 0.3% 达标线）的保底卡，过 `validate_card`；
- **处置证据**：errors=[]（硬项全过）、warnings=[NRMSE 软项] → **可交卷**；
- **抓出的真问题①**：修复前 NRMSE 超标是 ERROR，熔断 B 保底解会被自己的 Schema 卡死——"够用原则"名存实亡。已改两级校验（`make_submission.py`）。

## 熔断 C · LLM 全挂降级

- **模拟触发**：`DEEPSEEK_API_KEY=sk-invalid-fuseC` 跑 `--device yi --forms dc_transfer`；
- **处置证据**：analyze_data/coarse 双双降级（日志明记"熔断 C"），纯优化器+QA+expand 闭环：补偿解被 QA 驳回 2 次 → 扩 rontr1 → **0.0003% 三参数命中真值**，266 次仿真 4.1s；
- **抓出的真问题②**：修复前 coarse() 无 try/except，LLM 一挂整个 run 直接崩——卡11"不依赖 LLM 质量"名存实亡。已修（`qa_loop.py`）。

## 熔断 D · MCP 掉线重试

- **模拟触发**：`MCP_SERVER_PATH=/nonexistent/server.py` 跑 `--via-mcp`；
- **处置证据**：指数退避 1/2/4/8/16s 五次重试（日志逐条）→ `RuntimeError: MCP 连续 6 次连接失败（熔断 D）……处置：按作战手册上报组委会并截图留证`；
- **抓出的真问题③**：修复前连接失败直接抛栈、零重试——熔断 D 名存实亡。已修（`interface.py`：建连退避 + 运行期掉线重连一次 + ToolError 不重试）。

## T4 · 外推验证 + 红线总核对

`src/pipeline/eval_extrapolation.py`（提取卡 vs 答案卡，拟合集外网格）：

| 器件 | Vd=4V 转移 | Vd=8V 转移 | T=85°C 转移 |
|---|---|---|---|
| yi | 0.000% | 0.000% | 0.000% |
| jia | 0.281% | 0.278% | 0.405% |

- yi 四参数近真值 → 外推零反弹；jia 的 u0 补偿偏差（0.1666 vs 0.17）外推 0.28–0.41%，与拟合集内 0.386% 同量级、远低于 2× 反弹报警线——**风险记录：良性**；
- 红线核对：jia 81 次 / yi 2581 次，≥10 红线 ✅、≥30 目标 ✅。

## T5 · 提交物打包

- submission/：双模型卡（.inc+.json）+ manifest.json + logs/ 日志包，Schema 四项校验全过；
- AGENTS.md §4 状态机图在；仓库干净、commit 推送（本记录同批入档）。

## 战前检查单现状（手册 §0）

- [x] 冒烟对拍：`run_qa.py jia` 0.0000%（2026-09-22 回归）
- [x] 仓库干净已推送；本地 WSL 与 GitHub 一致
- [x] MCP 链路：mock 已就位；真文档测试日到场第一件事索要（T0 动作）
- [ ] **Qwen/GLM 备用 key 未填**（阻塞项②，战前必补）
- [ ] 赛前提交物未交（等组委会窗口；测试日日期未公布=阻塞项①）
