# 任务卡-20：view 配对与首次误差——MS_MEQLAB_SPICE license 卡点锁定

日期：2026-09-28 ｜ 执行：教练（本会话） ｜ 状态：**已取证，阻塞待组委会**

## 一句话结论

`error=nan / 0 视图`的头号根因已锁定为 **license 缺 feature**：ASM-HEMT 属于通用 SPICE 模型档，仿真需要 `MS_MEQLAB_SPICE`；我们的 license 服务器（15281@121.199.160.165）签不出该 feature，仿真根本无法运行，视图配对与误差计算随之全灭。**这不是配置问题，是 license 范围问题，需组委会确认。**

## 证据链（全部一手日志，文件指针在文末）

### E1 license 签出记录（~/.MS-MeQLab/dev/var/log/info.log，P7g 窗口 17:29-17:31）

```
Check out license MS_MEQLAB_CLUSTER failed.        ← 启动时
Check out license MS_MEQLAB_BB successful.
Check out license MS_MEQLAB_RF successful.
Check out license MS_MEQLAB_LIBM successful.
Check out license MS_MEQLAB_FLOW successful.
Check out license MS_MEQLAB_PARALLEL_SPICE successful.
Check out license MS_MEQLAB_SPICE failed.          ← 17:31:56 仿真调用时
Check out license MS_MEQLAB_BSIM4 successful.      ← 17:31:57 BSIM4 专属档
```

### E2 NanoSpice 真的跑过（warning.log，17:31:57，nmos_tt_N 模型源）

```
!NanoSpice-WARNING: Bin fitting check for single model 'nmos' is disabled as option soft_bin=singlemodels...
!NanoSpice-WARNING: Duplicate probe 'i(vd0)' is set. Ignored.
```
→ BSIM4 有专属 license，仿真引擎本身无恙。**license 是按模型类型分档签出的。**

### E3 P8 窗口：asmhemt 模型加载即触发 SPICE license 失败（p8_output.txt + messages.log 增量）

时序（2026-09-28 17:44，P8 探针 14 次调用全成功返回）：
```
17:44:39  Done loading model suite from file        ← jia_with_lib.inc（asmhemt）
17:44:40  Check out license MS_MEQLAB_SPICE failed  ← 模型源使用时立即签出、失败
17:44:40  Start loading jia_transfer.pms
17:44:40  SEVERE: Failed to call function findpage ×32  ← view 调用页查找全灭
```
结果：`get_view_group_error` → **共 0 个视图，聚合误差 nan**。期间 warning.log 零新增——NanoSpice 对 jiamod 一个字都没说，**仿真没跑**。

### E4 与 P7-bis 的不一致（标"未验证"，防假说固化）

- P7-bis（约 17:0x）：同一 jia+asmhemt 组合、同页名 id_vg_vb → **1 个视图** `(Id_Vg)Id_Vgs@vds=1.0@NMOS(W=10.00 L=1.000 T=27.00)`，error=nan。
- P8（17:44）：同组合同页名 → **0 个视图**，error=nan。
- 嫌疑：license 是远程浮动签出，feature 可能被他人占用/释放，不同窗口状态不同；P7-bis 窗口的日志已被轮转无法复核。两种失败（1视图nan / 0视图nan）都指向"仿真侧无结果"。**待 license 问题解决后复测分辨。**

## P7 系列实验矩阵（存档汇总，ledger 均在 tools/pmms-rehearsal/）

| 数据 | 模型 | 结果 | 实验 |
|---|---|---|---|
| jia_transfer.pms（自制，单 p 列） | jiamod_tt_N（asmhemt 卡） | 1 视图但 error=nan | P7-bis |
| jia_transfer.pms | jiamod_tt_N | 0 视图 nan（日志锁定 license 失败） | **P8** |
| jia_transfer.pms | nmos_tt_N（官方 BSIM 包装卡） | 0 视图（NanoSpice 真跑过） | P7g |
| 官方 demo iv .pms（5 条 p 曲线） | nmos_tt_N | 0 视图（filter 歧义已排除） | P7d/e |
| demo.lib 嵌套自引用任意组合 | — | add_model_source 全 code 8 | P7c/f |

已锁死的 PMMS 事实（前几轮证实，勿重开）：模型源必须 `.lib/.endl` 直包 `.model`；list_params 只列卡上声明参数；min/max/step 必须显式全传；模型源/数据源跨重启不持久；view 返回"视图选择成功"≠配对成功，唯一判据是 get_view_group_error 的"共 N 个视图"。

## 附带收获（零成本法医材料）

1. 官方完整示例工程 5 个：`~/MS-MeQLab/document/quickstart/MeQLab_bin_model_quickstart/3_demo_project/`。其中 `bin_model_demo_point_model` 含 74 个 Ordinary Page 曲线视图（已知良好配置参照）；workspace.xml 显示配对钥匙 = 数据源 pages + Filter(Sources 主数据+模型) + View(deviceid×pageid)。
2. MeQLab 运行日志在 `~/.MS-MeQLab/dev/var/log/{info,warning,severe,messages}.log`——**每次窗口后必读，是排障第一手来源**（已写入纪律）。
3. `etc/extraction/spec/HEMT/Spec.ini`、`etc/extraction/rfspec/HEMT/Spec.ini` 存在 HEMT spec 模板（内容是 HBT 式 vbe/Ib/Ic spec，非本赛题 IV/CV 曲线流，仅备查）。
4. MeQLab 安装内无 asmhemt 模型文件/无 .osdi——asmhemt 是 NanoSpice 内建模型类型，由 license feature 控制可用性。
5. B 段发现：`open_project` 不恢复视图组，`get_view_group_error` 报 `no view group loaded, call view first`——官方工程对照实验设计需先 view 选定视图组（留待 P9）。

## 阻塞与升级请求（→ 组委会）

**问题**：license 服务器 15281@121.199.160.165 无法签出 `MS_MEQLAB_SPICE` feature（日志原文如上）。ASM-HEMT 模型仿真依赖该 feature。
**请组委会确认**：① 赛题 license 是否应包含 MS_MEQLAB_SPICE（或 ASM-HEMT 对应 feature 名）；② 若有，是额度被占满还是授权缺失；③ 正式比赛环境的 license 配置是否与彩排环境一致。

## 下一步（license 打通前不空等）

- P9：license 空闲时段重试 A 段 + 补 B 段（官方 demo 工程 view→error 出数值，钉死"引擎无罪"终证）。
- 练兵场（本地 ngspice）主线不受此阻塞：M1-M6 全部基于本地仿真，继续推进。

## 文件指针

- 探针/输出/ledger：`tools/pmms-rehearsal/p8_probe.py`、`p8_output.txt`、`p8_ledger.jsonl`、`run_p8.sh`
- 日志：WSL `~/.MS-MeQLab/dev/var/log/`（运行时现读，不入库）
- 官方工程：`~/MS-MeQLab/document/quickstart/MeQLab_bin_model_quickstart/3_demo_project/`
