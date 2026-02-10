"""
Figma MCP 工具初始化

使用 figma-developer-mcp（npm 包）通过 stdio 模式连接，
返回可直接注入 AssistantAgent 的工具列表。

需要配置 FIGMA_API_KEY 环境变量或在 config/settings.py 中设置。
"""
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools
from config import settings


async def get_figma_tools() -> list:
    """启动 figma-developer-mcp 并返回工具列表。

    Raises:
        ValueError: FIGMA_API_KEY 未配置时抛出
    """
    if not settings.FIGMA_API_KEY:
        raise ValueError(
            "FIGMA_API_KEY 未配置！\n"
            "请设置环境变量 FIGMA_API_KEY 或在 config/settings.py 中配置。\n"
            "获取方式: https://help.figma.com/hc/en-us/articles/8085703771159"
        )

    params = StdioServerParams(
        command=settings.FIGMA_MCP_COMMAND,
        args=settings.FIGMA_MCP_ARGS,
        env={"FIGMA_API_KEY": settings.FIGMA_API_KEY},
    )
    return await mcp_server_tools(params)
