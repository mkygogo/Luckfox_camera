#!/bin/sh

# ========================================
# ⚙️ 核心系统参数配置 "record" "live"
# ========================================
RUN_MODE="live"
RESOLUTION="720"    
# ========================================

source /etc/profile 2>/dev/null
export PATH=$PATH:/oem/usr/bin:/usr/bin:/bin:/sbin:/usr/sbin
export LD_LIBRARY_PATH=/oem/usr/lib:/usr/lib:/lib:$LD_LIBRARY_PATH

echo "========================================"
if [ "$RUN_MODE" = "record" ]; then
    echo "🚀 启动 [后台录像与上传] 模式 ($RESOLUTION P) ..."
else
    echo "🚀 启动 [纯直播推流] 模式 ($RESOLUTION P) ..."
fi
echo "========================================"

echo timer > /sys/class/leds/work/trigger
echo 100 > /sys/class/leds/work/delay_on
echo 100 > /sys/class/leds/work/delay_off

echo "▶️ [1/5] 停止旧服务并清理底层冲突..."
RkLunch-stop.sh

echo "▶️ [2/5] 自动注入 $RESOLUTION P 高清配置..."
python patch_rkipc.py ffmpeg $RESOLUTION

echo "▶️ [3/5] 启动底层摄像头引擎 (容忍其网络扰动)..."
RkLunch.sh &

# 👈 核心防御策略：等待底层 rkipc 启动完毕并捣乱结束
echo "⏳ 等待底层服务稳定 (等待 15 秒)..."
sleep 15

echo "▶️ [4/5] 强行夺回网络控制权并校准时间..."
# 杀死底层引擎擅自调起的网络进程，彻底接管
killall udhcpc 2>/dev/null
ifconfig usb0 down 2>/dev/null
rmmod rk_usb_network 2>/dev/null

# 此时 rkipc 已安静，热点防御已重置，网络将瞬间连通！
python set_wifi.py

# 动态获取真实 IP
BOARD_IP=$(ifconfig wlan0 | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}')
if [ -z "$BOARD_IP" ]; then
    BOARD_IP=$(ip addr show wlan0 | grep "inet " | awk '{print $2}' | cut -d/ -f1)
fi

echo none > /sys/class/leds/work/trigger
echo 1 > /sys/class/leds/work/brightness

if [ "$RUN_MODE" = "record" ]; then
    echo "▶️ [5/5] 启动 Python 监控主程序..."
    nice -n 10 python -u main.py ffmpeg 0
else
    echo "▶️ [5/5] 🎉 纯直播模式已就绪！"
    echo "=========================================================="
    echo "📡 局域网直播流已开启，请使用 VLC 播放："
    echo "   高清主码流 : rtsp://$BOARD_IP/live/0"
    echo "   流畅子码流 : rtsp://$BOARD_IP/live/1"
    echo "=========================================================="
    while true; do sleep 3600; done
fi