import subprocess
import os
import time
import glob
import json
import urllib.request
import uuid
import concurrent.futures

class RTSPRecorder:
    def __init__(self, save_dir="./records", rtsp_url="rtsp://127.0.0.1/live/0"):
        self.save_dir = save_dir
        self.rtsp_url = rtsp_url
        self.server_url = "http://192.168.3.6:8920/upload/"
        self.uploaded_files = set() # 这里现在只存纯文件名！

        # 核心：初始化 1 个工人的线程池
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        try:
            # 执行 Linux 命令提取当前的默认网关 IP
            self.gateway = os.popen("ip route show default | awk '/default/ {print $3}'").read().strip()
            if self.gateway:
                print(f"🛡️ [网络守护] 成功捕获当前动态网关: {self.gateway}，已开启防断网保护伞！")
            else:
                print("⚠️ [网络守护] 未捕获到网关，这可能会在后续导致断网。")
        except Exception as e:
            self.gateway = None

    def _upload_task(self, filepath):
        """后台独立上传线程 - 纯内存发送版 (斩断 SD 卡 I/O 冲突)"""
        try:
            if not os.path.exists(filepath):
                return
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            
            print(f"\n🚀 [上传启动] 正在将视频拉入内存: {filename}...")

            # ==========================================
            # 🛡️ 核心绝杀：瞬间读取全部文件到内存，立刻释放 SD 卡！
            # ==========================================
            with open(filepath, 'rb') as f:
                video_data = f.read()
                
            print(f"📦 载入内存完毕 ({file_size/1024/1024:.2f} MB)！SD 卡已释放，开始网络投递...")

            boundary = uuid.uuid4().hex
            header_part = (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f'Content-Type: application/octet-stream\r\n\r\n'
            ).encode('utf-8')
            footer_part = f'\r\n--{boundary}--\r\n'.encode('utf-8')
            content_length = len(header_part) + file_size + len(footer_part)

            class MemoryStream:
                def __iter__(self):
                    yield header_part
                    chunk_size = 32768
                    for i in range(0, len(video_data), chunk_size):
                        yield video_data[i:i+chunk_size]
                        time.sleep(0.1) 
                    yield footer_part

            headers = {
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Content-Length': str(content_length)
            }
            
            # ==========================================
            # 🛡️ 无限次网络自愈重试
            # ==========================================
            attempt = 1
            while True:
                print(f"🔄 [网络守护] 准备第 {attempt} 次投递...")
                
                # 1. 尝试修复网关
                if self.gateway:
                    os.system(f"route add default gw {self.gateway} dev wlan0 >/dev/null 2>&1")
                
                # 2. 动态检查网络枢纽是否通畅
                target_ip = self.gateway if self.gateway else "8.8.8.8"
                ping_res = os.system(f"ping -c 1 -W 1 {target_ip} >/dev/null 2>&1")
                
                if ping_res != 0:
                    print(f"⚠️ [硬件掉电] 无法连接到网络枢纽 ({target_ip})，等待 Wi-Fi 重连 (5秒)...")
                    time.sleep(5)
                    if not self.gateway:
                        self.gateway = os.popen("ip route show default | awk '/default/ {print $3}'").read().strip()
                    continue 
                
                # 网络通了，开始发车！
                req = urllib.request.Request(self.server_url, data=MemoryStream(), headers=headers, method='POST')

                try:
                    with urllib.request.urlopen(req, timeout=120) as response:
                        ret_data = response.read().decode('utf-8')
                        try:
                            ret_json = json.loads(ret_data)
                            task_id = ret_json.get("taskid", "未返回ID")
                            print(f"✅ [上传成功] {filename} 已接单! TaskID: {task_id}")
                        except json.JSONDecodeError:
                            print(f"✅ [上传成功] {filename} 服务器返回: {ret_data}")
                        
                        # ✅ 修改点：成功后只做 break，不在这里执行清理！
                        break 
                        
                except Exception as e:
                    print(f"⚠️ [上传失败] 传输中断 ({e})，2秒后重试...")
                    attempt += 1
                    time.sleep(2)
            
            # ==========================================
            # 🧹 统一善后处理 (成功跳出 while 循环后，仅在此处执行一次)
            # ==========================================
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"🧹 [清理空间] 本地视频 {filename} 已阅即焚，成功销毁。")
                
            if 'video_data' in locals():
                del video_data

        except Exception as e:
            print(f"❌ [线程内部错误] {filepath}: {e}")
            # 异常时也要确保释放大内存
            if 'video_data' in locals():
                del video_data

    def record(self, record_count=0, segment_time=30):
        # 开机免疫：剥离所有路径，只提取纯文件名存入黑名单！
        existing_files = glob.glob(os.path.join(self.save_dir, '*.mkv'))
        for old_file in existing_files:
            pure_name = os.path.basename(old_file)
            self.uploaded_files.add(pure_name)
            
        if existing_files:
            print(f"{len(existing_files)} 个历史老视频，不上传。")

        print("⏳ 系统预热中，3秒后开始录制...")
        time.sleep(3)

        output_pattern = os.path.join(self.save_dir, "video_%Y-%m-%d_%H-%M-%S.mkv")

        cmd = [
            "ffmpeg", "-y",
            "-max_interleave_delta", "100k", 
            "-fflags", "+genpts",
            "-thread_queue_size", "2048",
            "-rtsp_transport", "udp",
            "-buffer_size", "10485760",
            "-i", self.rtsp_url,
            "-thread_queue_size", "2048",
            "-f", "alsa",
            "-ac", "2",
            "-ar", "48000",
            "-itsoffset", "2.5", 
            "-i", "hw:0,0",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "pcm_s16le",
            "-ac", "1",                      
            "-async", "1",                   
            "-fflags", "+igndts",            
            "-f", "segment",
            "-segment_time", str(segment_time),
            "-reset_timestamps", "1",
            "-strftime", "1"
        ]

        if record_count > 0:
            total_duration = record_count * segment_time
            cmd.extend(["-t", str(total_duration)])
            print("-" * 45)
            print(f"🎥 启动模式：【无缝切片定量测试】 (录制 {record_count} 个切片，每个 {segment_time} 秒)")
        else:
            print("-" * 45)
            print(f"🎥 启动模式：【单核排队无缝守护】 (无限监控，切片即传)")
        
        cmd.append(output_pattern)
        print("-" * 45)

        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        #process = subprocess.Popen(cmd)

        try:
            while True:
                time.sleep(3)
                is_running = process.poll() is None
                
                # 获取目录下所有视频文件
                files = sorted(glob.glob(os.path.join(self.save_dir, '*.mkv')))
                
                if is_running:
                    completed_files = files[:-1] if len(files) > 1 else []
                else:
                    completed_files = files
                    
                for f in completed_files:
                    pure_name = os.path.basename(f) # 核心防错：永远只拿纯文件名比较
                    
                    if pure_name not in self.uploaded_files:
                        if os.path.getsize(f) > 0:
                            self.uploaded_files.add(pure_name)
                            # ✅ 正确做法：把上传任务提交给线程池排队执行！
                            self.executor.submit(self._upload_task, f)
                        else:
                            pass
                        
                if not is_running:
                    print("\n🏁 底层录像已按计划完成，等待单核队列中剩余的上传任务...")
                    # ✅ 正确做法：强迫主线程安全等待，直到线程池里所有排队的文件都传完才退出！
                    self.executor.shutdown(wait=True)
                    print("🎉 所有排队任务均已完美收官，程序安全退出。")
                    break

        except KeyboardInterrupt:
            print("\n🛑 接收到手动停止中断信号。正在安全关闭摄像头...")
            process.terminate()
            process.wait()
            # 接收到 Ctrl+C 时，也等待正在传的文件传完再走
            self.executor.shutdown(wait=True)
            print("👋 录像已彻底终止。")