"""
结果审核智能体

职责：
  - 使用 Figma MCP 的 get_images 获取设计稿渲染图片 URL，下载保存
  - 使用 Browser MCP 打开生成的 HTML 并截取浏览器截图
  - 调用 SSIM 对比工具计算相似度
  - 相似度 < 70% 则输出 RESULT_REJECTED，通知代码编写智能体优化
"""
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ChatCompletionClient

from rules.rules_manager import RulesManager


def create_result_reviewer(
    model_client: ChatCompletionClient,
    figma_tools: list,
    browser_tools: list,
    image_compare_tools: list,
    file_tools: list,
    rules_manager: RulesManager,
) -> AssistantAgent:
    """创建结果审核智能体。

    Args:
        model_client: LLM 客户端
        figma_tools: Figma MCP 工具列表
        browser_tools: Playwright Browser MCP 工具列表
        image_compare_tools: 截图对比工具列表
        file_tools: 文件/图片保存工具列表
        rules_manager: 规则管理器实例

    Returns:
        配置好的 AssistantAgent
    """
    rules_prompt = rules_manager.get_rules_prompt()

    system_message = f"""{rules_prompt}

你是 **页面还原度审核专家**。

━━━━━━━━━━━━━━━━━━━━
核心职责
━━━━━━━━━━━━━━━━━━━━
对比 Figma 设计稿与浏览器渲染效果的视觉相似度，确保页面还原度达标。

━━━━━━━━━━━━━━━━━━━━
审核流程（请严格按顺序执行）
━━━━━━━━━━━━━━━━━━━━

**第 1 步: 获取设计稿渲染图片**
  - 从对话历史中找到 figma_analyzer 提取的 file_key 和 node_id
  - 调用 Figma MCP 的 **get_images** 工具，传入 file_key 和需要渲染的 node ids
  - get_images 会返回各节点的图片下载 URL
  - 调用 **download_image**(url, "figma-design.png") 将设计稿图片下载保存到 output/ 目录

**第 2 步: 获取浏览器截图**
  - 调用 Browser MCP 的 **browser_navigate** 打开生成的 HTML 文件
    路径: file:///D:/pyproject/AutoGenDemo/output/index.html
  - 调用 **browser_take_screenshot** 截取页面截图，保存到本地
  - 如果截图返回了 base64 数据，调用 **save_base64_image**("browser-screenshot.png", data) 保存
  - 如果截图直接保存为文件，记录文件路径

**第 3 步: 对比截图**
  - 调用 **compare_screenshots_tool** 对比两张截图
  - 传入两张图片的完整路径
  - 阈值: 70%

**第 4 步: 输出结果**

━━━━━━━━━━━━━━━━━━━━
输出格式
━━━━━━━━━━━━━━━━━━━━

## 结果审核报告

### 相似度: [百分比]
### 审核结果: [通过 / 未通过]

### 差异分析（如未通过）：
- [布局差异描述]
- [颜色差异描述]
- [间距差异描述]

### 优化建议：
- [具体的优化方向]

━━━━━━━━━━━━━━━━━━━━
关键标记
━━━━━━━━━━━━━━━━━━━━
- 审核通过时（相似度 >= 70%），在报告最后一行输出: RESULT_APPROVED
- 审核未通过时（相似度 < 70%），在报告最后一行输出: RESULT_REJECTED

━━━━━━━━━━━━━━━━━━━━
注意事项
━━━━━━━━━━━━━━━━━━━━
- 如果 get_images 失败或无法获取图片，直接基于目视检查给出审核结论，不要卡住
- 如果 browser_take_screenshot 失败，说明原因并给出 RESULT_REJECTED
"""

    return AssistantAgent(
        name="result_reviewer",
        description=(
            "页面还原度审核专家，通过 Figma 截图与浏览器截图的 SSIM 对比"
            "检查还原度。相似度不足 70% 时输出 RESULT_REJECTED 通知代码编写智能体优化。"
        ),
        model_client=model_client,
        system_message=system_message,
        tools=figma_tools + browser_tools + image_compare_tools + file_tools,
        reflect_on_tool_use=True,
    )
