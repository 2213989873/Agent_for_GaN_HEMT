# 任务卡 19 · 数据 I/O 支线打通 + .pms 格式复刻判决（P6 探针，2026-09-28 16:56）

> 隶属：M7 子任务2 / C3 双轨对拍前置。
> 问题：官方数据格式未知，练兵数据能否进 PMMS 决定"本地↔官方双轨"是否可行。
> 证据：`tools/pmms-rehearsal/p6_output.txt`、`p6_ledger.jsonl`（12 行，计数 12=12）、探针 `p6_probe.py`、生成器内嵌于 `run_p6.sh`。

## 结果：两问全 PASS

### A. 官方 demo 基线（全链一次通）
`load_data`(data_type=0/SWEEP) → `list_data_sources` → `get_data_detail`（类型自动推断 Mosfet，页数 4）→ `build_filter_by_data` → `list_filters` → `extract_spec` 全部成功。

**关键发现——filter 页族自动分裂**：build_filter_by_data 对一个 IV sweep 源自动生成 6 个 filter 页：`iv_demo(Sweep)(Ordinary Page)`、`(Spec)(Spec vs Instance)`、`(VbSpec)`、`(ErrMonitor)(Spec Table)`、`(DeltaT)(Spec Table)`。后续 `view` 的 filter 引用这些名字。

### B. 自制 .pms 判决：**PASS**
按 demo 格式复刻的 `data/sim/jia_transfer.pms`（jia 转移曲线，Vd=1V 协议，121 点，Id 取负还原符号）被完整接受：load_data 成功（ID:1）、detail 页数 1、filter 构建成功并入列。**练兵数据 ↔ PMMS 的桥已通**，C3 双轨对拍数据侧就绪。

## .pms 格式规范（从官方 demo 逆向，已验证可写）

```
// Primarius Technologies Co., Ltd.      ← 两行注释头
// Sweep Data
{group=Id_Vg,y=(Id),x=Vgs,p=Vbs(0.0,-0.625,...),condition=(ref_vs=0.00000,vds=0.0500000),device=(type=Mosfet,polarity=NMOS,w=9.0,t=125.0,l=9.0)}
<x>\t<y_p1>\t<y_p2>…                      ← 每行一个 x 点，列=p 的各取值
```
- 多曲线 = `p=` 维多列；固定偏置进 `condition=`；**温度在 `device=(t=…)` 和文件名/目录里**（demo 按 `-40/25/125` 分目录）——C1 多温度联合拟合在数据层的组织方式已现形（多文件多源，view 能否跨源圈选待子任务3 实测）；
- 路径组织：`data/mosfet/{nmos,pmos}/{iv,cv,…}/<温度>/<w,t,l 编码文件名>.pms`；
- `data_type`：0=SWEEP（本卡）/1=SPEC/2=WAT（统计，对应 wat.txt/sigma.txt）；
- `load_data` 的 `path` 接受 server 侧绝对路径（本次用法）或 `projectdir/user/` 相对路径（配 `upload_file`）。

## 对子任务3 的铺垫
view 的两个原料都已实测在手：**filter 页名**（本卡）+ **模型源名**（卡17/18）。下一探针 P7：`view`（含 selection_string）→ `get_view_group_error`——将触发首次 NanoSpice 真仿真并给出官方误差读数。
