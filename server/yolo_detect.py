import cv2
from ultralytics import YOLO
import os

# 全局加载标准的 YOLOv8 nano 模型 (体积小，速度快，适合跑 Demo)
# 如果你本地没有 yolov8n.pt，运行时它会自动下载
# 这个基础模型原生支持识别 80 种日常物体（人、手机、杯子、汽车、猫狗等）
print("⏳ 正在加载标准 YOLOv8 AI 模型...")
model = YOLO('yolov8n.pt') 
print("✅ 模型加载完毕！")

def process_video(video_path: str):
    """
    后台处理视频文件：标准 YOLO 检测 -> 绘制识别框 -> 保存到指定目录
    """
    output_dir = "files/yolo_detected"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 打开视频流
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ 无法打开视频文件: {video_path}")
        return

    # 2. 提取视频基础信息
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # 兜底保护：如果因为某些原因没读到帧率，给个 20fps 默认值
    if fps == 0:
        fps = 20.0

    # 3. 准备输出文件
    base_name = os.path.basename(video_path)
    name, _ = os.path.splitext(base_name)
    out_path = os.path.join(output_dir, f"{name}_detected.mp4")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    print(f"🎬 [AI 开始解析] {base_name} ...")
    
    # 4. 逐帧读取并进行 AI 检测
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break # 视频读取结束
            
        # 跑标准 YOLO 检测 (verbose=False 防止控制台疯狂刷屏)
        results = model.predict(source=frame, verbose=False) 
        
        # 核心魔法：Ultralytics 自带的 plot() 会自动把方框和名字完美画在图上
        annotated_frame = results[0].plot()
        
        # 将带有 AI 标记的画面写入新视频
        out.write(annotated_frame)

    # 5. 释放资源
    cap.release()
    out.release()
    print(f"🎉 [AI 解析完成] 带标记的视频已生成: {out_path}")