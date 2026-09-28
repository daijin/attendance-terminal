#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo ./install.sh" >&2
  exit 1
fi

project_dir="$(cd "$(dirname "$0")" && pwd)"
. /etc/os-release
if [ "${VERSION_CODENAME:-}" != "trixie" ]; then
  echo "Warning: this installer is tested for Raspberry Pi OS Trixie; detected ${VERSION_CODENAME:-unknown}." >&2
fi
if [ "$(dpkg --print-architecture)" != "arm64" ]; then
  echo "Warning: the requested target is arm64; detected $(dpkg --print-architecture)." >&2
fi
apt-get update
apt-get install -y python3-venv python3-dev swig libpcsclite-dev pcscd pcsc-tools libccid i2c-tools alsa-utils mpg123 systemd-timesyncd

id attendance >/dev/null 2>&1 || useradd --system --home /var/lib/attendance-terminal --shell /usr/sbin/nologin attendance
usermod -a -G audio,gpio attendance
install -d -o attendance -g attendance -m 0750 /var/lib/attendance-terminal
install -d -o root -g attendance -m 0750 /etc/attendance-terminal
install -d -o root -g attendance -m 0750 /etc/attendance-terminal/sounds
install -d -o root -g root -m 0755 /opt/attendance-terminal /usr/local/lib/attendance-terminal

cp -a "$project_dir/src" "$project_dir/pyproject.toml" /opt/attendance-terminal/
python3 -m venv /opt/attendance-terminal/venv
/opt/attendance-terminal/venv/bin/pip install --upgrade pip
/opt/attendance-terminal/venv/bin/pip install '/opt/attendance-terminal[gpio]'

if [ ! -f /etc/attendance-terminal/config.json ]; then
  install -o root -g attendance -m 0640 "$project_dir/config.example.json" /etc/attendance-terminal/config.json
fi
install -o root -g root -m 0755 "$project_dir/systemd/sync-clock.sh" /usr/local/lib/attendance-terminal/sync-clock.sh
install -o root -g root -m 0644 "$project_dir/systemd/attendance-clock.service" /etc/systemd/system/
install -o root -g root -m 0644 "$project_dir/systemd/attendance-terminal.service" /etc/systemd/system/
install -o root -g root -m 0644 "$project_dir/systemd/60-attendance-terminal-pcsc.rules" /etc/polkit-1/rules.d/

systemctl daemon-reload
systemctl enable pcscd.socket attendance-clock.service attendance-terminal.service

echo "Installed. Edit /etc/attendance-terminal/config.json, configure the RTC, then reboot."
