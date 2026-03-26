#!/bin/sh

# ========================================
# Core system mode config: "record" or "live"
# ========================================
RUN_MODE="live"
RESOLUTION="720"
# ========================================

source /etc/profile 2>/dev/null
export PATH=$PATH:/oem/usr/bin:/usr/bin:/bin:/sbin:/usr/sbin
export LD_LIBRARY_PATH=/oem/usr/lib:/usr/lib:/lib:$LD_LIBRARY_PATH

get_wlan_ip() {
    local detected_ip
    detected_ip=$(ifconfig wlan0 2>/dev/null | awk '/inet addr:/ {print $2}' | cut -d: -f2)
    if [ -z "$detected_ip" ]; then
        detected_ip=$(ip addr show wlan0 2>/dev/null | awk '/inet / {print $2}' | cut -d/ -f1 | head -n 1)
    fi
    if [ -z "$detected_ip" ]; then
        detected_ip=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')
    fi
    echo "$detected_ip"
}

safe_sysfs_write() {
    local value="$1"
    local path="$2"
    if [ -w "$path" ]; then
        echo "$value" > "$path"
    fi
}

echo "========================================"
if [ "$RUN_MODE" = "record" ]; then
    echo "Starting record mode ($RESOLUTION P) ..."
else
    echo "Starting live mode ($RESOLUTION P) ..."
fi
echo "========================================"

safe_sysfs_write timer /sys/class/leds/work/trigger
safe_sysfs_write 100 /sys/class/leds/work/delay_on
safe_sysfs_write 100 /sys/class/leds/work/delay_off

echo "[1/5] Stopping old services..."
RkLunch-stop.sh

echo "[2/5] Applying $RESOLUTION P config..."
if [ "$RUN_MODE" = "record" ]; then
    python patch_rkipc.py ffmpeg $RESOLUTION
else
    python patch_rkipc.py ffmpeg $RESOLUTION
fi
echo "[2.1/5] Effective [audio.0] section:"
sed -n '/^\[audio\.0\]/,/^\[/p' /userdata/rkipc.ini | sed '$d'
echo "[2.15/5] Effective [video.source] section:"
sed -n '/^\[video\.source\]/,/^\[/p' /userdata/rkipc.ini | sed '$d'
echo "[2.2/5] Effective [storage.0] section:"
sed -n '/^\[storage\.0\]/,/^\[/p' /userdata/rkipc.ini | sed '$d'
echo "[2.3/5] Effective [video.0] section:"
sed -n '/^\[video\.0\]/,/^\[/p' /userdata/rkipc.ini | sed '$d'
echo "[2.4/5] Effective [video.1] section:"
sed -n '/^\[video\.1\]/,/^\[/p' /userdata/rkipc.ini | sed '$d'

echo "[3/5] Starting camera engine..."
RkLunch.sh &

echo "Waiting 15 seconds for rkipc to stabilize..."
sleep 15

echo "[4/5] Reclaiming network control and syncing Wi-Fi..."
killall udhcpc 2>/dev/null
ifconfig usb0 down 2>/dev/null
rmmod rk_usb_network 2>/dev/null

python set_wifi.py

BOARD_IP=""
IP_WAIT_COUNT=0
while [ -z "$BOARD_IP" ] && [ "$IP_WAIT_COUNT" -lt 10 ]; do
    BOARD_IP=$(get_wlan_ip)
    if [ -n "$BOARD_IP" ]; then
        break
    fi
    IP_WAIT_COUNT=$((IP_WAIT_COUNT + 1))
    sleep 1
done

if [ -z "$BOARD_IP" ]; then
    BOARD_IP="127.0.0.1"
    echo "[warn] wlan0 IP not ready, temporary fallback to $BOARD_IP"
fi

safe_sysfs_write none /sys/class/leds/work/trigger
safe_sysfs_write 1 /sys/class/leds/work/brightness

if [ "$RUN_MODE" = "record" ]; then
    echo "[5/5] Starting Python monitor..."
    nice -n 10 python -u main.py ffmpeg 0
else
    echo "[5/5] Starting muxed RTSP relay..."
    echo "=========================================================="
    echo "LAN live streams ready:"
    echo "   Muxed AV    : http://$BOARD_IP:8080/live.ts"
    echo "   Video only  : rtsp://$BOARD_IP/live/0"
    echo "   Sub stream  : rtsp://$BOARD_IP/live/1"
    echo "=========================================================="
    exec python -u live_rtsp_relay.py "$BOARD_IP"
fi