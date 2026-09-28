#!/bin/bash
set -eu

# If Internet is available, NTP is authoritative and the result is copied to
# the RTC. Otherwise the RTC is authoritative for this boot.
if timeout 3 bash -c ': < /dev/tcp/8.8.8.8/443' 2>/dev/null; then
  for _attempt in $(seq 1 60); do
    if timedatectl show -p NTPSynchronized --value 2>/dev/null | grep -qx yes; then
      hwclock --systohc --utc
      logger -t attendance-clock 'NTP -> DS1307 synchronization complete'
      exit 0
    fi
    sleep 1
  done
  logger -t attendance-clock 'NTP did not synchronize; falling back to DS1307'
fi

hwclock --hctosys --utc
logger -t attendance-clock 'DS1307 -> system clock synchronization complete'
