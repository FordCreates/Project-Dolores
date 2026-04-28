#!/bin/bash
# heartbeat_type.sh — Determine current heartbeat type
# Window: 23:30 - 00:30 (Asia/Shanghai)
# Output: regular | midnight
H=$(TZ=Asia/Shanghai date +%H%M)
if [ "$H" -ge 2330 ] 2>/dev/null || [ "$H" -le 0030 ] 2>/dev/null; then
  echo "midnight"
else
  echo "regular"
fi
