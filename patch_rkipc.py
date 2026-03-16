import re
import sys

def patch_rkipc_ini(resolution="720"):
    """强制注入我们的最优摄像头配置，专治系统覆盖不服"""
    
    # 动态匹配分辨率
    if resolution == "1080":
        w, h = "1920", "1080"
    else:
        # 默认回退到 720P，保护单核 CPU 和 SD 卡 I/O
        w, h = "1280", "720"
        resolution = "720"

    print(f"\n🛠️ 正在拦截并注入自定义摄像头配置 ({resolution}P + VBR)...")
    ini_path = "/userdata/rkipc.ini"
    
    try:
        with open(ini_path, "r") as f:
            config = f.read()

        # 1. 动态注入分辨率 (大幅度减小 CPU 和内存压力)
        config = re.sub(r"max_width\s*=\s*\d+", f"max_width = {w}", config)
        config = re.sub(r"max_height\s*=\s*\d+", f"max_height = {h}", config)
        config = re.sub(r"width\s*=\s*\d+", f"width = {w}", config)
        config = re.sub(r"height\s*=\s*\d+", f"height = {h}", config)

        # 👇 核心降温修改：强制将帧率降为 15 帧 (监控标准的黄金帧率)
        config = re.sub(r"dst_frame_rate_num\s*=\s*\d+", "dst_frame_rate_num = 15", config)
        config = re.sub(r"src_frame_rate_num\s*=\s*\d+", "src_frame_rate_num = 15", config)

        # 2. 强制动态码率 VBR (彻底解决画面动起来就模糊变成马赛克的问题)
        config = re.sub(r"rc_mode\s*=\s*\w+", "rc_mode = VBR", config)

        # 3. 强制释放麦克风硬件 (让 rkipc 不要占用，留给我们的 ffmpeg 去扒底层原声)
        config = re.sub(r"\[audio\.0\]\n*enable\s*=\s*\d+", "[audio.0]\nenable = 0", config)

        # 将修改后的内容强行写回
        with open(ini_path, "w") as f:
            f.write(config)
            
        print(f"✅ 完美！配置注入成功，已锁定 {resolution}P 和高画质模式。")
    except Exception as e:
        print(f"⚠️ 配置文件注入失败: {e}")

if __name__ == "__main__":
    # 解析命令行参数 (例如: python patch_rkipc.py 1080)
    target_res = "720" # 默认 720P 护肝模式
    
    if len(sys.argv) > 1:
        param = sys.argv[1]
        if param == "1080":
            target_res = "1080"
        elif param == "720":
            target_res = "720"
        else:
            print(f"⚠️ [参数错误] 不支持的参数 '{param}'，仅支持 1080 或 720。将回退到默认 720P 配置！")
            
    patch_rkipc_ini(target_res)