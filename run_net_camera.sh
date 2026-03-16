#!/bin/sh

# 1. 强行加载系统全局配置
source /etc/profile 2>/dev/null
# 2. 补全可执行命令路径
export PATH=$PATH:/oem/usr/bin:/usr/bin:/bin:/sbin:/usr/sbin
# 3. 补全核心动态库路径（解决 librockit.so 找不到的问题）
export LD_LIBRARY_PATH=/oem/usr/lib:/usr/lib:/lib:$LD_LIBRARY_PATH

echo "========================================"
echo "🚀 启动一键录像监控系统 ..."
echo "========================================"

# 指示灯狂闪，代表正在连接 Wi-Fi
echo timer > /sys/class/leds/work/trigger
echo 100 > /sys/class/leds/work/delay_on
echo 100 > /sys/class/leds/work/delay_off

echo "▶️ [1/5] 初始网络连接与时间校准..."
# 这一步负责打通物理 Wi-Fi，并获取时间
python set_wifi.py

echo "🔌 正在强制禁用 USB 虚拟网卡接口..."
ifconfig usb0 down 2>/dev/null
# 如果你有 rndis 驱动，直接卸载它 (不一定会执行成功，但加上防身)
rmmod rk_usb_network 2>/dev/null

echo "⏳ 让路由器喘口气 (等待 12 秒)..."
sleep 12

echo "▶️ [2/5] 停止旧服务并清理网络冲突..."
# 这里会执行 killall udhcpc，为后续 rkipc 接管网络腾出干净的空间
RkLunch-stop.sh

echo "▶️ [3/5] 注入 1080P 高清配置..."
python patch_rkipc.py

echo "▶️ [4/5] 启动摄像头，并交出网络接管权..."
RkLunch.sh 

# 
# 给 rkipc 留出时间，让它自己的 DHCP 进程把 IP 和路由表安安稳稳地建好
echo "⏳ 等待底层服务和网络路由彻底稳定 ..."
sleep 10

#指示灯常亮，代表网络已通，进入录像守候状态
echo none > /sys/class/leds/work/trigger
echo 1 > /sys/class/leds/work/brightness

echo "▶️ [5/5] 启动 Python 录像与上传主程序..."
# 👇 核心降温修改：使用 nice -n 10 启动，让 Python 变成低优先级进程，绝不饿死摄像头驱动
nice -n 10 python -u main.py

echo "========================================"
echo "👋 系统已安全退出。"
echo "========================================"