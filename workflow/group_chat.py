"""
SelectorGroupChat 配置

使用模型驱动的发言者选择 + 自定义选择器函数，
实现群组管理员的调度逻辑。
"""
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_core.models import ChatCompletionClient

from agents.group_admin import create_selector_prompt, custom_selector_func


def create_group_chat(
    participants: list,
    model_client: ChatCompletionClient,
    max_messages: int = 50,
) -> SelectorGroupChat:
    """创建群聊团队。

    调度逻辑：
      - custom_selector_func 处理确定性状态转换（审核通过/未通过等）
      - 不确定时回退到 LLM（使用 selector_prompt 引导选择）

    终止条件：
      - 消息中出现 "TASK_COMPLETE" 或 "RESULT_APPROVED"
      - 消息总数超过 max_messages

    Args:
        participants: 参与群聊的智能体列表
        model_client: 用于选择器的 LLM 客户端
        max_messages: 最大消息数

    Returns:
        配置好的 SelectorGroupChat 实例
    """
    # 构建参与者信息（供选择器提示词使用）
    roles_info = "\n".join(
        [f"- **{p.name}**: {p.description}" for p in participants]
    )
    selector_prompt = create_selector_prompt(roles_info)

    # 组合终止条件
    termination = (
        TextMentionTermination("TASK_COMPLETE")
        | TextMentionTermination("RESULT_APPROVED")
        | MaxMessageTermination(max_messages)
    )

    return SelectorGroupChat(
        participants=participants,
        model_client=model_client,
        selector_prompt=selector_prompt,
        selector_func=custom_selector_func,
        termination_condition=termination,
        allow_repeated_speaker=True,   # 允许同一智能体连续发言（如工具调用后继续）
    )
