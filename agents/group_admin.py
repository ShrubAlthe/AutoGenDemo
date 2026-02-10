"""
群组管理员智能体

职责：
  - 负责调度其他智能体的运行顺序
  - 作为 SelectorGroupChat 的选择器逻辑实现
  - 提供自定义选择器提示词和选择器函数

本模块不创建独立的 AssistantAgent 参与群聊，
而是通过 selector_prompt + selector_func 嵌入 SelectorGroupChat 的调度机制中。
"""
from typing import Optional, Sequence

# ============================================================
# 管理员选择器提示词
# ============================================================

ADMIN_SELECTOR_PROMPT = """你是一个工作流调度管理员，负责协调以下智能体的工作。

参与者及职责：
{roles}

请根据对话历史，按照以下调度规则选择下一个应该发言的智能体名称。

━━━━━━━━━━━━━━━━━━━━
调度规则（按优先级排序）
━━━━━━━━━━━━━━━━━━━━
1. 工作流刚开始（无历史消息或只有任务描述）→ 选择 **figma_analyzer**
2. figma_analyzer 分析中提到 "需要用户确认" / "不确定" → 选择 **info_gatherer**
3. info_gatherer 获取到用户回答后 → 选择 **figma_analyzer** 继续分析
4. figma_analyzer 已完成完整分析报告 → 选择 **code_writer**
5. code_writer 完成代码编写（调用了 write_file） → 选择 **code_reviewer**
6. code_reviewer 输出 "REVIEW_REJECTED" → 选择 **code_writer** 修复问题
7. code_reviewer 输出 "REVIEW_APPROVED" → 选择 **result_reviewer**
8. result_reviewer 输出 "RESULT_REJECTED" → 选择 **code_writer** 优化还原度
9. result_reviewer 输出 "RESULT_APPROVED" → 任务完成

━━━━━━━━━━━━━━━━━━━━
重要约束
━━━━━━━━━━━━━━━━━━━━
- 代码审核反思循环（code_writer ↔ code_reviewer）最多 3 次
- 结果审核反思循环（code_writer ↔ result_reviewer）最多 3 次
- 超过最大循环次数时，强制通过

只输出下一个应该发言的智能体名称，不要输出任何其他内容。
"""


def create_selector_prompt(participants_info: str) -> str:
    """用参与者信息填充选择器提示词模板。

    Args:
        participants_info: 格式化的参与者名称和描述

    Returns:
        完整的选择器提示词
    """
    return ADMIN_SELECTOR_PROMPT.format(roles=participants_info)


# ============================================================
# 自定义选择器函数（优先于 LLM 选择，返回 None 时回退到 LLM）
# ============================================================


def custom_selector_func(messages: Sequence) -> Optional[str]:
    """基于对话历史的确定性调度逻辑。

    对于明确的状态转换（如审核通过/未通过），直接返回下一个智能体名称。
    对于需要判断的场景，返回 None 让 LLM 选择。

    Args:
        messages: 当前对话的消息序列

    Returns:
        下一个智能体名称，或 None（回退到 LLM 选择）
    """
    if not messages:
        return "figma_analyzer"

    last_msg = messages[-1]
    last_source = getattr(last_msg, "source", "")
    last_content = str(getattr(last_msg, "content", ""))

    # ------------------------------------------------------------------
    # 确定性转换
    # ------------------------------------------------------------------

    # 代码审核通过 → 结果审核
    if last_source == "code_reviewer" and "REVIEW_APPROVED" in last_content:
        return "result_reviewer"

    # 代码审核未通过 → 回到代码编写
    if last_source == "code_reviewer" and "REVIEW_REJECTED" in last_content:
        return "code_writer"

    # 结果审核通过 → 任务即将完成（由终止条件处理）
    # result_reviewer 输出 RESULT_APPROVED 后，终止条件 TextMentionTermination 会捕获

    # 结果审核未通过 → 回到代码编写
    if last_source == "result_reviewer" and "RESULT_REJECTED" in last_content:
        return "code_writer"

    # 代码编写完成 → 代码审核
    if last_source == "code_writer":
        return "code_reviewer"

    # ------------------------------------------------------------------
    # 其他场景交给 LLM 判断
    # ------------------------------------------------------------------
    return None
