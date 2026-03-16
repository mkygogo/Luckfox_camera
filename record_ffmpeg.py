import subprocess
import os

# ================= 配置区 =================
SAVE_DIR = "./records"

# rkipc 默认提供两个本地流：
# live/0 是主码流 (高分辨率，通常是传感器的最大分辨率)
# live/1 是子码流 (通常是 640x480)
RTSP_URL = "rtsp://127.0.0.1/live/0" 
# ==========================================

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

output_pattern = os.path.join(SAVE_DIR, "video_%Y-%m-%d_%H-%M-%S.mp4")

cmd = [
    "ffmpeg",
    "-rtsp_transport", "tcp",  # 使用 TCP 传输更稳定，防止丢包花屏
    "-i", RTSP_URL,
    "-c:v", "copy",            # 核心魔法：直接复制 VPU 硬件编码好的 H264 流，0 CPU 占用！
    #"-an",                     # 丢弃音频（如果你的摄像头模块带麦克风且需要录音，可删掉此行）
    "-f", "segment",
    "-segment_time", "30",    # 300秒(5分钟)切分一次
    "-reset_timestamps", "1",
    "-strftime", "1",
    output_pattern
]

print(f"🚀 开始截取本地 RTSP 流进行分段保存...")
print(f"录像将保存在: {SAVE_DIR}")

try:
    subprocess.run(cmd)
except KeyboardInterrupt:
    print("\n🛑 录制已终止。")