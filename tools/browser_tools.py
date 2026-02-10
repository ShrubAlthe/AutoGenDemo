"""
Playwright Browser MCP 工具初始化

通过 autogen_ext 的 MCP 适配器连接 Playwright MCP Server，
返回可直接注入 AssistantAgent 的工具列表。
"""
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools
from config import settings


async def get_browser_tools() -> list:
    """启动 Playwright MCP Server 并返回工具列表。

    工具包括：
    - browser_navigate       : 导航到指定 URL
    - browser_take_screenshot: 截取当前页面截图
    - browser_snapshot       : 获取页面无障碍快照
    - browser_click          : 点击页面元素
    - ...等其他浏览器操作工具
    """
    params = StdioServerParams(
        command=settings.BROWSER_MCP_COMMAND,
        args=settings.BROWSER_MCP_ARGS,
    )
    return await mcp_server_tools(params)
