import os
import subprocess
import time
import socket
import struct

# ================= 配置区 =================
SSID = "HUAWEI-JR"
PASSWORD = "jr825319"
INTERFACE = "wlan0"  # 默认的无线网卡名称
CONF_FILE = "/etc/wpa_supplicant.conf"
NTP_SERVER = "ntp.aliyun.com"  # 阿里云 NTP 服务器
# ==========================================

def setup_wifi_and_time():
    print(f"🔄 准备连接 Wi-Fi: {SSID}...")

    # 1. 生成并写入 wpa_supplicant 配置文件
    wpa_config = f"""ctrl_interface=/var/run/wpa_supplicant
ap_scan=1
update_config=1
network={{
    ssid="{SSID}"
    psk="{PASSWORD}"
}}
"""
    try:
        with open(CONF_FILE, "w") as f:
            f.write(wpa_config)
        print("✅ 网络配置文件已更新")
    except Exception as e:
        print(f"❌ 写入配置文件失败: {e}")
        return

    # 2. 清理可能卡住的旧网络进程
    print("🧹 清理旧的网络进程...")
    subprocess.run("killall wpa_supplicant", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run("killall udhcpc", shell=True, stderr=subprocess.DEVNULL)
    time.sleep(1)

    # 3. 唤醒网卡并启动连接服务
    print("🚀 启动无线网卡并尝试连接...")
    subprocess.run(f"ifconfig {INTERFACE} up", shell=True)
    
    start_wpa_cmd = f"wpa_supplicant -B -i {INTERFACE} -c {CONF_FILE}"
    subprocess.run(start_wpa_cmd, shell=True)
    
    print("⏳ 等待握手认证...")
    time.sleep(4)

    # 4. 向路由器请求分配动态 IP
    print("🌐 正在向路由器请求 IP 地址...")
    result = subprocess.run(f"udhcpc -i {INTERFACE} -q", shell=True, stdout=subprocess.DEVNULL)
    
    if result.returncode == 0:
        print("\n🎉 Wi-Fi 连接成功！")
        print("你的板子现在的 IP 信息如下：")
        subprocess.run(f"ifconfig {INTERFACE} | grep 'inet '", shell=True)
        
        # ================= 5. 强写 DNS (专治嵌入式系统不服) =================
        print("\n🛠️ 正在修复系统 DNS 解析...")
        try:
            with open("/etc/resolv.conf", "w") as f:
                f.write("nameserver 114.114.114.114\n")  # 国内最稳定的 114 DNS
                f.write("nameserver 192.168.3.1\n")      # 备用：你的路由器网关
                f.write("nameserver 8.8.8.8\n")          # 备用：谷歌 DNS
            print("✅ DNS 配置写入完成！")
        except Exception as e:
            print(f"⚠️ DNS 写入失败: {e}")
        # ===============================================================

        # ---------------- 6. 纯 Python NTP 强制对时逻辑 ----------------
        print(f"\n⏳ 正在绕过系统命令，使用纯 Python 底层请求 {NTP_SERVER}...")
        try:
            # 建立 UDP 网络连接
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(8.0)  # 设置 8 秒超时
            
            # 构造 NTP 协议的请求魔法包
            msg = b'\x1b' + 47 * b'\0'
            client.sendto(msg, (NTP_SERVER, 123))
            
            # 接收服务器响应
            msg, address = client.recvfrom(1024)
            if msg:
                # 解包获取时间数据
                t = struct.unpack('!12I', msg)[10]
                # 转换成 Unix 时间戳，并强制加上 8 小时 (28800秒) 补偿北京时间时区
                timestamp = t - 2208988800 + 28800
                
                # 格式化时间字符串
                time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
                
                # 强制使用 date -s 写入系统
                subprocess.run(f'date -s "{time_str}"', shell=True, stdout=subprocess.DEVNULL)
                subprocess.run('hwclock -w', shell=True, stderr=subprocess.DEVNULL)
                
                print(f"✅ 纯 Python 对时成功！已校准为北京时间。")
                
                # 极其关键：对时成功后重启视频服务，刷新画面上的时间水印
                print("🔄 正在刷新系统推流服务以更新时间戳水印...")
                subprocess.run("RkLunch-stop.sh", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                subprocess.run("RkLunch.sh &", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                
            else:
                print("⚠️ 收到空数据。")
                
        except socket.gaierror:
            print("❌ DNS 解析失败！你的板子可能无法访问外网，请检查路由器配置。")
        except socket.timeout:
            print("❌ NTP 请求超时！UDP 123 端口可能被封，或者路由器没网。")
        except Exception as e:
            print(f"⚠️ 纯 Python 对时发生未知错误: {e}")
        
        # 打印最终系统确认的时间
        print("\n当前系统真实时间为：")
        subprocess.run("date", shell=True)
        # -----------------------------------------------------------
        
    else:
        print("\n❌ 获取 IP 失败。")
        print("请检查：1. 密码是否正确；2. 板子是否插了正确的 Wi-Fi 模块。")



if __name__ == "__main__":
    setup_wifi_and_time()