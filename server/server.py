import uvicorn
from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from uuid import uuid4
import os
import shutil
import yolo_detect

app = FastAPI()  
  
# 确保基础存储文件夹存在
os.makedirs("files", exist_ok=True)

def background_ai_task(file_path: str):
    """分配给后台线程的 AI 解析任务"""
    try:
        yolo_detect.process_video(file_path)
    except Exception as e:
        print(f"❌ [后台任务] 视频处理崩溃: {e}")

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    # 接收并保存文件
    file_name = file.filename
    file_path = os.path.join("files", file_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print(f"📥 收到设备端视频: {file_name}，已推送给 AI 分析引擎。")

    # 核心：立刻把繁重的 AI 推理任务踢给后台线程去跑
    background_tasks.add_task(background_ai_task, file_path)

    # 瞬间给板子返回成功！让板子赶紧去删掉本地缓存的 mkv 视频
    return {"taskid": str(uuid4()), "status": "success", "msg": "Video received"}

if __name__ == "__main__":
    # 启动服务器
    uvicorn.run(host="0.0.0.0", port=8920, app=app)