#!/usr/bin/env bash
set -eu
echo 'Read-only VPS audit'
cat /etc/os-release
free -h
df -h /
uptime
ss -lntup
if command -v docker >/dev/null; then docker ps --format 'table {{.Names}}\t{{.Ports}}'; docker compose version; fi
systemctl list-units --type=service --state=running --no-pager
echo 'Check 1935 and 8554 before deployment. Do not stop existing services.'
