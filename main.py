import sys
from video_recorder_multithread import RTSPRecorder


if __name__ == "__main__":
    # ==========================================
    # 默认值：0 代表无限循环录制（生产部署模式）
    # ==========================================
    target_count = 0
    
    # 动态参数解析：允许通过终端命令传入指定次数 (例如: python main.py 3)
    if len(sys.argv) > 1:
        try:
            target_count = int(sys.argv[1])
            print(f"🔧 [调试模式] 接收到外部指令，本次将限量录制: {target_count} 个切片")
        except ValueError:
            print("⚠️ [参数错误] 传入的次数不是数字，将回退到默认无限录制模式！")
            target_count = 0
            
    # 初始化录像机实例
    recorder = RTSPRecorder(save_dir="./records", rtsp_url="rtsp://127.0.0.1/live/0")
    
    # 启动核心流水线 (segment_time=30表示每个视频30秒)
    recorder.record(record_count=target_count, segment_time=30)