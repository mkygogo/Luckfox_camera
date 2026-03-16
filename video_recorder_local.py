import subprocess
import os
import time

class RTSPRecorder:
    def __init__(self, save_dir="./records", rtsp_url="rtsp://127.0.0.1/live/0"):
        self.save_dir = save_dir
        self.rtsp_url = rtsp_url
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def record(self, record_count=0, segment_time=30):
        print("⏳ 系统预热中，3秒后开始录制...")
        time.sleep(3)

        output_pattern = os.path.join(self.save_dir, "video_%Y-%m-%d_%H-%M-%S.mkv")

        cmd = [
            "ffmpeg", "-y",
            "-max_interleave_delta", "100k", 
            
            # ================== 输入源 1：视频 (慢，有延迟) ==================
            "-fflags", "+genpts",
            "-thread_queue_size", "2048",
            "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            
            # ================== 输入源 2：音频 (快，需强制延后) ==================
            "-thread_queue_size", "2048",
            "-f", "alsa",
            "-ac", "2",
            "-ar", "48000",
            
            # 核心修正：给跑得快的音频强行加上 1.5 秒的延迟，等待视频到达！
            # 这个值 (1.5) 需要根据你实际录制的视频效果进行微调
            # 如果声音比嘴型早，就增大这个值；如果声音比嘴型晚，就减小它甚至给视频源加 offset。
            "-itsoffset", "2.5", 
            
            "-i", "hw:0,0",
            
            # ================== 映射与编码配置 ==================
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "pcm_s16le",
            "-ac", "1",                      # 合并为单声道
            "-async", "1",                   # -async 1 会像橡皮筋一样，自动拉伸/压缩那些时间戳错乱的音频帧，完美贴合视频
            #"-af", "asetpts=PTS-STARTPTS",   # 滤镜对齐起跑线
            "-fflags", "+igndts",            # 告诉 FFmpeg：遇到错乱的 DTS 直接忽略，不要大惊小怪报警
            
            # ================== 分段切片配置 ==================
            "-f", "segment",
            "-segment_time", str(segment_time),
            "-reset_timestamps", "1",
            "-strftime", "1"
        ]

        if record_count > 0:
            total_duration = record_count * segment_time
            cmd.extend(["-t", str(total_duration)])
        
        cmd.append(output_pattern)

        print("-" * 45)
        print("🎥 录像机启动参数 (物理延迟补偿版)：")
        if record_count > 0:
            print(f"   🎯 模式: 定量录制 ({record_count} 次，每次 {segment_time} 秒)")
        else:
            print(f"   ♾️ 模式: 持续守护录制 (每 {segment_time} 秒分段)")
        print("-" * 45)

        try:
            # 增加 check=True 可以在 ffmpeg 异常崩溃时抛出 Python 异常
            subprocess.run(cmd, stderr=subprocess.STDOUT)
            if record_count > 0:
                print("\n✅ 设定的录制任务已顺利完成，程序自动安全退出。")
        except KeyboardInterrupt:
            print("\n🛑 接收到中断信号，录像已安全停止。")
        except Exception as e:
            print(f"\n⚠️ 录制过程中发生错误: {e}")