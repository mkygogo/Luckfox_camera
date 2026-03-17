import re
import sys

def patch_rkipc_ini(mode="native", resolution="720"):
    print(f"\n🛠️ 正在注入配置: [模式={mode}] [分辨率={resolution}P]...")
    ini_path = "/userdata/rkipc.ini"
    
    try:
        with open(ini_path, "r") as f:
            config = f.read()

        # 1. 动态注入分辨率
        w, h = ("1920", "1080") if resolution == "1080" else ("1280", "720")
        config = re.sub(r"max_width\s*=\s*\d+", f"max_width = {w}", config)
        config = re.sub(r"max_height\s*=\s*\d+", f"max_height = {h}", config)
        config = re.sub(r"width\s*=\s*\d+", f"width = {w}", config)
        config = re.sub(r"height\s*=\s*\d+", f"height = {h}", config)

        # 2. 降温配置: 强制 15 帧, 动态码率 VBR
        config = re.sub(r"dst_frame_rate_num\s*=\s*\d+", "dst_frame_rate_num = 15", config)
        config = re.sub(r"src_frame_rate_num\s*=\s*\d+", "src_frame_rate_num = 15", config)
        config = re.sub(r"rc_mode\s*=\s*\w+", "rc_mode = VBR", config)
        #强制设置 GOP，确保每秒都有关键帧，拯救 FFmpeg 的切片强迫症！
        config = re.sub(r"gop\s*=\s*\d+", "gop = 15", config)

        # 3. 核心：双模切换逻辑
        if mode == "native":
            # 开启 rkipc 原生麦克风采集，关闭降噪滤镜防崩溃
            config = re.sub(r"\[audio\.0\]\n*enable\s*=\s*\d+", "[audio.0]\nenable = 1", config)
            config = re.sub(r"enable_vqe\s*=\s*\d+", "enable_vqe = 0", config)
            
            # 👇 核心修复 1：向固件妥协！因为板子不支持 AAC，必须退回 G711A (8000Hz 单声道)
            config = re.sub(r"encode_type\s*=\s*\w+", "encode_type = G711A", config)
            config = re.sub(r"sample_rate\s*=\s*\d+", "sample_rate = 8000", config)
            config = re.sub(r"channels\s*=\s*\d+", "channels = 1", config)
            config = re.sub(r"bit_rate\s*=\s*\d+", "bit_rate = 16000", config)
            config = re.sub(r"frame_size\s*=\s*\d+", "frame_size = 1152", config)
            
            # 👇 核心修复 2：强迫 Muxer 把音频轨道写进 MP4！
            config = re.sub(r"\[storage\.0\]\n*enable\s*=\s*\d+", "[storage.0]\nenable = 1\nrecord_audio = 1", config)
            config = re.sub(r"file_duration\s*=\s*\d+", "file_duration = 30", config)
        else:
            # ffmpeg 模式: 阉割 rkipc 的麦克风和存储，留给外部 FFmpeg 独占
            config = re.sub(r"\[audio\.0\]\n*enable\s*=\s*\d+", "[audio.0]\nenable = 0", config)
            config = re.sub(r"\[storage\.0\]\n*enable\s*=\s*\d+", "[storage.0]\nenable = 0", config)

        with open(ini_path, "w") as f:
            f.write(config)
            
        print("✅ 完美！系统底层已重构完毕。")
    except Exception as e:
        print(f"⚠️ 配置文件注入失败: {e}")

if __name__ == "__main__":
    work_mode = sys.argv[1] if len(sys.argv) > 1 else "native"
    target_res = sys.argv[2] if len(sys.argv) > 2 else "720"
    
    if work_mode not in ["native", "ffmpeg"]:
        work_mode = "native"
    if target_res not in ["720", "1080"]:
        target_res = "720"
        
    patch_rkipc_ini(work_mode, target_res)