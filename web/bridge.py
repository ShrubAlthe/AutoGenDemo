"""
WorkflowBridge — 编排器与 Web UI 之间的异步消息桥接

职责：
  - 编排器通过 emit() 发送智能体消息 → Web UI 通过 WebSocket 读取
  - Web UI 通过 provide_input() 发送用户输入 → 编排器通过 request_input() 读取
  - 支持取消正在运行的工作流
  - 维护完整的消息历史，供新连接的 WebSocket 客户端回放
"""
import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    """单条聊天消息"""

    source: str                                    # 发送者（智能体名称 / system / user）
    content: str                                   # 消息内容
    timestamp: float = field(default_factory=time.time)
    msg_type: str = "agent"                        # agent / system / user / tool / error

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
            "msg_type": self.msg_type,
        }


class WorkflowBridge:
    """连接编排器和 Web UI 的异步消息总线。"""

    def __init__(self) -> None:
        # 编排器 → Web UI（多个 WebSocket 客户端可同时监听）
        self.message_queue: asyncio.Queue[ChatMessage] = asyncio.Queue()
        # Web UI → 编排器（用户输入）
        self.input_queue: asyncio.Queue[str] = asyncio.Queue()
        # 完整消息历史
        self.messages: list[ChatMessage] = []
        # 当前是否在等待用户输入
        self.waiting_for_input: bool = False
        # 工作流是否正在运行
        self.running: bool = False
        # 取消事件
        self.cancel_event: asyncio.Event = asyncio.Event()
        # 当前工作流任务引用（用于 cancel）
        self._workflow_task: asyncio.Task | None = None
        # 已连接的 WebSocket 客户端
        self._subscribers: list[asyncio.Queue] = []

    # ------------------------------------------------------------------
    # 编排器 → Web UI
    # ------------------------------------------------------------------

    async def emit(self, source: str, content: str, msg_type: str = "agent") -> None:
        """编排器发送消息到 Web UI。"""
        msg = ChatMessage(source=source, content=content, msg_type=msg_type)
        self.messages.append(msg)
        # 推送到所有已订阅的 WebSocket
        for sub_queue in self._subscribers:
            await sub_queue.put(msg)

    def emit_chunk(self, token: str) -> None:
        """同步推送 token chunk 到所有订阅者（用于 model_client 的 on_token 回调）。

        不记录到 messages 历史（完整消息会由 agent 消息覆盖）。
        """
        chunk_msg = {
            "source": "assistant",
            "content": token,
            "timestamp": time.time(),
            "msg_type": "chunk",
        }
        for sub_queue in self._subscribers:
            try:
                sub_queue.put_nowait(chunk_msg)
            except Exception:
                pass  # 队列满时丢弃 chunk，不影响主流程

    # ------------------------------------------------------------------
    # Web UI → 编排器
    # ------------------------------------------------------------------

    async def request_input(self, prompt: str) -> str:
        """编排器请求用户输入（阻塞直到用户回复）。"""
        self.waiting_for_input = True
        await self.emit("system", prompt, msg_type="input_request")
        # 通知所有订阅者状态变化
        await self._emit_status()
        user_text = await self.input_queue.get()
        self.waiting_for_input = False
        # 记录用户输入为消息
        await self.emit("user", user_text, msg_type="user")
        return user_text

    async def provide_input(self, text: str) -> None:
        """Web UI 提供用户输入。"""
        await self.input_queue.put(text)

    # ------------------------------------------------------------------
    # 取消工作流
    # ------------------------------------------------------------------

    def request_cancel(self) -> None:
        """请求取消当前工作流。"""
        self.cancel_event.set()
        if self._workflow_task and not self._workflow_task.done():
            self._workflow_task.cancel()

    @property
    def is_cancelled(self) -> bool:
        """检查是否已请求取消。"""
        return self.cancel_event.is_set()

    def reset_cancel(self) -> None:
        """重置取消状态（新工作流开始前调用）。"""
        self.cancel_event.clear()

    # ------------------------------------------------------------------
    # WebSocket 订阅管理
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        """注册一个新的消息订阅者，返回其专属消息队列。"""
        q: asyncio.Queue[ChatMessage] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """注销订阅者。"""
        if q in self._subscribers:
            self._subscribers.remove(q)

    # ------------------------------------------------------------------
    # 状态推送
    # ------------------------------------------------------------------

    async def _emit_status(self) -> None:
        """向所有订阅者推送当前状态。"""
        status_msg = {
            "source": "system",
            "content": "",
            "timestamp": time.time(),
            "msg_type": "status",
            "running": self.running,
            "waiting_for_input": self.waiting_for_input,
        }
        for sub_queue in self._subscribers:
            await sub_queue.put(status_msg)

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def get_history(self) -> list[dict]:
        """返回完整消息历史（字典列表，可 JSON 序列化）。"""
        return [m.to_dict() for m in self.messages]

    def clear(self) -> None:
        """清空消息历史（新一轮工作流时调用）。"""
        self.messages.clear()

    def reset(self) -> None:
        """完全重置状态。"""
        self.messages.clear()
        self.running = False
        self.waiting_for_input = False
        self.cancel_event.clear()
        self._workflow_task = None
        # 清空队列
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
