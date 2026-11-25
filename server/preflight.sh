#!/usr/bin/env bash
# Read-only: no fetch, pull, push, restart, or install.
echo '=== SYSTEM ==='
hostname; cat /etc/os-release; nproc; free -h; df -h /; uptime
echo '=== LISTENERS ==='
ss -lntup
echo '=== SERVICES ==='
systemctl list-units --type=service --state=running --no-pager
echo '=== DOCKER ==='
if command -v docker >/dev/null; then docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'; docker compose ls; fi
echo '=== MEDIAMTX ==='
command -v mediamtx; systemctl is-active mediamtx; pgrep -x mediamtx
echo '=== REPOSITORIES ==='
find /opt /srv /var/www /root /home -maxdepth 5 -type d -name .git -print0 2>/dev/null | while IFS= read -r -d '' gitdir; do
  repo="${gitdir%/.git}"
  printf '\n%s\n' "$repo"
  git -C "$repo" rev-parse HEAD
  git -C "$repo" branch --show-current
  git -C "$repo" status --short
  git -C "$repo" remote get-url origin 2>/dev/null | sed -E 's#(https?://)[^/@]+@#\1[REDACTED]@#'
done
echo '=== FIREWALL ==='
if command -v ufw >/dev/null; then ufw status verbose; fi
echo '=== END ==='
