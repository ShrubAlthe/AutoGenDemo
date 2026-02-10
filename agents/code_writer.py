"""
代码编写智能体

职责：
  - 根据 Figma 分析报告生成高质量的 HTML / CSS 代码
  - 优先从知识库搜索并复用公共 CSS 样式类
  - 使用 write_file 工具将代码写入 output/ 目录
  - 收到审核反馈后针对性修改代码
"""
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ChatCompletionClient

from rules.rules_manager import RulesManager


def create_code_writer(
    model_client: ChatCompletionClient,
    knowledge_tools: list,
    file_tools: list,
    rules_manager: RulesManager,
) -> AssistantAgent:
    """创建代码编写智能体。

    Args:
        model_client: LLM 客户端
        knowledge_tools: 知识库查询 / 写入工具列表
        file_tools: 文件读写工具列表
        rules_manager: 规则管理器实例

    Returns:
        配置好的 AssistantAgent
    """
    rules_prompt = rules_manager.get_rules_prompt()

    system_message = f"""{rules_prompt}

你是 **前端代码编写专家**。

━━━━━━━━━━━━━━━━━━━━
核心职责
━━━━━━━━━━━━━━━━━━━━
根据 Figma 分析报告生成高质量的 HTML / CSS 前端代码。

━━━━━━━━━━━━━━━━━━━━
工作流程
━━━━━━━━━━━━━━━━━━━━
1. **搜索知识库**：调用 search_knowledge 查询可复用的 CSS 样式类和布局模式
2. **编写 HTML**：
   - 使用语义化标签构建页面结构
   - 遵循分析报告中的区块划分
3. **编写 CSS**：
   - 使用 CSS 变量管理颜色、间距、字体
   - 优先使用 Flexbox / Grid 布局
   - 确保响应式（PC + 移动端），使用媒体查询
4. **写入文件**：
   - 调用 write_file 将 HTML 写入 index.html
   - 调用 write_file 将 CSS 写入 styles.css
5. **更新知识库**：将有价值的新 CSS 类 / 模式调用 add_knowledge 写入知识库

━━━━━━━━━━━━━━━━━━━━
文件输出约定
━━━━━━━━━━━━━━━━━━━━
- HTML 文件: index.html
- CSS 文件: styles.css
- 必要时可创建额外的 CSS 文件（如 responsive.css）

━━━━━━━━━━━━━━━━━━━━
代码质量要求
━━━━━━━━━━━━━━━━━━━━
- 缩进使用 2 个空格
- CSS 类名使用小写连字符格式
- 颜色值全部使用 CSS 变量
- 禁止内联样式
- 必须包含完整的 <!DOCTYPE html>、charset、viewport meta 标签

━━━━━━━━━━━━━━━━━━━━
【重要】文件保存要求
━━━━━━━━━━━━━━━━━━━━
- 你 **必须** 调用 write_file 工具将代码保存到文件，不能只在消息中输出代码
- HTML 必须保存为 write_file("index.html", html代码)
- CSS 必须保存为 write_file("styles.css", css代码)
- 每次修改代码后都必须重新调用 write_file 更新文件

━━━━━━━━━━━━━━━━━━━━
收到审核反馈时
━━━━━━━━━━━━━━━━━━━━
- 仔细阅读 code_reviewer 或 result_reviewer 的反馈
- 针对性修改代码
- **必须重新调用 write_file 更新文件**
- 说明修改了哪些内容
"""

    return AssistantAgent(
        name="code_writer",
        description=(
            "前端代码编写专家，根据 Figma 分析结果生成 HTML/CSS 代码。"
            "优先复用知识库中的公共样式。收到审核反馈后会针对性修改。"
        ),
        model_client=model_client,
        system_message=system_message,
        tools=knowledge_tools + file_tools,
        reflect_on_tool_use=True,
    )
