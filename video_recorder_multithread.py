import subprocess
import os
import time
import glob
import json
import urllib.request
import uuid
import concurrent.futures

class RTSPRecorder:
    def __init__(self, mode="native", save_dir="./records", rtsp_url="rtsp://127.0.0.1/live/0"):
        self.mode = mode
        self.rtsp_url = rtsp_url
        self.server_url = "http://192.168.3.6:8920/upload/"
        self.uploaded_files = set() 
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        # ==========================================
        # 🧠 双引擎目录与扩展名路由
        # ==========================================
        if self.mode == "native":
            self.save_dir = "/userdata/video0" # rkipc默认直录路径
            self.ext = "*.mp4"                 # rkipc默认生成 mp4
        else:
            #self.save_dir = save_dir
            self.save_dir = "/tmp/records"  #将 FFmpeg 写入路径改到 Linux 纯内存盘
            self.ext = "*.mkv"                 # ffmpeg我们设定的 mkv

        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        try:
            self.gateway = os.popen("ip route show default | awk '/default/ {print $3}'").read().strip()
            if self.gateway:
                print(f"🛡️ [网络守护] 成功捕获当前动态网关: {self.gateway}")
        except Exception:
            self.gateway = None

    def _upload_task(self, filepath):
        """后台独立上传线程 - 纯内存发送 + 无限自愈版"""
        try:
            if not os.path.exists(filepath):
                return
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            
            print(f"\n🚀 [上传启动] 正在将视频拉入内存: {filename}...")

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
            # 🛡️ 终极绝杀装甲：无限次网络自愈 + Wi-Fi 假死急救
            # ==========================================
            attempt = 1
            ping_fail_count = 0  # 👈 新增：连续 ping 失败计数器
            
            while True:
                print(f"🔄 [网络守护] 准备第 {attempt} 次投递...")
                
                if self.gateway:
                    os.system(f"route add default gw {self.gateway} dev wlan0 >/dev/null 2>&1")
                
                target_ip = self.gateway if self.gateway else "8.8.8.8"
                ping_res = os.system(f"ping -c 1 -W 1 {target_ip} >/dev/null 2>&1")
                
                if ping_res != 0:
                    ping_fail_count += 1 # 👈 失败次数 +1
                    print(f"⚠️ [硬件掉电] 无法连接到网络枢纽 ({target_ip})，等待 Wi-Fi 重连 (5秒)...")
                    
                    # 👇 核心除颤逻辑：如果连续 12 次 (约 1 分钟) 都不通，说明 Wi-Fi 假死了！
                    if ping_fail_count >= 12:
                        print("⚡ [网络急救] 侦测到 Wi-Fi 假死，正在对无线网卡进行物理重启除颤！")
                        os.system("ifconfig wlan0 down && sleep 2 && ifconfig wlan0 up")
                        ping_fail_count = 0 # 重置计数器，再给它 1 分钟机会
                        
                    time.sleep(5)
                    if not self.gateway:
                        self.gateway = os.popen("ip route show default | awk '/default/ {print $3}'").read().strip()
                    continue 
                
                # 走到这里说明网络通了，清零计数器
                ping_fail_count = 0 
                
                req = urllib.request.Request(self.server_url, data=MemoryStream(), headers=headers, method='POST')
                
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
                        
                        break 
                except Exception as e:
                    print(f"⚠️ [上传失败] 传输中断 ({e})，2秒后重试...")
                    attempt += 1
                    time.sleep(2)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"🧹 [清理空间] 本地视频 {filename} 已阅即焚，成功销毁。")
                
            if 'video_data' in locals():
                del video_data

        except Exception as e:
            print(f"❌ [线程内部错误] {filepath}: {e}")
            if 'video_data' in locals():
                del video_data

    def record(self, record_count=0, segment_time=30):
        # 扫描特定扩展名并加入忽略黑名单
        existing_files = glob.glob(os.path.join(self.save_dir, self.ext))
        for old_file in existing_files:
            pure_name = os.path.basename(old_file)
            self.uploaded_files.add(pure_name)
            
        if existing_files:
            print(f"🛡️ 免疫 {len(existing_files)} 个历史遗留视频，直接略过。")

        print("⏳ 系统预热中，3秒后开始监控流...")
        time.sleep(3)

        process = None
        if self.mode == "ffmpeg":
            print("-" * 45)
            print(f"🎥 启动引擎：【FFmpeg 外挂录制】 (精准切片)")
            print("-" * 45)
            output_pattern = os.path.join(self.save_dir, "video_%Y-%m-%d_%H-%M-%S.mkv")
            cmd = [
                "ffmpeg", "-y", "-max_interleave_delta", "100k", "-fflags", "+genpts",
                "-thread_queue_size", "2048", "-rtsp_transport", "udp", "-buffer_size", "10485760",
                "-i", self.rtsp_url, "-thread_queue_size", "2048", "-f", "alsa", "-ac", "2",
                "-ar", "48000", "-itsoffset", "2.5", "-i", "hw:0,0", "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "pcm_s16le", "-ac", "1", "-async", "1", "-fflags", "+igndts",
                "-f", "segment", "-segment_time", str(segment_time), "-reset_timestamps", "1", "-strftime", "1"
            ]
            if record_count > 0:
                cmd.extend(["-t", str(record_count * segment_time)])
            cmd.append(output_pattern)
            
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print("-" * 45)
            print(f"🎥 启动引擎：【原生直录】 (DMA硬件直写，零CPU耗损)")
            print("-" * 45)

        try:
            while True:
                time.sleep(3)
                
                # 判断当前录像进程是否存活
                if self.mode == "ffmpeg":
                    is_running = process.poll() is None
                else:
                    # 原生直录由底层控制，Python端永远认为是 True，除非限制了次数
                    is_running = True 
                
                files = sorted(glob.glob(os.path.join(self.save_dir, self.ext)))
                
                if self.mode == "ffmpeg":
                    # 防线 1: 数量堆积过多 (断网导致)
                    if len(files) > 5:
                        try:
                            print(f"⚠️ [内存保护] 断网堆积过多，强行丢弃极老视频: {files[0]}")
                            os.remove(files[0])
                            if os.path.basename(files[0]) in self.uploaded_files:
                                self.uploaded_files.remove(os.path.basename(files[0]))
                            files = files[1:] # 更新文件列表
                        except: pass
                        
                    # 👇 防线 2 (新增): 检测“切片失效”导致的单个巨无霸文件！
                    # 如果正在写的唯一文件超过了 15MB (大约 3 分钟)，说明底层卡死了，立刻断臂求生！
                    if len(files) > 0 and os.path.getsize(files[-1]) > 15 * 1024 * 1024:
                        print(f"⚠️ [致命警报] 检测到视频切片失效，体积已达 {os.path.getsize(files[-1])/1024/1024:.2f}MB！")
                        print("⚡ 正在强行重启 FFmpeg 引擎以拯救 Linux 内存...")
                        if process:
                            process.terminate()
                        time.sleep(1)
                        try:
                            os.remove(files[-1]) # 毫不犹豫地干掉巨无霸
                        except: pass
                

                # 如果正在录像，永远排除最新生成的那 1 个文件，防止文件读写冲突
                if is_running:
                    completed_files = files[:-1] if len(files) > 1 else []
                else:
                    completed_files = files
                    
                for f in completed_files:
                    pure_name = os.path.basename(f) 
                    
                    if pure_name not in self.uploaded_files:
                        if os.path.getsize(f) > 0:
                            self.uploaded_files.add(pure_name)
                            self.executor.submit(self._upload_task, f)
                            
                            # 原生直录模式下，如果达到了指定的录制次数，则关闭扫描循环
                            if self.mode == "native" and record_count > 0:
                                if len(self.uploaded_files) >= record_count + len(existing_files):
                                    is_running = False
                                    
                if not is_running:
                    print("\n🏁 底层录像已完毕，等待队列中剩余的上传任务...")
                    self.executor.shutdown(wait=True)
                    print("🎉 所有排队任务均已完美收官，程序安全退出。")
                    break

        except KeyboardInterrupt:
            print("\n🛑 接收到手动停止信号。正在安全关闭...")
            if process:
                process.terminate()
                process.wait()
            self.executor.shutdown(wait=True)
            print("👋 系统监控已彻底终止。")