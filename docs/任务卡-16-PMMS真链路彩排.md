# 任务卡 16 — PMMS 真链路彩排（P0/P1 通过）

日期：2026-09-25。环境：本机 WSL2 + Windows 互操作。执行：教练（本会话）直接施工。

## 结论

**真链路全通**。initialize OK（server=primarius-modeling v1.26.0，protocolVersion=2025-11-25），
**44 工具 / 5 prompts / 4 resources** 全部列出，会话干净关闭。

## 链路拓扑（彩排形态）

```
python mcp client (WSL, gan-agent env)
  → stdio → pmms.exe (Windows PE，WSL interop 直接运行，~/MCP/mcp/pmms.exe)
  → CreateProcess → meqlab-wrapper.exe (自编译 TCP 代理，监听 127.0.0.1:<分配端口>)
  → 转发 127.0.0.1:2008（WSL localhostForwarding / wslrelay）
  → 预热中的 Linux MeQLab (~/MS-MeQLab，gRPC *:2008)
```

## 三个真问题与解法（全部有反编译/实测证据，非猜测）

1. **pmms.exe 是 Windows PE32+**（56MB，PyInstaller 打包的 Python 3.12）。
   WSL interop 可直接运行（需 chmod +x；拷到 D: 的副本被 Windows Defender 静默清除过一次，
   原始份留在 Linux 原生目录 ~/MCP/mcp 运行）。
2. **local 模式 subprocess.Popen 跑不了 .bat**（CreateProcess 不能直接执行批处理，
   且 `%*` 展开会重解析 `prim|rf_main|ppei` 里的管道符）。
   解法：PowerShell Add-Type 离线编译 C# 真 exe 包装层（`tools/pmms-rehearsal/meqlab-wrapper.cs`）。
3. **MeQLab 冷启动 ~150s > pmms 60s 就绪超时**（本机 8GB/WSL 实测）。
   反编译证据：`meqlab_manager.pyc` 中 `READY_WAIT_TIMEOUT=60`、`READY_PROBE_INTERVAL=1.0`，
   就绪判据是**裸 TCP connect**（`_probe_port` → `socket.create_connection`），不是 gRPC 握手。
   解法：**预热 + 端口代理**——先手动起 MeQLab（150s 到 LISTEN），wslrelay 占住 Windows 侧 2008，
   pmms 扫端口自动分配到 2009，代理把 2009 流量倒进 2008。pmms 日志实测 0.5s 判就绪。

## pmms 源码事实（pyc 常量提取，/tmp/pmms_src 解包）

- pmms 传给 MeQLab 的启动参数：`--grpc-port-timeout <port> --feature <features> [--prjdir <dir>]`
- 心跳：`HeartbeatThread` 每 10s 调 `IsServiceAvailable`，失败仅告警（grpc_client.pyc）；
  server 端 watchdog 2 分钟无心跳自动退出 IDE——**pmms 退出后 MeQLab 会自清理，彩排无需手工扫尾**
- 本地模式 stop() 直接 terminate 子进程；SSH 模式不 kill 远端，靠 watchdog
- SSH 模式会自动探测 DISPLAY（扫 ssh_user 进程 /proc environ → xdpyinfo/xset 验证 → /tmp/.X11-unix 兜底）
  ——**MeQLab 是 GUI 应用，需要 X**；本机经 WSLg DISPLAY=:0 满足，GUI 窗口会真实弹出
- v4 协议：无 token 鉴权、无 TLS，insecure_channel 明文 gRPC 直连动态端口
- BUSY(9) 自动重试 **PMMS 未实现**，需我们客户端自己做（API 文档原文确认）

## 彩排 SOP（复现入口）

```bash
# 1. 预热（约 150s，等到 GRPC_PORT_LISTENING）
bash ~/projects/gan-hemt-agent/tools/pmms-rehearsal/warm_start.sh
# 2. 握手+工具清单
~/miniconda3/envs/gan-agent/bin/python ~/projects/gan-hemt-agent/tools/pmms-rehearsal/p1_handshake.py
# 3. 无需清理：心跳停止后 MeQLab watchdog 2 分钟自退出；再彩排重回第 1 步
```

编译包装层（改了 .cs 才需要）：
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File compile.ps1`（同目录）

## 未验证/风险

- MS_MEQLAB_CLUSTER license checkout failed（其余 BB/RF/LIBM/FLOW/PARALLEL_SPICE 五项成功）——影响未知，真数据练习时观察
- 测试日若组委会给 SSH 凭证，链路变为 `pmms.exe --ssh-host ... --ssh-key ...`，本包装层整体不需要；
  SSH 模式同样 60s 就绪超时，组委会 server 启动速度未知（裸机大概率 <60s）
- 44 工具的参数细节以 `docs/pmms/MCP_API.md` 为准；`selection_string`/`view_fields`/`filter` 语法未实战
- pmms 进程被强杀时代理孤儿由 MeQLab watchdog 兜底，但 Windows 侧 wrapper.exe 可能残留（彩排后 `taskkill /IM meqlab-wrapper.exe`）

## 证据文件

- 握手输出（44 工具清单）：本任务卡存档于 git 历史；运行脚本 `tools/pmms-rehearsal/p1_handshake.py`
- pmms 启动日志关键行：`✓ gRPC 端口就绪：127.0.0.1:2009` / `✓ MCP Server 启动成功`（2026-09-25 20:53:31）
- 预热计时证据：warm_start.sh 输出 `GRPC_PORT_LISTENING after ~150s`
