#!/bin/bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "Usage: sudo bash install-sounds.sh FILE.mp3 [FILE.wav ...]" >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash install-sounds.sh FILE.mp3 [FILE.wav ...]" >&2
  exit 1
fi
if ! id attendance >/dev/null 2>&1; then
  echo "Error: run install.sh first to create the attendance user." >&2
  exit 1
fi

# Check all inputs before copying any files.
for source in "$@"; do
  if [ ! -f "$source" ] || [ ! -r "$source" ]; then
    echo "Error: not a readable file: $source" >&2
    exit 1
  fi
  case "${source,,}" in
    *.mp3|*.wav) ;;
    *) echo "Error: sound must be an MP3 or WAV file: $source" >&2; exit 1 ;;
  esac
done

destination=/etc/attendance-terminal/sounds
install -d -o root -g attendance -m 0750 /etc/attendance-terminal "$destination"
for source in "$@"; do
  target="$destination/$(basename -- "$source")"
  install -o root -g attendance -m 0640 -- "$source" "$target"
  if ! runuser -u attendance -- test -r "$target"; then
    echo "Error: attendance cannot read $target" >&2
    exit 1
  fi
  echo "Installed: $target"
done

echo "Set notification_sound/startup_sound in /etc/attendance-terminal/config.json to the installed paths."
echo "Then run: sudo systemctl restart attendance-terminal"
