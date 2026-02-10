"""
信息获取智能体

职责：
  - 当分析或编码过程中遇到不确定的信息时，向用户提问获取答案
  - 禁止盲目执行，必须获得明确答案后才继续

基于 UserProxyAgent 实现，接收人类输入并传递回团队。
"""
from typing import Callable, Optional

from autogen_agentchat.agents import UserProxyAgent


def create_info_gatherer(
    input_func: Optional[Callable[[str], str]] = None,
) -> UserProxyAgent:
    """创建信息获取智能体。

    Args:
        input_func: 自定义输入函数，默认为 None（使用标准 input()）。
                    签名: (prompt: str) -> str

    Returns:
        配置好的 UserProxyAgent
    """
    return UserProxyAgent(
        name="info_gatherer",
        description=(
            "信息获取智能体，负责向用户询问不确定的信息。"
            "当 figma_analyzer 或 code_writer 遇到需要用户确认的问题时，"
            "选择此智能体向用户提问。禁止盲目执行，必须获得明确答案后才继续。"
        ),
        input_func=input_func,
    )
