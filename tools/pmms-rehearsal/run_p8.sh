#!/bin/bash
# run_p8.sh — P8 窗口：nan 现场取证（日志快照）+ 官方 point_model 工程对照
set -euo pipefail
cd "$HOME/projects/gan-hemt-agent"

# 0) 官方示例工程复制到 PMMS 工程目录（幂等，原件不动）
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
nohup /home/zhengjp2/MS-MeQLab/bin/MS-MeQLab --grpc-port-timeout 2008 --feature 'primarius|rf_main|pnano' > /tmp/meqlab_warm.log 2>&1 &
echo "LAUNCH_PID=$!"
ok=0
for i in $(seq 1 24); do
  if ss -tln 2>/dev/null | grep -q ':2008'; then ok=1; echo "PORT_UP after ~$((i*10))s"; break; fi
  sleep 10
done
if [ "$ok" != "1" ]; then
  echo "PORT_TIMEOUT"; tail -3 /tmp/meqlab_warm.log; exit 1
fi

# 2) 探针
cd ~/projects/gan-hemt-agent
~/miniconda3/envs/gan-agent/bin/python tools/pmms-rehearsal/p8_probe.py 2>&1 | tee tools/pmms-rehearsal/p8_output.txt
