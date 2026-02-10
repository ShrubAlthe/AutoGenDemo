"""
工作流控制数据类 — 任务状态、用户反馈等，与智能体解耦
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class WorkflowPhase(Enum):
    """工作流阶段枚举"""

    INIT = "init"
    FIGMA_ANALYSIS = "figma_analysis"
    INFO_GATHERING = "info_gathering"
    CODE_WRITING = "code_writing"
    CODE_REVIEW = "code_review"
    RESULT_REVIEW = "result_review"
    USER_FEEDBACK = "user_feedback"
    COMPLETED = "completed"


@dataclass
class WorkflowState:
    """工作流运行时状态"""

    phase: WorkflowPhase = WorkflowPhase.INIT
    review_round: int = 0             # 当前代码审核轮次
    result_review_round: int = 0      # 当前结果审核轮次
    code_approved: bool = False
    result_approved: bool = False


@dataclass
class UserFeedback:
    """用户反馈"""

    is_ok: bool = False
    corrections: Optional[str] = None
