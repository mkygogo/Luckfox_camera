import subprocess
import os
import time
import glob
import json
import urllib.request
import uuid

class RTSPRecorder:
    def __init__(self, save_dir="./records", rtsp_url="rtsp://127.0.0.1/live/0"):
        self.save_dir = save_dir
        self.rtsp_url = rtsp_url
        
        # ======== 你的 FastAPI 服务器地址 ========
        self.server_url = "http://192.168.3.6:8920/upload/"
        
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def upload_latest_video(self):
        """纯 Python 内存安全版流式上传"""
        list_of_files = glob.glob(os.path.join(self.save_dir, '*.mkv'))
        if not list_of_files:
            print("⚠️ 没找到可以上传的视频文件。")
            return

        latest_file = max(list_of_files, key=os.path.getctime)
        filename = os.path.basename(latest_file)
        
        print(f"\n" + "="*45)
        print(f"⬆️ 开始向服务器投递视频 (纯净流式传输)...")
        print(f"📁 本地文件: {latest_file}")
        print(f"🌐 目标地址: {self.server_url}")

        # 1. 构造表单的边界(Boundary)
        boundary = uuid.uuid4().hex
        
        # 2. 构造 multipart 的头部和尾部数据
        header_part = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n'
        ).encode('utf-8')
        footer_part = f'\r\n--{boundary}--\r\n'.encode('utf-8')
        
        file_size = os.path.getsize(latest_file)
        content_length = len(header_part) + file_size + len(footer_part)

        # 3. 核心魔法：定义数据生成器 (Generator)
        # 每次只往内存里读 8KB 数据发送，防止把 64MB 的板子撑死！
        class StreamingFile:
            def __iter__(self):
                yield header_part
                with open(latest_file, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
                yield footer_part

        # 4. 组装 HTTP 请求头
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(content_length)
        }

        # 5. 发起请求
        req = urllib.request.Request(self.server_url, data=StreamingFile(), headers=headers, method='POST')
        
        try:
            print(f"⏳ 正在上传 {file_size / 1024 / 1024:.2f} MB 的视频，请稍候...")
            # 留出 120 秒的超时时间，因为局域网传输也有耗时
            with urllib.request.urlopen(req, timeout=120) as response:
                ret_data = response.read().decode('utf-8')
                try:
                    ret_json = json.loads(ret_data)
                    task_id = ret_json.get("taskid", "未返回ID")
                    print(f"✅ 上传成功！服务器已接单。")
                    print(f"🏷️ 任务 ID: {task_id}")
                except json.JSONDecodeError:
                    print(f"✅ 上传可能已成功，服务器返回: {ret_data}")
        except Exception as e:
            print(f"❌ 上传失败，请检查服务器是否开启: {e}")
        print("="*45 + "\n")

    def record(self, record_count=0, segment_time=30):
        print("⏳ 系统预热中，3秒后开始录制...")
        time.sleep(3)

        output_pattern = os.path.join(self.save_dir, "video_%Y-%m-%d_%H-%M-%S.mkv")

        cmd = [
            "ffmpeg", "-y",
            "-max_interleave_delta", "100k", 
            
            # ================== 输入源 1：视频 ==================
            "-fflags", "+genpts",
            "-thread_queue_size", "2048",
            "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            
            # ================== 输入源 2：音频 ==================
            "-thread_queue_size", "2048",
            "-f", "alsa",
            "-ac", "2",
            "-ar", "48000",
            "-itsoffset", "2.5", 
            "-i", "hw:0,0",
            
            # ================== 映射与编码配置 ==================
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "pcm_s16le",
            "-ac", "1",                      
            "-async", "1",                   
            "-fflags", "+igndts",            
            
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
        print("🎥 录像机启动参数 (带自动流式上传)：")
        if record_count > 0:
            print(f"   🎯 模式: 定量录制 ({record_count} 次，每次 {segment_time} 秒)")
        else:
            print(f"   ♾️ 模式: 持续守护录制 (每 {segment_time} 秒分段)")
        print("-" * 45)

        try:
            subprocess.run(cmd, stderr=subprocess.STDOUT)
            if record_count > 0:
                print("\n✅ 设定的录制任务已顺利完成，准备上传...")
                self.upload_latest_video()
                
        except KeyboardInterrupt:
            print("\n🛑 接收到手动停止中断信号，准备上传刚刚录制的视频...")
            self.upload_latest_video()
        except Exception as e:
            print(f"\n⚠️ 录制过程中发生错误: {e}")