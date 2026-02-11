"""
MCP 服务统一生命周期管理器

解决的问题：
  原先每次调用 mcp_server_tools() 都会启动新的 MCP 子进程，
  导致启动开销大、资源浪费且无法保持状态。

方案：
  使用 create_mcp_server_session 创建持久化 ClientSession，
  通过 mcp_server_tools(session=...) 复用连接获取工具列表。
  整个工作流期间只启动一次 MCP 进程。

用法:
  async with McpManager() as mgr:
      figma_tools = await mgr.get_figma_tools()
      browser_tools = await mgr.get_browser_tools()
      # ... 使用工具 ...
  # 退出时自动清理
"""
import contextlib
from typing import Optional

from autogen_ext.tools.mcp import (
    StdioServerParams,
    create_mcp_server_session,
    mcp_server_tools,
)

from config import settings


class McpManager:
    """统一管理 Figma MCP 和 Browser MCP 的连接生命周期。

    特性：
      - 延迟初始化：第一次调用 get_xxx_tools() 时才启动对应的 MCP 进程
      - 连接复用：整个生命周期内共享同一个 session
      - 安全关闭：通过 async with 或手动 close() 确保资源释放
    """

    def __init__(self) -> None:
        self._figma_session = None
        self._figma_session_cm = None
        self._figma_tools: Optional[list] = None

        self._browser_session = None
        self._browser_session_cm = None
        self._browser_tools: Optional[list] = None

    # ------------------------------------------------------------------
    # Figma MCP
    # ------------------------------------------------------------------

    async def get_figma_tools(self) -> list:
        """获取 Figma MCP 工具列表，首次调用时启动 MCP 进程。"""
        if self._figma_tools is not None:
            return self._figma_tools

        if not settings.FIGMA_API_KEY:
            raise ValueError(
                "FIGMA_API_KEY 未配置！\n"
                "请设置环境变量 FIGMA_API_KEY 或在 .env 中配置。\n"
                "获取方式: https://help.figma.com/hc/en-us/articles/8085703771159"
            )

        params = StdioServerParams(
            command=settings.FIGMA_MCP_COMMAND,
            args=settings.FIGMA_MCP_ARGS,
            env={"FIGMA_API_KEY": settings.FIGMA_API_KEY},
        )

        # 创建持久 session
        self._figma_session_cm = contextlib.asynccontextmanager(
            create_mcp_server_session
        )(params)
        self._figma_session = await self._figma_session_cm.__aenter__()

        # 用 session 复用连接获取工具
        self._figma_tools = await mcp_server_tools(params, session=self._figma_session)
        return self._figma_tools

    # ------------------------------------------------------------------
    # Browser MCP
    # ------------------------------------------------------------------

    async def get_browser_tools(self) -> list:
        """获取 Browser MCP 工具列表，首次调用时启动 MCP 进程。"""
        if self._browser_tools is not None:
            return self._browser_tools

        params = StdioServerParams(
            command=settings.BROWSER_MCP_COMMAND,
            args=settings.BROWSER_MCP_ARGS,
        )

        self._browser_session_cm = contextlib.asynccontextmanager(
            create_mcp_server_session
        )(params)
        self._browser_session = await self._browser_session_cm.__aenter__()

        self._browser_tools = await mcp_server_tools(params, session=self._browser_session)
        return self._browser_tools

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """关闭所有 MCP 连接，释放子进程资源。"""
        errors = []

        if self._figma_session_cm is not None:
            try:
                await self._figma_session_cm.__aexit__(None, None, None)
            except Exception as e:
                errors.append(f"Figma MCP 关闭失败: {e}")
            finally:
                self._figma_session = None
                self._figma_session_cm = None
                self._figma_tools = None

        if self._browser_session_cm is not None:
            try:
                await self._browser_session_cm.__aexit__(None, None, None)
            except Exception as e:
                errors.append(f"Browser MCP 关闭失败: {e}")
            finally:
                self._browser_session = None
                self._browser_session_cm = None
                self._browser_tools = None

        if errors:
            print(f"[MCP] 关闭时出现错误: {'; '.join(errors)}")

    async def __aenter__(self) -> "McpManager":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
