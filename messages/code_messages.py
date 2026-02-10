"""
代码编写 / 审核相关数据类 — 与智能体解耦，独立存放
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class CodeWriteRequest:
    """代码编写请求"""

    analysis_result: str          # Figma 分析结果的文本描述
    requirements: str = ""        # 额外需求说明
    knowledge_context: str = ""   # 从知识库检索到的相关信息
    correction: str = ""          # 用户纠正点（如有）


@dataclass
class CodeWriteResult:
    """代码编写结果"""

    html_code: str = ""
    css_code: str = ""
    js_code: str = ""
    file_paths: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class CodeReviewRequest:
    """代码审核请求"""

    code: str                     # 需审核的代码（HTML + CSS）
    coding_rules: str = ""        # 需检查的编码规范


@dataclass
class CodeReviewResult:
    """代码审核结果"""

    approved: bool = False
    issues: List[str] = field(default_factory=list)
    suggestions: str = ""
    review_text: str = ""
