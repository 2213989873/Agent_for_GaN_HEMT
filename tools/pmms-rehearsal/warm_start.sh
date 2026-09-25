#!/bin/bash
# 预热启动 MeQLab（与 pmms 相同参数），等待 gRPC TCP 端口就绪，最长 6 分钟
pkill -f 'nbexe[c]' 2>/dev/null; pkill -f 'jre17/bin/jav[a]' 2>/dev/null; pkill -f 'IEP[S]' 2>/dev/null
sleep 2

LOG=/tmp/meqlab_warm.log
nohup /home/zhengjp2/MS-MeQLab/bin/MS-MeQLab --grpc-port-timeout 2008 --feature 'prim|rf_main|ppei' > "$LOG" 2>&1 &
echo "WARM_LAUNCH_PID=$!"

for i in $(seq 1 36); do
  sleep 10
  if ss -tln 2>/dev/null | grep -q ':2008\b'; then
    echo "GRPC_PORT_LISTENING after ~$((i*10))s"
    exit 0
  fi
  if ! pgrep -f 'jre17/bin/jav[a]' > /dev/null; then
    echo "JAVA_DIED at ~$((i*10))s, log tail:"
    tail -20 "$LOG"
    exit 1
  fi
done
echo "TIMEOUT_360S_NOT_LISTENING"
tail -20 "$LOG"
exit 1
