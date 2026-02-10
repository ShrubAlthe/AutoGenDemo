"""
FastAPI Web 应用 — 提供聊天界面和 WebSocket 实时通信

路由：
  GET  /            → 聊天界面主页
  WS   /ws          → WebSocket（实时消息推送 + 用户输入）
  GET  /api/history → 获取完整消息历史
  GET  /api/files   → 获取 output/ 目录文件列表
"""
import asyncio
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from web.bridge import WorkflowBridge

# ============================================================
# 全局状态
# ============================================================

app = FastAPI(title="Figma2Code 多智能体工作流")
bridge = WorkflowBridge()

# 确保目录存在
_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

# 静态文件
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# output 目录（供预览生成的页面）
app.mount("/output", StaticFiles(directory=settings.OUTPUT_DIR), name="output")


# ============================================================
# HTTP 路由
# ============================================================


@app.get("/", response_class=HTMLResponse)
async def index():
    """返回聊天界面主页。"""
    html_path = os.path.join(_static_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/history")
async def get_history():
    """返回完整消息历史。"""
    return JSONResponse(content={"messages": bridge.get_history()})


@app.get("/api/files")
async def get_files():
    """返回 output/ 目录的文件列表。"""
    files = []
    if os.path.exists(settings.OUTPUT_DIR):
        for root, _dirs, filenames in os.walk(settings.OUTPUT_DIR):
            for fname in filenames:
                rel = os.path.relpath(os.path.join(root, fname), settings.OUTPUT_DIR)
                files.append(rel.replace("\\", "/"))
    return JSONResponse(content={"files": files})


@app.get("/api/status")
async def get_status():
    """返回工作流当前状态。"""
    return JSONResponse(content={
        "running": bridge.running,
        "waiting_for_input": bridge.waiting_for_input,
        "message_count": len(bridge.messages),
    })


# ============================================================
# WebSocket 路由
# ============================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点：实时推送消息 + 接收用户输入。"""
    await websocket.accept()

    # 注册订阅
    sub_queue = bridge.subscribe()

    # 发送历史消息
    for msg in bridge.messages:
        await websocket.send_json(msg.to_dict())

    # 发送当前状态
    await websocket.send_json({
        "source": "system",
        "content": "",
        "msg_type": "status",
        "running": bridge.running,
        "waiting_for_input": bridge.waiting_for_input,
    })

    async def send_task():
        """持续从订阅队列读取新消息并推送到 WebSocket。"""
        try:
            while True:
                msg = await sub_queue.get()
                if isinstance(msg, dict):
                    await websocket.send_json(msg)
                else:
                    await websocket.send_json(msg.to_dict())
        except Exception:
            pass

    async def receive_task():
        """持续接收 WebSocket 消息（用户输入 / 启动 / 停止命令）。"""
        try:
            while True:
                data = await websocket.receive_text()
                parsed = json.loads(data)
                msg_type = parsed.get("type", "")

                if msg_type == "input":
                    await bridge.provide_input(parsed.get("text", ""))

                elif msg_type == "start":
                    if not bridge.running:
                        await bridge.emit(
                            "system",
                            "收到启动请求，正在初始化工作流...",
                            msg_type="system",
                        )
                        await bridge.provide_input(json.dumps(parsed))

                elif msg_type == "stop":
                    if bridge.running:
                        bridge.request_cancel()
                        await bridge.emit(
                            "system",
                            "正在停止工作流...",
                            msg_type="system",
                        )

        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    # 并行运行发送和接收
    send = asyncio.create_task(send_task())
    receive = asyncio.create_task(receive_task())

    try:
        done, pending = await asyncio.wait(
            [send, receive], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    finally:
        send.cancel()
        receive.cancel()
        bridge.unsubscribe(sub_queue)
