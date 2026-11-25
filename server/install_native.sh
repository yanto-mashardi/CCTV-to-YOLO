#!/usr/bin/env bash
# Install standalone relay without touching BIMA2 services or firewall.
set -euo pipefail
[[ $(id -u) == 0 ]]
ROOT=/opt/CCTV_RELAY
VERSION=1.15.0
case $(uname -m) in x86_64) arch=amd64;; aarch64) arch=arm64;; *) echo 'Unsupported architecture';exit 1;; esac
if systemctl is-active --quiet cctv-relay.service; then echo 'Relay already active; no changes';exit 0;fi
if ss -lntH | awk '{print $4}' | grep -Eq ':(1935|8554)$'; then echo 'RTMP or RTSP port occupied';exit 1;fi
tmp=$(mktemp -d);trap 'rm -rf "$tmp"' EXIT
asset="mediamtx_v${VERSION}_linux_${arch}.tar.gz"
curl -fsSL --retry 3 "https://api.github.com/repos/bluenviron/mediamtx/releases/tags/v$VERSION" -o "$tmp/release.json"
digest=$(python3 - "$tmp/release.json" "$asset" <<'PY'
import json,sys,re
a=next(x for x in json.load(open(sys.argv[1]))["assets"] if x["name"]==sys.argv[2])
d=a.get("digest","")
assert re.fullmatch("sha256:[0-9a-f]{64}",d),"Release digest unavailable"
print(d.split(":")[1])
PY
)
curl -fsSL --retry 3 "https://github.com/bluenviron/mediamtx/releases/download/v$VERSION/$asset" -o "$tmp/$asset"
echo "$digest  $tmp/$asset" | sha256sum -c -
tar -xzf "$tmp/$asset" -C "$tmp" mediamtx
id cctvrelay >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin cctvrelay
install -d -o root -g cctvrelay -m 0750 "$ROOT"
install -m 0755 "$tmp/mediamtx" "$ROOT/mediamtx"
if [[ ! -s "$ROOT/mediamtx.yml" ]]; then
 umask 077
 B=$(openssl rand -hex 16);P=$(openssl rand -hex 16);R=$(openssl rand -hex 16)
 sed -e "s/REPLACE_BENGKALIS_PASSWORD/$B/" -e "s/REPLACE_PAKNING_PASSWORD/$P/" -e "s/REPLACE_READER_PASSWORD/$R/" "$(dirname "$(realpath "$0")")/mediamtx.yml.example" > "$ROOT/mediamtx.yml"
 chown root:cctvrelay "$ROOT/mediamtx.yml";chmod 640 "$ROOT/mediamtx.yml"
fi
cat > /etc/systemd/system/cctv-relay.service <<'UNIT'
[Unit]
Description=CCTV RTMP to RTSP relay
After=network-online.target
[Service]
User=cctvrelay
Group=cctvrelay
ExecStart=/opt/CCTV_RELAY/mediamtx /opt/CCTV_RELAY/mediamtx.yml
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
MemoryMax=256M
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now cctv-relay.service
sleep 2
systemctl is-active --quiet cctv-relay.service
ss -lntp | grep -E ':(1935|8554)\b'
echo 'Relay active. Check provider firewall for TCP 1935 and 8554. No firewall rules changed.'
echo 'Credentials: /opt/CCTV_RELAY/mediamtx.yml (root-readable; do not share publicly)'
