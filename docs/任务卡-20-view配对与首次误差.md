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
4. ~~MeQLab 安装内无 asmhemt 模型文件/无 .osdi——asmhemt 是 NanoSpice 内建模型类型，由 license feature 控制可用性。~~ **已被 P9（2026-09-30）证伪**：NanoSpice 不内建 asmhemt（strings 仅 bsim/psp 族），提供方式待组委会说明——见文末 P9 小节。
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

---

## 2026-09-29 复跑取证（P8-verify1，实况验证）

复跑 p8_probe.py（输出 `p8_verify1_output.txt`，license 服务器连通性 nc 验证通过）：

1. 症状原样复现：jia+asmhemt → 共 0 个视图，聚合误差 nan。
2. `MS_MEQLAB_SPICE` 签出失败再次复现（messages.log 14:09:27，模型套件加载后 1 秒，时序签名与 P8 完全一致）。
3. **新证据**：severe.log 抓到 NanoSpice 实际被调用并报错——
   `!!NanoSpice-ERROR: In FILE ~/.jms-meqlab/TempP_0.sp, LINE 14: In top level circuit, cannot find master of element 'm1'.`
   即仿真引擎跑了，但生成的网表里 m1 没有模型定义（临时网表跑完即删，当时未捕获）。
4. 副产物：pmms.exe --local 会自启独立 MeQLab 实例（端口 2009，feature `prim|rf_main|ppei`），正式比赛链路以它为准。

## 2026-09-30 组委会 A17 回复——license 假说撤回

> Q17: 每次使用 asmhemt 模型源时 MS_MEQLAB_SPICE 签出失败……授权缺失还是额度占满？
> A17: **可以忽略该 error，缺少该 license 不影响使用。** 如不希望每次报错，启动 MeQLab 时不勾选"single nano"，仅勾选"parallel nano"。

**结论修订**：`MS_MEQLAB_SPICE`（= single NanoSpice 档）签出失败是无害噪音；parallel nano（`MS_MEQLAB_PARALLEL_SPICE`，一直签出成功）才是实际使用的档。**"license 缺 feature 导致仿真不跑"假说撤回**，E4 的不一致（P7-bis 1 视图 nan vs P8 0 视图 nan）也随之不再是 license 浮动证据。

**当前头号嫌疑**：P8-verify1 抓到的 `cannot find master of element 'm1'`——jia+asmhemt 组合生成的仿真网表缺少模型定义，属网表组装/模型源使用层面的问题，方向从"license 范围"转为"我方模型源/视图配对用法"。

**下一步（P9，已启动）**：① 官方 point_model 工程 view→error 出数值，钉死"引擎无罪"终证；② 复跑 jia 组合并高频捕获 `~/.jms-meqlab/TempP_0.sp`，看 m1 引用的模型名与 deck 内模型定义/包含行，定位 master 缺失根因。

---

## P9 结果（2026-09-30，两个窗口）

探针 `tools/pmms-rehearsal/p9_probe.py`，脚本 `run_p9.sh`，输出 `p9_output.txt`（run2）/ `p9_output_run1.txt`，ledger `p9_ledger.jsonl` / `p9_ledger_run1.jsonl`。

### 目标1 判决：NUMBER（引擎无罪终证达成，两次复现）

- 参数一次命中：`filter_string="name,IV_data(Sweep)"`、`source_string="IV_data, Binning1"`、`page_string` run1 用 `id_vd` → **共 4 个视图**，run2 用 `id_vd_vg` → **共 2 个视图**，视图名均为 `(id_vd)Id_Vds@vbs=…@NMOS(W=0.3000 L=… T=25.00)`，误差全是数值（如 0.014959786082024158 / 7.19e-07），聚合误差 run1=**0.007597814444251153**、run2=**0.015194800466514152**。`dump_view_group` 导出 `/tmp/p9_demo_view_group.xlsx` 成功。
- 基线复验：open_project 后不 view 直接 get_view_group_error → code 2 `no view group loaded, call view first`（与既有事实一致）。
- 页名来源：工程页名不在 workspace.xml，从 `data.h2.db` strings 出 `Id_Vg`/`id_vd`；`get_data_detail("IV_data")` 报页数 64。
- **新观察（配对数量不稳定）**：同一参数组合 `id_vd` 在 run1 配 4 视图、run2 配 0 视图，`id_vd_vg` 在 run2 配 2 视图——view 配对结果跨会话不完全确定，正式流程须接受"多试几个页名"。
- 注意：该工程模型源 Binning1 的 simulator="Internal"，目标1 证明的是 MeQLab view→error 链路 + Internal 引擎无罪；NanoSpice 对 BSIM 无罪由 P7g 证据承担。

### 目标2：TempP_0.sp 捕获成功，根因定位

- 捕获文件：`/tmp/p9_deck_capture/TempP_0.sp.f9028a40292ed7aa58180871166505aa`（7969B，md5 去重监视器，run2 轮询 0.05s）。
- **第 14 行**：`m1 d0 g0 s0 b0 jiamod  w=pari_w l=pari_l` —— m1 引用的模型名是 `jiamod`。
- **模型定义/包含行**：deck 第 2 行 `.lib '/tmp/MeqlabProjects/pmms_rehearsal/model/0/jia_with_lib.inc' tt`——模型经 `.lib` 正确包含；该文件存在且内容即 `.lib tt / .model jiamod asmhemt (rdsmod=1) / .endl tt`。deck 内无其他 `.model`/`.include`。第 24 行有 `simulator lang=spectre`（供 altergroup 块用），第 69 行切回 `lang=spice`，与报错无关。
- **根因判断**：网表组装完全正确（MeQLab 无罪），但 `strings` 全安装树扫描证实 **整个 MS-MeQLab 安装（含 nanospice 二进制、cpei.so、etc 配置）不存在任何 "asmhemt" 字样**；nanospice 只内建 bsim3/bsim4/bsimbulk/bsimcmg/psp 等族。`.model jiamod asmhemt` 引用了一个 NanoSpice 不认识的模型类型 → 该语句未能注册 master → 第 14 行 `m1 … jiamod` 报 `cannot find master`。即 **ASM-HEMT 不是 NanoSpice 内建模型，需以组委会指定方式提供（内建别名/VA 模型加载/专用 license feature），这是下一个组委会问题**。nanospice 二进制拒绝独立运行（"This is NOT a standalone version"），无法脱离 MeQLab 做最小复现。
- 触发方式修正：NanoSpice 仿真由 view/save_sim_result **异步**触发（"Done simulation" 比 view 晚约 1s 落日志）。run1 探针在 get_view_group_error 返回后 3ms 关会话，pmms 杀掉 MeQLab，异步仿真没来得及写 deck；run2 在 jia 段加 `save_sim_result`（同步，但**仿真失败也返回"成功"**，不可信其文本）+ `sleep 10` 后成功复现并捕获。
- 附带观察：jia_iv 本次 0 视图是因 messages.log 里 `FindPage: failed to find needed page` SEVERE 重复 32 次（页查找失败），与仿真失败是两回事；`save_sim_result` 对 jia 组合返回"仿真结果保存成功"属假阳性。
