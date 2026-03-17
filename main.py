import sys
from video_recorder_multithread import RTSPRecorder

if __name__ == "__main__":
    mode = "native"
    target_count = 0
    
    # 动态参数解析: python main.py <native|ffmpeg> <次数>
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            target_count = int(sys.argv[2])
        except ValueError:
            target_count = 0
            
    print(f"🔧 [启动参数] 工作模式: {mode}, 录制限量: {target_count if target_count > 0 else '无限守护'}")
    
    # 初始化录像机引擎
    recorder = RTSPRecorder(mode=mode, save_dir="./records", rtsp_url="rtsp://127.0.0.1/live/0")
    
    # 启动流水线
    recorder.record(record_count=target_count, segment_time=30)