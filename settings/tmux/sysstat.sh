#!/bin/sh
# CPU% since the previous call (state in /tmp), RAM% and root disk% for the tmux status bar.
df -P / | awk -v s="/tmp/tmux-sysstat-$USER" '
NR == 2 { disk = $5 }
END {
  getline l < "/proc/stat"; n = split(l, c)
  for (i = 2; i <= n; i++) total += c[i]
  idle = c[5] + c[6]
  if ((getline p < s) > 0) { split(p, q); dt = total - q[1]; if (dt > 0) cpu = 100 * (1 - (idle - q[2]) / dt) }
  close(s); print total, idle > s
  while ((getline l < "/proc/meminfo") > 0) { split(l, m); if (m[1] == "MemTotal:") mt = m[2]; else if (m[1] == "MemAvailable:") ma = m[2] }
  printf "#[fg=colour240]C:#[default]%d%% #[fg=colour240]R:#[default]%d%% #[fg=colour240]D:#[default]%s", cpu, 100 * (1 - ma / mt), disk
}'
