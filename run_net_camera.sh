#!/bin/sh

# ========================================
# ⚙️ 核心系统参数配置
# ========================================
# 模式可选: "native" (原生直录，零CPU消耗) 或 "ffmpeg" (支持音频,外挂录像，切片精准)
WORK_MODE="ffmpeg"  
# 分辨率可选: "720" 或 "1080"
RESOLUTION="720"    
# ========================================

source /etc/profile 2>/dev/null
export PATH=$PATH:/oem/usr/bin:/usr/bin:/bin:/sbin:/usr/sbin
export LD_LIBRARY_PATH=/oem/usr/lib:/usr/lib:/lib:$LD_LIBRARY_PATH

echo "========================================"
echo "🚀 启动双擎录像监控系统 (当前模式: $WORK_MODE, $RESOLUTION P) ..."
echo "========================================"

echo timer > /sys/class/leds/work/trigger
echo 100 > /sys/class/leds/work/delay_on
echo 100 > /sys/class/leds/work/delay_off

echo "▶️ [1/5] 初始网络连接与时间校准..."
python set_wifi.py

echo "🔌 正在强制禁用 USB 虚拟网卡接口(防幽灵插拔)..."
ifconfig usb0 down 2>/dev/null
rmmod rk_usb_network 2>/dev/null

echo "⏳ 让路由器喘口气 (等待 12 秒)..."
sleep 12

echo "▶️ [2/5] 停止旧服务并清理网络冲突..."
RkLunch-stop.sh

echo "▶️ [3/5] 根据 $WORK_MODE 模式自动注入 $RESOLUTION P 高清配置..."
python patch_rkipc.py $WORK_MODE $RESOLUTION

echo "▶️ [4/5] 启动摄像头，并交出网络接管权..."
RkLunch.sh &

echo "⏳ 等待底层服务和网络路由彻底稳定 ..."
sleep 10

echo none > /sys/class/leds/work/trigger
echo 1 > /sys/class/leds/work/brightness

echo "▶️ [5/5] 启动 Python 监控主程序..."
# 将模式作为参数传入主程序
nice -n 10 python -u main.py $WORK_MODE 0

echo "========================================"
echo "👋 系统已安全退出。"
echo "========================================"