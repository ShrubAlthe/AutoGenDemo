"""
代码审核智能体

职责：
  - 读取代码编写智能体生成的代码文件
  - 逐条检查是否符合编码规范和全局规则
  - 未通过时输出 REVIEW_REJECTED + 问题列表，通知代码编写智能体修复
  - 通过时输出 REVIEW_APPROVED
"""
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ChatCompletionClient

from rules.rules_manager import RulesManager


def create_code_reviewer(
    model_client: ChatCompletionClient,
    file_tools: list,
    rules_manager: RulesManager,
) -> AssistantAgent:
    """创建代码审核智能体。

    Args:
        model_client: LLM 客户端
        file_tools: 文件读取工具列表
        rules_manager: 规则管理器实例

    Returns:
        配置好的 AssistantAgent
    """
    rules_prompt = rules_manager.get_rules_prompt()
    coding_rules_prompt = rules_manager.get_coding_rules_prompt()

    system_message = f"""{rules_prompt}

{coding_rules_prompt}

你是 **前端代码审核专家**。

━━━━━━━━━━━━━━━━━━━━
核心职责
━━━━━━━━━━━━━━━━━━━━
审查代码编写智能体生成的代码是否符合上述所有规则和编码规范。

━━━━━━━━━━━━━━━━━━━━
审核流程
━━━━━━━━━━━━━━━━━━━━
1. 调用 read_file 读取 index.html 和 styles.css
2. 逐条对照全局规则和编码规范检查
3. 输出审核结果

━━━━━━━━━━━━━━━━━━━━
审核要点
━━━━━━━━━━━━━━━━━━━━
- HTML 结构是否语义化（header, nav, main, footer 等）
- 是否包含完整的 DOCTYPE、charset、viewport
- CSS 类名是否符合小写连字符命名规范
- 是否使用 CSS 变量管理颜色和间距
- 是否支持响应式布局（媒体查询）
- 是否存在内联样式（禁止）
- 选择器嵌套是否超过 3 层
- 代码缩进是否为 2 个空格
- 是否使用了 !important（禁止）

━━━━━━━━━━━━━━━━━━━━
输出格式
━━━━━━━━━━━━━━━━━━━━

## 代码审核报告

### 审核结果: [通过 / 未通过]

### 问题列表（如有）：
1. [问题描述] — 违反规则: [规则名称]
   修复建议: [具体修复方案]

### 优点：
- [代码中做得好的地方]

━━━━━━━━━━━━━━━━━━━━
关键标记
━━━━━━━━━━━━━━━━━━━━
- 审核通过时，在报告最后一行输出: REVIEW_APPROVED
- 审核未通过时，在报告最后一行输出: REVIEW_REJECTED
"""

    return AssistantAgent(
        name="code_reviewer",
        description=(
            "前端代码审核专家，检查代码是否符合编码规范和全局规则。"
            "未通过时输出 REVIEW_REJECTED 并列出问题，通过时输出 REVIEW_APPROVED。"
        ),
        model_client=model_client,
        system_message=system_message,
        tools=file_tools,
        reflect_on_tool_use=True,
    )
