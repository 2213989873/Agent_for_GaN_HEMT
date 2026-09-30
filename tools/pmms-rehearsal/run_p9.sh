#!/bin/bash
# run_p9.sh — P9 窗口：官方示例工程 view→error（目标1）+ jia 复现捕获 TempP_0.sp（目标2）
set -euo pipefail
cd "$HOME/projects/gan-hemt-agent"

CAPTURE=/tmp/p9_deck_capture
mkdir -p "$CAPTURE"

# 0) 官方示例工程就位（幂等，原件不动）
if [ ! -d /tmp/MeqlabProjects/bin_model_demo_point_model ]; then
  cp -r ~/MS-MeQLab/document/quickstart/MeQLab_bin_model_quickstart/3_demo_project/bin_model_demo_point_model /tmp/MeqlabProjects/
  echo "demo project copied -> /tmp/MeqlabProjects/bin_model_demo_point_model"
else
  echo "demo project already in place"
fi

# 1) 预热（与探针同一脚本背靠背，规避 120s watchdog）
pkill -f 'nbexe[c]' 2>/dev/null || true; pkill -f 'jre17/bin/jav[a]' 2>/dev/null || true; pkill -f 'IEP[S]' 2>/dev/null || true
sleep 2
cd ~
nohup /home/zhengjp2/MS-MeQLab/bin/MS-MeQLab --grpc-port-timeout 2008 --feature 'primarius|rf_main|pnano' > /tmp/meqlab_p9_warm.log 2>&1 &
echo "LAUNCH_PID=$!"
ok=0
for i in $(seq 1 24); do
  if ss -tln 2>/dev/null | grep -q ':2008'; then ok=1; echo "PORT_UP after ~$((i*10))s"; break; fi
  sleep 10
done
if [ "$ok" != "1" ]; then
  echo "PORT_TIMEOUT"; tail -3 /tmp/meqlab_p9_warm.log; exit 1
fi

# 2) 后台高频网表捕获（按内容 md5 去重，避免部分写覆盖好副本）
(
  declare -A seen
  while true; do
    for f in "$HOME"/.jms-meqlab/*.sp "$HOME"/.jms-meqlab/Temp*; do
      [ -f "$f" ] || continue
      h=$(md5sum "$f" 2>/dev/null | cut -d' ' -f1) || continue
      [ -n "$h" ] || continue
      if [ -z "${seen[$h]:-}" ]; then
        seen[$h]=1
        cp "$f" "$CAPTURE/$(basename "$f").$h" 2>/dev/null || true
        echo "captured: $f ($h)" >> "$CAPTURE/capture.log"
      fi
    done
    sleep 0.05
  done
) &
WATCHER_PID=$!
echo "WATCHER_PID=$WATCHER_PID"

# 3) 探针
cd ~/projects/gan-hemt-agent
set +e
~/miniconda3/envs/gan-agent/bin/python tools/pmms-rehearsal/p9_probe.py 2>&1 | tee tools/pmms-rehearsal/p9_output.txt
PROBE_RC=${PIPESTATUS[0]}
set -e

# 4) 停捕获 + 清理进程
kill "$WATCHER_PID" 2>/dev/null || true
echo "--- 捕获结果 ---"
ls -la "$CAPTURE" || true
pkill -f 'nbexe[c]' 2>/dev/null || true; pkill -f 'jre17/bin/jav[a]' 2>/dev/null || true; pkill -f 'IEP[S]' 2>/dev/null || true
sleep 3
echo "--- 端口残留检查（应为空）---"
ss -tln | grep -E ':200[0-9]' || echo "no :200x listener"
exit "$PROBE_RC"
