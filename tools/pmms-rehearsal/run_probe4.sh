#!/bin/bash
# 拉起 pnano 实例 + 等端口 + 窗口内立即跑 P4 探针
pkill -f 'nbexe[c]' 2>/dev/null; pkill -f 'jre17/bin/jav[a]' 2>/dev/null; pkill -f 'IEP[S]' 2>/dev/null
sleep 2
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
cd ~/projects/gan-hemt-agent
cp /mnt/d/KimiData/kimi/tasks/2026-09-14/08-32-13-31782a90/pmms-rehearsal/repo/tools/pmms-rehearsal/p4_probe.py tools/pmms-rehearsal/
~/miniconda3/envs/gan-agent/bin/python tools/pmms-rehearsal/p4_probe.py
