"""
模型客户端工厂 — 支持多模型自动回退

当某个模型返回 429 (Rate Limit) 时自动切换到下一个备选模型，
所有模型均限流时等待一段时间后重试。
"""
import asyncio
import time
from typing import Any, AsyncGenerator, Literal, Mapping, Optional, Sequence, Union

from pydantic import BaseModel

from autogen_core import CancellationToken
from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    LLMMessage,
    ModelInfo,
    RequestUsage,
)
from autogen_core.tools import Tool, ToolSchema
from autogen_ext.models.openai import OpenAIChatCompletionClient

from config import settings


# ============================================================
# 多模型回退包装器
# ============================================================


class FallbackChatCompletionClient(ChatCompletionClient):
    """包装多个 OpenAI 兼容客户端，遇到 429 限流时自动切换。

    特性：
      - 按 MODEL_FALLBACK_CHAIN 中的顺序逐个尝试
      - 被限流的模型进入冷却期（默认 60 秒内不再尝试）
      - 所有模型均限流时，等待后从头重试
      - 对外暴露的接口与 ChatCompletionClient 完全一致
    """

    # ComponentBase 要求的类型配置
    component_type = "model"
    component_config_schema = BaseModel
    component_provider_override = None

    def __init__(
        self,
        clients: list[OpenAIChatCompletionClient],
        model_names: list[str],
        cooldown_seconds: float = 60,
        retry_wait_seconds: float = 10,
    ) -> None:
        if not clients:
            raise ValueError("至少需要一个模型客户端")

        self._clients = clients
        self._model_names = model_names
        self._cooldown_seconds = cooldown_seconds
        self._retry_wait_seconds = retry_wait_seconds

        # 当前优先使用的模型索引
        self._current_index: int = 0
        # 被限流的模型 → 冷却截止时间戳
        self._cooldowns: dict[int, float] = {}

    # ------------------------------------------------------------------
    # 核心方法：create（带回退逻辑）
    # ------------------------------------------------------------------

    async def create(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = [],
        tool_choice: Tool | Literal["auto", "required", "none"] = "auto",
        json_output: Optional[bool | type[BaseModel]] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> CreateResult:
        """调用 LLM 生成回复，429 时自动切换模型。"""
        last_error: Optional[Exception] = None
        now = time.time()

        # 第一轮：按顺序尝试所有未冷却的模型
        for i in range(len(self._clients)):
            idx = (self._current_index + i) % len(self._clients)

            # 跳过仍在冷却期的模型
            if idx in self._cooldowns and self._cooldowns[idx] > now:
                continue

            try:
                result = await self._clients[idx].create(
                    messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    json_output=json_output,
                    extra_create_args=extra_create_args,
                    cancellation_token=cancellation_token,
                )
                # 成功 → 记住这个模型
                self._current_index = idx
                return result

            except Exception as e:
                if self._is_rate_limit_error(e):
                    name = self._model_names[idx]
                    print(f"[模型切换] {name} 请求受限 (429)，冷却 {self._cooldown_seconds}s")
                    self._cooldowns[idx] = now + self._cooldown_seconds
                    last_error = e
                    continue
                # 非限流错误直接抛出
                raise

        # 第二轮：所有模型均限流 → 等待后清除冷却、重试第一个
        if last_error is not None:
            print(
                f"[模型切换] 所有 {len(self._clients)} 个模型均受限，"
                f"等待 {self._retry_wait_seconds}s 后重试..."
            )
            await asyncio.sleep(self._retry_wait_seconds)
            self._cooldowns.clear()
            self._current_index = 0
            return await self._clients[0].create(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                json_output=json_output,
                extra_create_args=extra_create_args,
                cancellation_token=cancellation_token,
            )

        raise RuntimeError("没有可用的模型客户端")

    # ------------------------------------------------------------------
    # create_stream（带回退逻辑）
    # ------------------------------------------------------------------

    def create_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = [],
        tool_choice: Tool | Literal["auto", "required", "none"] = "auto",
        json_output: Optional[bool | type[BaseModel]] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncGenerator[Union[str, CreateResult], None]:
        """流式调用当前活跃模型。"""
        return self._clients[self._current_index].create_stream(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            json_output=json_output,
            extra_create_args=extra_create_args,
            cancellation_token=cancellation_token,
        )

    # ------------------------------------------------------------------
    # 委托方法：转发到当前活跃客户端
    # ------------------------------------------------------------------

    def count_tokens(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = [],
    ) -> int:
        return self._clients[self._current_index].count_tokens(messages, tools=tools)

    def remaining_tokens(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = [],
    ) -> int:
        return self._clients[self._current_index].remaining_tokens(messages, tools=tools)

    def remaining_budget(self) -> float:
        return self._clients[self._current_index].remaining_budget()

    @property
    def capabilities(self) -> Any:
        return self._clients[self._current_index].capabilities

    @property
    def model_info(self) -> ModelInfo:
        return self._clients[self._current_index].model_info

    def actual_usage(self) -> RequestUsage:
        # 汇总所有客户端的用量
        total = RequestUsage(prompt_tokens=0, completion_tokens=0)
        for client in self._clients:
            usage = client.actual_usage()
            total = RequestUsage(
                prompt_tokens=total.prompt_tokens + usage.prompt_tokens,
                completion_tokens=total.completion_tokens + usage.completion_tokens,
            )
        return total

    def total_usage(self) -> RequestUsage:
        total = RequestUsage(prompt_tokens=0, completion_tokens=0)
        for client in self._clients:
            usage = client.total_usage()
            total = RequestUsage(
                prompt_tokens=total.prompt_tokens + usage.prompt_tokens,
                completion_tokens=total.completion_tokens + usage.completion_tokens,
            )
        return total

    async def close(self) -> None:
        """关闭所有底层客户端。"""
        for client in self._clients:
            await client.close()

    # ------------------------------------------------------------------
    # ComponentBase 必要方法（包装器不需要序列化，提供桩实现）
    # ------------------------------------------------------------------

    def _to_config(self) -> BaseModel:
        return BaseModel()

    @classmethod
    def _from_config(cls, config: BaseModel) -> "FallbackChatCompletionClient":
        raise NotImplementedError("FallbackChatCompletionClient 不支持从配置反序列化")

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _is_rate_limit_error(error: Exception) -> bool:
        """判断异常是否为 429 限流错误。"""
        # openai.RateLimitError
        error_type = type(error).__name__
        if "RateLimitError" in error_type:
            return True
        # 兜底：检查错误信息
        error_str = str(error).lower()
        return "429" in error_str or "rate limit" in error_str

    def get_status(self) -> str:
        """返回当前模型切换状态（调试用）。"""
        now = time.time()
        lines = ["模型状态:"]
        for i, name in enumerate(self._model_names):
            status = "✓ 活跃" if i == self._current_index else "  待命"
            if i in self._cooldowns and self._cooldowns[i] > now:
                remaining = int(self._cooldowns[i] - now)
                status = f"✗ 冷却中 ({remaining}s)"
            lines.append(f"  [{i}] {name} — {status}")
        return "\n".join(lines)


# ============================================================
# 工厂函数
# ============================================================


def create_model_client() -> FallbackChatCompletionClient:
    """根据 MODEL_FALLBACK_CHAIN 配置创建带自动回退的模型客户端。

    Returns:
        FallbackChatCompletionClient 实例（兼容 ChatCompletionClient 接口）
    """
    clients: list[OpenAIChatCompletionClient] = []
    model_names: list[str] = []

    for cfg in settings.MODEL_FALLBACK_CHAIN:
        client = OpenAIChatCompletionClient(
            model=cfg["model"],
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            temperature=settings.MODEL_TEMPERATURE,
            model_info={
                "vision": cfg.get("vision", False),
                "function_calling": cfg.get("function_calling", True),
                "json_output": cfg.get("json_output", True),
                "structured_output": cfg.get("structured_output", False),
                "family": cfg.get("family", "unknown"),
            },
        )
        clients.append(client)
        model_names.append(cfg["model"])

    print(f"[模型] 已加载 {len(clients)} 个备选模型:")
    for i, name in enumerate(model_names):
        marker = "→" if i == 0 else " "
        print(f"  {marker} [{i}] {name}")

    return FallbackChatCompletionClient(
        clients=clients,
        model_names=model_names,
        cooldown_seconds=settings.MODEL_COOLDOWN_SECONDS,
        retry_wait_seconds=settings.MODEL_RETRY_WAIT_SECONDS,
    )
