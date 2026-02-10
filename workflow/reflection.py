"""
RoundRobinGroupChat 反思循环配置

提供两种反思子流程：
  1. 代码编写 ↔ 代码审核  （最多 N 轮）
  2. 代码编写 ↔ 结果审核  （最多 N 轮）

可作为独立的子团队运行，也可由编排器按需调用。
"""
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat

from config import settings


def create_code_review_loop(
    code_writer,
    code_reviewer,
    max_rounds: int | None = None,
) -> RoundRobinGroupChat:
    """创建代码编写 ↔ 代码审核的反思循环。

    流程：
      code_writer → code_reviewer → code_writer → code_reviewer → ...
    终止条件：
      - code_reviewer 输出 REVIEW_APPROVED
      - 达到最大轮次

    Args:
        code_writer: 代码编写智能体
        code_reviewer: 代码审核智能体
        max_rounds: 最大反思轮次（默认使用配置值）

    Returns:
        配置好的 RoundRobinGroupChat 实例
    """
    if max_rounds is None:
        max_rounds = settings.MAX_REFLECTION_ROUNDS

    termination = (
        TextMentionTermination("REVIEW_APPROVED")
        | MaxMessageTermination(max_rounds * 2)  # 每轮 2 条消息
    )

    return RoundRobinGroupChat(
        participants=[code_writer, code_reviewer],
        termination_condition=termination,
    )


def create_result_review_loop(
    code_writer,
    result_reviewer,
    max_rounds: int | None = None,
) -> RoundRobinGroupChat:
    """创建代码编写 ↔ 结果审核的反思循环。

    流程：
      code_writer → result_reviewer → code_writer → result_reviewer → ...
    终止条件：
      - result_reviewer 输出 RESULT_APPROVED
      - 达到最大轮次

    Args:
        code_writer: 代码编写智能体
        result_reviewer: 结果审核智能体
        max_rounds: 最大反思轮次（默认使用配置值）

    Returns:
        配置好的 RoundRobinGroupChat 实例
    """
    if max_rounds is None:
        max_rounds = settings.MAX_REFLECTION_ROUNDS

    termination = (
        TextMentionTermination("RESULT_APPROVED")
        | MaxMessageTermination(max_rounds * 2)
    )

    return RoundRobinGroupChat(
        participants=[code_writer, result_reviewer],
        termination_condition=termination,
    )
